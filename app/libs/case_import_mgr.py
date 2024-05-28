# -*- coding: utf-8 -*-
# @Time    : 2022/4/12
# @Author  : Jiaxin Chen


import os
import re
import git
import copy
import json
import shutil
import requests
import datetime
import traceback
import subprocess
from urllib import parse
from app.commons import myrq, Process, utils, init_mymq, MyRedis, db
from flask import current_app
from app.models import Project, Case, OFFICIAL_ExecutorType, Group, ExecutorType, CaseType, case_schema
from sqlalchemy.orm.attributes import flag_modified


class GitProgress(git.RemoteProgress):
    def __init__(self, call_back, exec_type):
        super().__init__()
        self.call_back = call_back
        self.exec_type = exec_type
        self.count = 0

    def update(self, op_code, cur_count, max_count=None, message=''):
        if self.call_back and message and self.count % 10 == 0:
            self.call_back({
                "name": f"{self.exec_type}",
                "status": "ongoing",  # fail/success/skip/done
                "details": f"get: {cur_count}, total: {max_count}, info: {message}"
            })
        self.count += 1


class CaseImportMgr:

    @staticmethod
    def send_cmd(cmd, dir):
        current_app.logger.info(f'call linux cmd: {cmd}')
        child = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=dir,
        )
        outputs, _ = child.communicate()
        retcode = child.poll()
        outputs = outputs.decode(
            'utf-8') if isinstance(outputs, (bytes,)) else outputs
        if not retcode:
            return True, outputs
        else:
            return False, outputs

    @staticmethod
    def _git_cmd(cmd, dir, log_file):
        if 'git pull' in cmd:
            shutil.copyfile(
                current_app.config['ORIGIN_GIT_CREDENTIALS'], current_app.config['GIT_CREDENTIALS'])

        with open(log_file, "a+") as f:
            index = f.tell()
            current_app.logger.info(f'call linux cmd: {cmd}')
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=dir,
                # env=env
            )
            proc.wait()
            result = True if not proc.returncode else False
            f.seek(index)
            res_contents = f.readline()
            return result, res_contents

    @staticmethod
    def format_commit_log(s):
        pattern = r'"summary":"(.*?)","date":"'
        m = re.findall(pattern, s)
        if m:
            format_m = re.sub(r'[^\w ]+', '_', m[0])
            s = s.replace(m[0], format_m)
        return s

    @classmethod
    def collect_repo(cls, project):
        repos = []

        if project.extra.get('executors', {}):
            new_extra = copy.deepcopy(project.extra)
            new_extra['executors'] = {

            }
            executor_path_bash = os.path.join(
                project.get_product_path(), 'executors')
            for executor_type, executor_info in project.extra['executors'].items():
                new_extra['executors'][executor_type.lower()] = executor_info
                if not executor_info or not executor_info.get("url", ""):
                    continue
                executor_path = os.path.join(
                    executor_path_bash, executor_type.lower())
                repos.append({
                    "executor_path": executor_path,
                    "repo_info": executor_info,
                    "executor_type": executor_type.lower()
                })

            project.extra = new_extra
            project.save()

        # Compatible with older projects
        elif project.executor != 'default':
            if project.extra and project.extra.get("url", ""):
                executor_path = os.path.join(
                    project.get_product_path(), 'executor')
                repos.append({
                    "executor_path": executor_path,
                    "repo_info": project.extra,
                    "executor_type": project.executor.lower()
                })

        return repos

    @classmethod
    def delete_old(cls, project, call_back):
        call_back({
            "name": f"Remove old executor",
            "status": "ongoing",
            "details": f"Start removing......"
        })

        try:
            # Get new executors
            executor_types = []
            if project.extra.get('executors', {}):
                for executor_type, executor_info in project.extra['executors'].items():
                    executor_types.append(executor_type.lower())
            # Compatible with older projects
            elif project.executor != 'default':
                if project.extra and project.extra.get("url", ""):
                    executor_types.append(project.executor.lower())

            # Read what executors are in the executor directory
            executor_path_bash = os.path.join(
                project.get_product_path(), 'executors')
            exist_executor_file = []
            if os.path.exists(executor_path_bash):
                exist_executor_file = os.listdir(executor_path_bash)
                for file in exist_executor_file[::]:
                    if os.path.isfile(os.path.join(executor_path_bash, file)):
                        exist_executor_file.remove(file)

            # Filter out the executors to be deleted
            need_to_remove = []
            for file in exist_executor_file:
                if file not in executor_types:
                    need_to_remove.append(file)

            if need_to_remove:
                call_back({
                    "name": f"Remove old executor",
                    "status": "ongoing",
                    "details": f"Executors to be deleted: {need_to_remove}"
                })
                for file in need_to_remove:
                    # Delete the executor folder
                    path = os.path.join(executor_path_bash, file)
                    shutil.rmtree(path, ignore_errors=True)
                    # Set the deleted field of the case to true and remove the association with project
                    cases = Case.query.filter(
                        Case.project_id == project.id, Case.category.ilike(file)).all()
                    for case in cases:
                        project.cases.remove(case)
                        case.delete()
                    call_back({
                        "name": f"Remove old executor",
                        "status": "ongoing",
                        "details": f"Successfully deleted: {file}"
                    })
                call_back({
                    "name": f"Remove old executor",
                    "status": "success",
                    "details": f"All unneeded executors have been successfully deleted!!!"
                })
            else:
                call_back({
                    "name": f"Remove old executor",
                    "status": "skip",
                    "details": f"No executors to be deleted."
                })

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            call_back({
                "name": f"Remove old executor",
                "status": "fail",
                "details": str(err)
            })

    @classmethod
    def pull(cls, project_info, log_file, call_back):
        # project_info = {
        #     "executor_path": executor_path,
        #     "repo_info": project.extra,
        #     "executor_type": project.executor
        # }

        # repo_info = {
        #     "url": "https://git.garena.com/xun.gong/ssp_regression.git",
        #      "branch": "kobe",
        #      "project_path": ""
        # }
        # executor_type = "PY/WEBUI"
        # file deleted/file modify/branch changed/add files/  low priority: url changed

        ok = True
        call_back({
            "name": f"pull executor",
            "status": "ongoing",  # fail/success/skip/done
            "details": f"try to pull last codes"
        })
        try:
            # do more git action here
            repo = git.Repo(project_info['executor_path'])

            if repo.active_branch.name != project_info['repo_info']['branch']:
                # re-clone
                call_back({
                    "name": f"pull executor",
                    "status": "ongoing",
                    "details": f"wrong executor branch, re-clone...\n"
                               f"current branch: {repo.active_branch.name}\n"
                               f"expect branch: {project_info['repo_info']['branch']}\n"
                               f"Server network is slow, please be patient"
                })
                shutil.rmtree(
                    project_info['executor_path'], ignore_errors=True)
                cls.clone(project_info, log_file, call_back)
                repo = git.Repo(project_info['executor_path'])
                call_back({
                    "name": f"pull executor",
                    "status": "ongoing",
                    "details": f"re-clone success"
                })
            else:
                call_back({
                    "name": f"pull executor",
                    "status": "ongoing",
                    "details": f"git clean -df "
                })
                # Discard all changes in the current directory
                cls._git_cmd('git clean -df',
                             project_info['executor_path'], log_file)
                call_back({
                    "name": f"pull executor",
                    "status": "ongoing",
                    "details": f"git checkout . "
                })
                cls._git_cmd('git checkout .',
                             project_info['executor_path'], log_file)

                call_back({
                    "name": f"pull executor",
                    "status": "ongoing",
                    "details": f"git pull --recurse-submodules"
                })
                if cls._git_cmd('git pull --recurse-submodules', project_info['executor_path'], log_file)[0]:
                    call_back({
                        "name": f"pull executor",
                        "status": "ongoing",  # fail/success/skip/done
                        "details": f"Successfully pulling the latest code."
                    })
                    pass
                else:
                    retry = {
                        1: ["First", "git clean -df"],
                        2: ["Second", "git checkout ."],
                        3: ["Third", "git reset --hard"],
                    }

                    ok = False
                    for i in range(1, 4):
                        retry_time = retry[i][0]
                        retry_exec = retry[i][1]
                        call_back({
                            "name": f"pull executor",
                            "status": "ongoing",
                            "details": retry_time + " pull failed, perform the " + retry_time.lower() + " retry: " + retry_exec
                        })
                        cls._git_cmd(retry_exec,
                                     project_info['executor_path'], log_file)
                        # Show current status.
                        cls._git_cmd(f'git status',
                                     project_info['executor_path'], log_file)

                        if cls._git_cmd('git pull --recurse-submodules', project_info['executor_path'], log_file)[0]:
                            ok = True
                            break

                    if not ok:
                        # After three retries, pull still fails, try to delete executor and re-clone
                        call_back({
                            "name": f"pull executor",
                            "status": "ongoing",
                            "details": f"Fourth pull fails, perform the fourth retry: delete executor"
                                       f" and re-clone."
                        })
                        shutil.rmtree(project_info['executor_path'])
                        cls.clone(project_info, log_file, call_back)
                        repo = git.Repo(project_info['executor_path'])

                        # Show current status.
                        cls._git_cmd(f'git status',
                                     project_info['executor_path'], log_file)
                        if cls._git_cmd('git pull', project_info['executor_path'], log_file)[0]:
                            pass
                        else:
                            call_back({
                                "name": f"pull executor",
                                "status": "fail",
                                "details": "After re-clone still pull failed, please try again later."
                            })
                            return False

            summary = {
                "author": str(repo.active_branch.commit.author),
                "message": repo.active_branch.commit.message,
                "commit": repo.active_branch.commit.hexsha
            }

            call_back({
                "name": f"pull executor",
                "status": "success",
                "details": f"git info: {utils.convert_to_dictstr(summary)}"
            })
            # do more git action end

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            call_back({
                "name": f"pull executor",
                "status": "fail",
                "details": str(err)
            })
            ok = False
        return ok

    @classmethod
    def clone(cls, repo, log_file, call_back):
        ok = True
        try:
            shutil.copyfile(
                current_app.config['ORIGIN_GIT_CREDENTIALS'], current_app.config['GIT_CREDENTIALS'])
            git.Repo.clone_from(
                url=repo['repo_info']['url'], to_path=repo['executor_path'],
                progress=GitProgress(
                    call_back=call_back, exec_type=f"get executor: {repo['executor_type']}"),
                branch=repo['repo_info']['branch'], multi_options=['--recursive'])
            call_back({
                "name": f"get executor: {repo['executor_type']}",
                "status": "success",
                "details": f"done"
            })

            # cls._git_cmd('git submodule init', repo['executor_path'], log_file)
            # cls._git_cmd('git submodule update',
            #              repo['executor_path'], log_file)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            call_back({
                "name": f"get executor: {repo['executor_type']}",
                "status": "fail",
                "details": str(err)
            })
            ok = False
        return ok

    @classmethod
    def import_case_v2(cls, project_instance, log_file, category, author, token=None):
        from app.libs import TaskFactory
        ok = True
        try:
            errmsg = ''
            py_modules_path = os.path.join(
                project_instance.get_product_path(), "pips")
            if not os.path.exists(py_modules_path):
                os.makedirs(py_modules_path, exist_ok=True)

            cases_info_file = ''
            import_type = 'http'
            task = TaskFactory.get_import_task(category, project_instance, py_modules_path, log_file,
                                               author, token, import_type, cases_info_file)

            result_hd = MyRedis(current_app.config['URL_FOR_RESULT'])
            TaskFactory.set_origin_result(result_hd, task['channel_id'])

            # send task
            mymq = init_mymq()
            if category in OFFICIAL_ExecutorType:
                # The official type is sent to the worker of the official api by default
                env = project_instance.extra['executors'][category].get(
                    'type', 'api')
                ok = mymq.send('oneworker',
                               f"{category}__{env}", json.dumps(task))
            else:
                ok = mymq.send('oneworker',
                               f"{category}__common", json.dumps(task))
            mymq.close()
            # else:
            #     task_hd = MyRedis(
            #         current_app.config['REDIS']['URL_FOR_TASK'])
            #     current_app.logger.info(f"To send task: {task}")
            #     task_hd.lpush(cls._get_routekey(task), json.dumps(task))
            #     task_hd.disconnect()

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            errmsg = str(err)
            log_file = None
            ok = False

        return ok, log_file, errmsg


@myrq.job('sync')
def git_core(id, author='someone', token=None):
    ok = True
    process = Process(project_id=id)
    if process.is_ongoing():
        msg = "last process is still ongoing"
        current_app.logger.warn(msg)
        return ok, msg
    else:
        current_app.logger.warn(f"reset process")
        process.reset()

    try:
        project = Project.query.get(id)
        log_path = project.get_log_path()
        if not os.path.exists(log_path):
            os.makedirs(log_path, exist_ok=True)

        log_file = os.path.join(
            log_path, datetime.datetime.now().strftime("%Y-%m-%d__%H:%M:%S") + '.log')
        with open(log_file, 'w') as f:
            f.write(
                f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %p")} {project.name} to update cases, started by {author}:\n')

        repos = CaseImportMgr.collect_repo(project)
        current_app.logger.info(f"all repos: {repos}")

        # Remove unneeded executors
        CaseImportMgr.delete_old(project, process.update)

        for repo in repos:
            process.update({
                "name": f"get executor: {repo['executor_type']}",
                "status": "ongoing",
                "details": f"start to clone repo: {utils.convert_to_dictstr(repo['repo_info'])}\n"
                           f"Server network is slow, please be patient"
            })

            if os.path.exists(repo['executor_path']):
                try:
                    _, res = CaseImportMgr._git_cmd(
                        'git config --get remote.origin.url', repo['executor_path'], log_file)
                    if 'git.garena.com' in res:
                        current_url = res.strip().split('git.garena.com')[1]
                        new_url = repo['repo_info'].get(
                            'url', '').strip().split('git.garena.com')[1]
                        if current_url[1:] != new_url[1:]:
                            raise git.exc.InvalidGitRepositoryError

                    rg = git.Repo(repo['executor_path'])
                    process.update({
                        "name": f"get executor: {repo['executor_type']}",
                        "status": "skip",
                        "details": f"repo exist!"
                    })

                except git.exc.InvalidGitRepositoryError:
                    msg = f"git repo {repo['executor_path']} is invalid, re-clone it!"
                    current_app.logger.error(msg)
                    process.update({
                        "name": f"get executor: {repo['executor_type']}",
                        "status": "ongoing",
                        "details": msg
                    })
                    shutil.rmtree(repo['executor_path'], ignore_errors=True)
                    process.update({
                        "name": f"get executor: {repo['executor_type']}",
                        "status": "ongoing",
                        "details": f"Old executor successfully removed."
                    })

                    # clone
                    ret = CaseImportMgr.clone(repo, log_file, process.update)
                    if not ret:
                        continue

                # pull
                ret = CaseImportMgr.pull(repo, log_file, process.update)
                if not ret:
                    continue

            else:
                # clone
                ret = CaseImportMgr.clone(repo, log_file, process.update)
                if not ret:
                    continue

            # Store the latest commit information in the database
            r = git.Repo(repo['executor_path'])
            commit_log = r.git.log('--pretty={"commit":"%h","author":"%an","summary":"%s","date":"%cd"}',
                                   max_count=1)
            commit_dic = json.loads(
                CaseImportMgr.format_commit_log(commit_log))
            gmt_date = datetime.datetime.strptime(commit_dic["date"], '%a %b %d %H:%M:%S %Y %z') +\
                datetime.timedelta(hours=8)
            commit_dic["date"] = gmt_date.strftime('%Y-%m-%d %H:%M:%S')

            try:
                commit_dic = json.loads(
                    CaseImportMgr.format_commit_log(commit_log))
                commit_dic["date"] = datetime.datetime.strptime(commit_dic["date"], '%a %b %d %H:%M:%S %Y %z').strftime(
                    '%Y-%m-%d %H:%M:%S')

                if not project.commit_info:
                    project.commit_info = {repo['executor_type']: commit_dic}
                else:
                    project.commit_info[repo['executor_type']] = commit_dic
                flag_modified(project, "commit_info")
                current_app.logger.info(
                    f"commit_log: {commit_log}, commit_dic: {commit_dic}")
                project.save()

            except Exception:
                current_app.logger.error(
                    f"commit_log: {commit_log} format error!")

            process.update({
                "name": "assign import task",
                "status": "ongoing",
                "details": f"send task to {repo['executor_type']} worker, user={author}"
            })
            ok, _, errmsg = CaseImportMgr.import_case_v2(
                project, log_file, repo['executor_type'], author=author, token=token)
            if not ok:
                process.update({
                    "name": "assign import task",
                    "status": "fail",
                    "details": f"{errmsg}"
                })
            else:
                process.update({
                    "name": "assign import task",
                    "status": "success",
                    "details": f"done"
                })
    except Exception:
        err = traceback.format_exc()
        current_app.logger.error(err)
        process.update({
            "name": "rq git_core error",
            "status": "fail",
            "details": f"{err}"
        })
        ok = False

    finally:
        process.close()

    return ok, log_file


class CaseUpdateMgr:
    @staticmethod
    def get_pk(value):
        '''
            return bool pk
            if bool is True,  means pk in extra
            if bool is False, means pk normal
        '''
        pk = value["primary_key"]
        if pk in value:
            return False, pk
        else:
            return True, pk.split('.')[-1]

    @staticmethod
    def post_check(value, project_executors, callback):
        normal = {
            "name": "string",
            "primary_key": "same with name",
            "author": "string",
            "category": "string",
            "type": "string",
            # "priority": "string",
            # "description": "string",
            "project_id": 0,
            "group_id": 0,
            # "group_name": "",
            "extra": {},
            # "timeout": 1800
        }
        errors = []
        try:
            for k, v in normal.items():
                if k == "name" and k in value:
                    if len(value[k]) > 256:
                        errors.append('invalid name')
                        callback({
                            "name": f"update cases",
                            "status": "fail",
                            "details": f'{value.get("name", "")} case name error: case name longer than 256!'
                        })

                elif k == 'author' and k in value:
                    if not str(value[k]).endswith('@shopee.com'):
                        errors.append('invalid author')
                        callback({
                            "name": f"update cases",
                            "status": "fail",
                            "details": f'{value.get("name", "")} author error: author should be email address!'
                        })

                elif k == "primary_key" and k in value:
                    if value[k] in value or (value[k].startswith('extra') and value[k].split('.')[-1] in value.get("extra", {})):
                        pass
                    else:
                        errors.append(f"primary_key wrong!")
                elif k == "group_id":
                    if k in value and value['group_id']:
                        groups = Group.query.filter_by(
                            id=value['group_id']).count()
                        if not groups:
                            errors.append(
                                f"group: {k} not exist! {value['group_id']}")
                    else:
                        pass

                # elif k == "group_name":
                #     if k in value and value['group_name']:
                #         group_list = value['group_name'].split(os.sep)
                #         # project_obj = Project.query.get(value['project_id'])
                #         mum_id = Group.query.filter_by(mum_id=None).all()[0].id
                #         for group_name in group_list:
                #             groups = Group.query.filter_by(
                #                 name=group_name, project_id=value['project_id'], mum_id=mum_id).all()
                #             if not groups:
                #                 group = Group(
                #                     name=group_name, project_id=value['project_id'], mum_id=mum_id)
                #                 group.save()
                #                 mum_id = group.id
                #             else:
                #                 mum_id = groups[0].id
                #                 errors.append(
                #                     f"group: {k} not exist! {value['group_id']}")
                #     else:
                #         pass

                elif k == "category":
                    if k in value and value[k].lower() in ExecutorType:
                        value[k] = value[k].lower()
                    else:
                        errors.append(
                            f"category error: valid category are: {ExecutorType.keys()}")

                    if value[k].lower() not in project_executors:
                        errors.append(f'category error: '
                                      f'case: {value.get("name", "")} category information[{value[k].lower()}] '
                                      f'differs from project[{project_executors}]')

                elif k == "type":
                    if k in value and value[k] in CaseType:
                        pass
                    else:
                        errors.append(
                            f"type error: valid type are: {CaseType.keys()}")

                # elif k == "timeout" and k in value:
                #     if isinstance(value[k], int):
                #         pass
                #     elif isinstance(value[k], str):
                #         try:
                #             timeout = int(value[k])
                #         except Exception as err:
                #             errors.append(
                #                 f"{k}: value has wrong type! {err}"
                #             )
                #     else:
                #         errors.append(f"{k}: value has wrong type, expect int!")

                elif k in value:
                    if isinstance(value[k], type(v)):
                        pass
                    else:
                        errors.append(
                            f"{k}: value has wrong type! [{type(value[k])} != {type(v)}]")

                else:
                    errors.append(f"{k} missed!")

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            errors.append(str(err))

        return errors

    @staticmethod
    def put_data(case, json_data, callback):
        case.put_check(json_data)
        for k, v in json_data.items():
            if k in ('id', 'created_time', 'updated_time', 'primary_key'):
                continue
            elif k == 'timeout':
                v = int(v)
                if v < 60:
                    setattr(case, k, 60)
                elif v > 3600:
                    setattr(case, k, 3600)
                else:
                    setattr(case, k, v)
                continue

            else:
                setattr(case, k, v)

        case.get_base_group()
        case.deleted = False
        case.save()
        msg = f"Put case: {case.name} success! {case.id}"
        callback({
            "name": f"update cases",
            "status": "ongoing",
            "details": msg
        })
        current_app.logger.info(msg)

    @staticmethod
    def post_data(json_data, callback):
        json_data.pop('primary_key', None)
        json_data['is_draft'] = True
        Case.post_check(json_data)

        timeout = json_data.get('timeout', None)
        if timeout:
            timeout = int(timeout)
            if timeout < 60:
                json_data['timeout'] = 60
            elif timeout > 3600:
                json_data['timeout'] = 3600
            else:
                json_data['timeout'] = timeout

        case = case_schema.load(utils.del_id_none(json_data))
        case.get_base_group()
        case.save()
        msg = f"Post case: {case.name} success! {case.id}"
        callback({
            "name": f"update cases",
            "status": "ongoing",
            "details": msg
        })
        current_app.logger.info(msg)
        return case.id

    @staticmethod
    def manual_case_id_sync(case_id_list, manual_case_id_list, old_manual_case_id_list):
        try:
            err = ''
            url = parse.urljoin(
                current_app.config['CASEMANAGE_URL'], current_app.config['LINK_AUTO_CASE'])
            data = {
                "before_case_id": old_manual_case_id_list,
                "case_id": manual_case_id_list,
                "auto_case_id": case_id_list
            }
            resp = requests.post(url, json=data, timeout=5)
            if resp.status_code != 200:
                errmsg = f"Link auto error: {resp.status_code}"
                current_app.logger.warn(errmsg)
                raise Exception(errmsg)
            return err

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return err

    @staticmethod
    def del_empty_group(project_id):
        def _del_empty_group(group_id):
            msg = ''
            group = Group.query.get(group_id)
            children = [g for g in group.children if not g.deleted]
            if len(children) == 0:
                # leaf node
                if len([case for case in group.cases if not case.deleted]) == 0:
                    # empty group
                    # group.rdelete()
                    msg = f'Group [{group.name}] is empty, to delete \n'
                return msg
            else:
                for child in children:
                    msg += _del_empty_group(child.id)

            if len([g for g in group.children if not g.deleted]) == 0 and \
                    len([case for case in group.cases if not case.deleted]) == 0:
                group.rdelete()
                msg += f'Group [{group.name}] is empty, to delete \n'

            return msg

        try:
            msg = ''
            root_groups = Group.query.filter_by(
                project_id=project_id, mum_id=None, deleted=False).all()
            for root_group in root_groups:
                msg += _del_empty_group(root_group.id)

            return True, msg

        except Exception as e:
            return False, 'process error,reason:%s' % str(e)


@myrq.job('sync')
def update_cases(json_data):
    process = None
    err_case = None
    project_name = ''
    project_author = ''
    try:
        if not isinstance(json_data, list) or not json_data:
            raise ValueError("json format should be: [{}, {}...]")
        else:
            project_id = json_data[0]['project_id']
            category = json_data[0]['category'].lower()
            cases_num = Case.query.filter(
                Case.project_id == project_id, Case.category.ilike(category), Case.deleted == False).count()

            process = Process(project_id=project_id)
            process.update({
                "name": f"update cases",
                "status": "ongoing",
                "details": f"updating cases..."
            })

            process.update({
                "name": f"update cases",
                "status": "ongoing",
                "details": f"{cases_num} old cases of category {category} found, to delete them..."
            })
            Case.query.filter(
                Case.project_id == project_id, Case.category.ilike(
                    category), Case.deleted == False
            ).update({Case.deleted: True}, synchronize_session=False)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.error(traceback.format_exc())

        project = None
        project_executors = []
        default_group = None
        count = 0
        case_id_list, manual_case_id_list, old_manual_case_id_list = [], [], []

        err_msg = ''
        for case_dict in json_data:
            err_case = case_dict
            if not isinstance(case_dict, dict):
                raise ValueError("json format should be): [{}, {}...]")
            else:
                if not project:
                    project = Project.query.get(case_dict['project_id'])
                    project_name, project_author = project.name, project.author
                    project_executors = [k.lower()
                                         for k, v in project.extra.get("executors", {}).items() if v.get("url")]

                errors = CaseUpdateMgr.post_check(
                    case_dict, project_executors, process.update)
                if errors:
                    if len(errors) == 1 and 'invalid author' == errors[0]:
                        err_msg += 'Invalid author format: author should be email address \n'
                        continue
                    elif len(errors) == 1 and 'invalid name' == errors[0]:
                        err_msg += f'Invalid case name: {err_case["name"]} \n'
                        continue
                    elif len(errors) == 1 and 'category error' in errors[0]:
                        err_msg += f'{errors[0]} \n'
                        continue
                    elif len(errors) == 2 and ('invalid name' in errors and 'invalid author' in errors):
                        err_msg += f'Invalid author and case name: {err_case["name"]} \n'
                        continue
                    else:
                        raise ValueError(errors)
                else:
                    flag, pk = CaseUpdateMgr.get_pk(case_dict)

                    if case_dict.get("group_id", None):
                        group = Group.query.filter_by(
                            id=case_dict["group_id"], project_id=case_dict['project_id']).first()
                        if group:
                            case_dict["group_id"] = group.id
                        else:
                            if default_group is None:
                                default_group = Group.query.filter_by(
                                    name=project.name, project_id=case_dict['project_id']).first()
                            case_dict["group_id"] = default_group.id

                    elif case_dict.get("group_name", None):
                        group_name = case_dict.pop("group_name")
                        if default_group is None:
                            default_group = Group.query.filter_by(
                                name=project.name, project_id=case_dict['project_id']).first()
                        mum_id = default_group.id
                        group_list = group_name.split(os.sep)
                        for gn in group_list:
                            groups = Group.query.filter_by(
                                name=gn, project_id=case_dict['project_id'], mum_id=mum_id).first()
                            if not groups:
                                group = Group(
                                    name=gn, project_id=case_dict['project_id'], mum_id=mum_id)
                                group.save()
                                mum_id = group.id
                            else:
                                mum_id = groups.id
                        case_dict["group_id"] = mum_id

                    else:
                        if default_group is None:
                            default_group = Group.query.filter_by(
                                name=project.name, project_id=case_dict['project_id']).first()
                            if not default_group:
                                errmsg = f"group {project.name} with project id {project_id} not found!!!"
                                current_app.logger.error(errmsg)
                                raise Exception(errmsg)

                        case_dict["group_id"] = default_group.id

                    if 'group_name' in case_dict:
                        case_dict.pop("group_name")
                    case_dict["extra"].update(
                        {"sys_env": case_dict.get("sys_env", {})})

                    if flag is False:
                        # if not case_dict.get('name', None):
                        case_dict["name"] = case_dict[pk]

                        case = Case.query.filter(Case.project_id == case_dict['project_id'],
                                                 Case.group_id == case_dict["group_id"], getattr(
                            Case, pk) == case_dict[pk]).first()
                        if case:
                            case_id = case.id
                            old_manual_case_id = case.manual_case_id if case.manual_case_id else 0
                            current_app.logger.warn(
                                "CaseSyncView to put case")
                            CaseUpdateMgr.put_data(
                                case, case_dict, process.update)

                        else:
                            current_app.logger.warn(
                                "CaseSyncView to post case")
                            case_id = CaseUpdateMgr.post_data(
                                case_dict, process.update)
                            old_manual_case_id = 0

                    else:
                        # if not case_dict.get('name', None):
                        case_dict["name"] = case_dict["extra"].get(pk)
                        cases = Case.query.filter(
                            Case.project_id == case_dict['project_id']).all()

                        dst_cases = None
                        old_manual_case_id = 0
                        for case in cases:
                            if case.extra.get(pk, -1) == case_dict["extra"].get(pk, -2):
                                old_manual_case_id = case.manual_case_id if case.manual_case_id else 0
                                current_app.logger.warn(
                                    "CaseSyncView to put case")
                                CaseUpdateMgr.put_data(
                                    case, case_dict, process.update)
                                dst_cases = case
                                break

                        if dst_cases:
                            case_id = dst_cases.id
                        else:
                            current_app.logger.warn(
                                "CaseSyncView to post case")
                            case_id = CaseUpdateMgr.post_data(
                                case_dict, process.update)

                    if case_dict.get('manual_case_id', None):
                        case_id_list.append(case_id)
                        manual_case_id_list.append(
                            case_dict['manual_case_id'])
                        old_manual_case_id_list.append(old_manual_case_id)
                    count += 1

        if err_msg:
            err_case = None
            raise Exception(err_msg)

        process.update({
            "name": f"update cases",
            "status": "success",
            "details": f"total update cases: {count}"
        })
        # if case_id_list:
        #     res = CaseUpdateMgr.manual_case_id_sync(
        #         case_id_list, manual_case_id_list, old_manual_case_id_list)
        #     if res:
        #         raise Exception(res)

        process.update({
            "name": "delete empty group",
            "status": "ongoing",
            "details": f"start delete empty group..."
        })
        result, msg = CaseUpdateMgr.del_empty_group(
            project_id)  # SPSZQA-6043 sync后删除多余的空目录
        process.update({
            "name": "delete empty group",
            "status": "success" if result else "fail",
            "details": msg
        })

    except Exception as err:
        if err_case:
            err = str(err) + '\n' + \
                f'Error when dealing with case: {err_case["name"]}'
        if process:
            process.update({
                "name": f"update cases",
                "status": "fail",
                "details": str(err)
            })
        current_app.logger.error(f"Case many error: {traceback.format_exc()}")

    finally:
        if process:
            if not process.check_done('case collect'):
                process.update({
                    "name": f"case collect",
                    "status": "done",
                    "details": f"done"
                })
            process.send_fail_to_people(project_author, project_name)
            process.finish()
