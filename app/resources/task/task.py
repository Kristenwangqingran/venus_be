# -*- coding: utf-8 -*-
# @Time    : 2020/09/01
# @Author  : GongXun

import os
import time
import copy
import requests
import json
import re
import base64
from flask import request, current_app
from datetime import datetime

from app import limiter
from app.commons import ma, resp_return, utils, MyRedis, config, Process, myrq
from app.resources import BaseResource, OpenAPIRequestArgs
import traceback
from app.models import (Case, CaseResult, Casesuite,
                        SuiteResult, casesuite_schema, ProductLine, SubLine, Feature, Project, Group, ExecutorType)
from app.resources.base_resource import limiter_by_path, limiter_by_project, rate_limit_for_user, index_ratelimit_error_responder_for_user
from app.resources.project import ProjectsView
from app.libs import clean_logs, ExecUtils, ExecMgr, goc_profile, git_core, _run_suite_v2, parser, Pipeline, common_pipeline_callback
from app.commons.config import get_config

current_env = get_config()


class CaseRequestArgs(ma.Schema):
    env_id = ma.Integer(required=True)
    timeout = ma.Integer(default=1)


class CaseRunView(BaseResource):
    decorators = [limiter.limit(
        config.CASE_LIMIT_PATTERN, key_func=limiter_by_path)]

    def post(self, id):
        '''runtime_args:
            devices: [{k, v, }, ]
            browser: []
        '''
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        try:
            case = Case.query.get(id)
            if case:
                data = {
                    "author": request.headers.get('email', 'no-user'),
                    "code_coverage": json_data.get("code_coverage", {}),
                    "official_mobile": json_data.get("official_mobile", {}),
                    "official_web": json_data.get("official_web", {}),
                    "api": json_data.get("api", {}),
                    "common": json_data.get("common", {}),
                }

                result_hd = MyRedis(current_app.config['URL_FOR_RESULT'])
                record_id = int(datetime.now().timestamp())
                errmsg = ExecMgr.run_case_v2(
                    case_instance=case, data=data, record_id=record_id)
                if errmsg:
                    return resp_return('RUN_ERROR', new_msg=errmsg)

                ret = utils.get_result_id(result_hd, record_id, timeout=30)

                if not ret:
                    return resp_return('TASK_IN_QUEUE')
                else:
                    return resp_return('EXECUTE_OK', append=ret)

            else:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding case found!")

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))

    @limiter.exempt
    def delete(self, id):
        caseresult = CaseResult.query.filter_by(id=id).first()
        if caseresult:
            try:
                ExecUtils.cancel_task(id)
                caseresult.status = 'canceled'
                caseresult.save()
            except Exception as err:
                return resp_return('TASK_ERROR', new_msg=str(err))
            else:
                return resp_return('CANCELED_OK')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding case_result found!")


class CasesRunView(BaseResource):

    def post(self, ):
        try:
            json_data = request.get_json()

            user = request.headers.get('email')

            if not user:
                current_app.logger.error(
                    f"some gays want to run suite without login!")
                return resp_return('NO_LOGIN')

            cases = json_data['cases']
            if cases:
                case_instance = Case.query.get(cases[0])
                suite_dict = {
                    "name": f"Batch-execution-{datetime.now().strftime('%m-%d %H:%M:%S')}",
                    "case_id_list": cases,
                    "description": "This case suite will be delete soon...",
                    "project_id": case_instance.project_id,
                    "plan": {
                        "sequence": {

                        },
                        "dependency": {

                        },
                        "must_serial": []
                    },
                    "run_all_config": {
                        "cross_project": False,
                        "run_all": []
                    }
                }

                Casesuite.post_check(suite_dict)
                casesuite = casesuite_schema.load(
                    utils.del_id_none(suite_dict))
                casesuite.save()

                data = {
                    "author": user,
                    "code_coverage": json_data.get("code_coverage", {}),
                    "official_mobile": json_data.get("official_mobile", {}),
                    "official_web": json_data.get("official_web", {}),
                    "api": json_data.get("api", {}),
                    "common": json_data.get("common", {}),
                }

                error = ExecMgr.run_suite_v2(
                    suite_id=casesuite.id, data=data)
                if error:
                    return resp_return('COMMON_ERROR', new_msg=error)
                else:
                    return resp_return('EXECUTE_OK')
            else:
                return resp_return('NOFOUND_ERROR', new_msg='No corresponding cases found!')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class ManualCaseRunView(BaseResource):
    decorators = [limiter.limit(
        config.CASE_LIMIT_PATTERN, key_func=limiter_by_path)]

    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        try:
            manual_case_id_list = json_data.get("manual_case_id_list", [])
            execute_case_id_list = json_data.get("execute_case_id_list", [])
            email = json_data.get("email", "no-user")
            case_execute_map = dict(
                zip(manual_case_id_list, execute_case_id_list))

            data = {
                "author": email,
                "code_coverage": json_data.get("code_coverage", {}),
                "official_mobile": json_data.get("official_mobile", {}),
                "official_web": json_data.get("official_web", {}),
                "api": json_data.get("api", {}),
                "common": json_data.get("common", {}),
            }
            errmsg = ExecMgr.run_manual_cases(
                manual_case_id_list, data, case_execute_map)

            if not errmsg:
                return resp_return('EXECUTE_OK')
            else:
                return resp_return('RUN_ERROR', new_msg=errmsg)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SuiteRequestArgs(ma.Schema):
    env_name = ma.String(required=False)
    region = ma.String(required=False)
    timeout = ma.Integer(default=1)
    user = ma.String(required=False)


class SuiteRunView(BaseResource):
    decorators = [limiter.limit(
        config.SUITE_LIMIT_PATTERN, key_func=limiter_by_path)]

    def post(self, id):
        try:
            json_data = request.get_json()
            use_plan_config = json_data.get('use_plan_config', False)

            user = request.headers.get('email')
            if not user:
                current_app.logger.error(
                    f"some gays want to run suite: {id} without login!")
                return resp_return('NO_LOGIN')

            casesuite = Casesuite.query.get(id)
            if casesuite:
                source = json_data if not use_plan_config else casesuite.runtime_config
                if not isinstance(source.get('code_coverage', {}).get('args'), dict):
                    return resp_return('JSON_ERROR', new_msg='goc configuration format error')

                data = {
                    "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "author": user,
                    "code_coverage": source.get("code_coverage", {}),
                    "official_mobile": source.get("official_mobile", {}),
                    "official_web": source.get("official_web", {}),
                    "api": source.get("api", {}),
                    "common": source.get("common", {}),
                    "setup": source.get("setup", {})
                }

                result_hd = MyRedis(current_app.config['URL_FOR_RESULT'])
                record_id = int(datetime.now().timestamp())
                error = ExecMgr.run_suite_v2(
                    suite_id=id, data=data, record_id=record_id)
                if error:
                    return resp_return('COMMON_ERROR', new_msg=error)

                ret = utils.get_result_id(result_hd, record_id, timeout=30)

                if not ret:
                    return resp_return('TASK_IN_QUEUE')
                else:
                    return resp_return('EXECUTE_OK', append=ret)

            else:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding casesuite found!")

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    @limiter.exempt
    def delete(self, id):
        suiteresult = SuiteResult.query.filter_by(id=id).first()
        if suiteresult:
            try:
                suiteresult.status = 'canceled'
                suiteresult.save()

            except Exception as err:
                suiteresult.status = 'canceled'
                suiteresult.save()
                return resp_return('TASK_ERROR', new_msg=str(err))
            else:
                return resp_return('CANCELED_OK')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding suiteresult found!")


class SuiteRunForWebhookView(BaseResource):
    decorators = [limiter.limit(rate_limit_for_user, key_func=limiter_by_path,
                                on_breach=index_ratelimit_error_responder_for_user)]

    def post(self, id):
        try:
            user = request.headers.get('email', 'webhook')
            request_body = request.get_json()
            casesuite = Casesuite.query.get(id)
            if casesuite:
                source = casesuite.runtime_config
                if not isinstance(source.get('code_coverage', {}).get('args'), dict):
                    return resp_return('JSON_ERROR', new_msg='goc configuration format error')

                common_params = source.get("common", {})
                if "extra" not in common_params or not isinstance(common_params["extra"], dict):
                    common_params["extra"] = {}
                common_params["extra"].update(
                    request_body.get("pipeline_info", {}))

                api_params = source.get("api", {})
                if "routing" not in api_params:
                    api_params["routing"] = {}
                api_params["routing"]["pfb"] = common_params["extra"].get(
                    "PFB", "")
                data = {
                    "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "author": user,
                    "code_coverage": source.get("code_coverage", {}),
                    "official_mobile": source.get("official_mobile", {}),
                    "official_web": source.get("official_web", {}),
                    "api": api_params,
                    "common": common_params,
                }

                result_hd = MyRedis(current_app.config['URL_FOR_RESULT'])
                record_id = int(datetime.now().timestamp())
                error = ExecMgr.run_suite_v2(
                    suite_id=id, data=data, record_id=record_id)
                if error:
                    return resp_return('COMMON_ERROR', new_msg=error)

                ret = utils.get_result_id(result_hd, record_id, timeout=30)

                if not ret:
                    return resp_return('TASK_IN_QUEUE')
                else:
                    return resp_return('EXECUTE_OK', append=ret)

            else:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding casesuite found!")

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HookRequestArgs(OpenAPIRequestArgs):
    threshold = ma.Float(default=1)


class SuiteRunForWebhooksView(BaseResource):
    decorators = [limiter.limit(rate_limit_for_user, key_func=limiter_by_project,
                                on_breach=index_ratelimit_error_responder_for_user)]

    webhook_suite = "webhook-suite"

    @classmethod
    def _check_executor(self, data):
        for executor_type, executor_value in data.items():
            if executor_type in ExecutorType:
                if executor_value["url"] and executor_value["branch"]:
                    return executor_type
        return None

    @classmethod
    def post_check(self, value):
        """
        return: errors, status code, extra
            errors empty means no error;
            status code:
                0: just use suite_id directly
                1: need pull the project 1st, then create a suite automately
                2: the project already exist, but suite not exist
                3: suite exist, just run
        """
        normal = {
            "project": {
                "line": "",
                "subline": "",
                "feature": "",
                "name": "this will show at Venus",
                "repo": {
                    "rpc": {
                        "url": "https://git.garena.com/shopee/szqa/messaging/noti/spex-api-testing",
                        "branch": "dev"
                    },
                    "cases_forder": "will run cases in this forder"
                }
            },
            "exec_strategy": {
                "update": False,
                "serial": True,
                "retry": 0,
                "extra": {},
            },
            "exec_args": {
                "env": {
                    "name": "test-env",
                },
                "routing": {
                    "pfb": "123"
                },
                "region": "SG"
            },
            "suite": {
                "suite_id": 0,
                "noti": {}
            }
        }
        errors = []

        try:
            # if suite_id is assigned, use it directly
            if int(value.get("suite", {}).get("suite_id", 0)) > 0:
                suite = Casesuite.query.get(int(value['suite']["suite_id"]))
                if not suite or suite.deleted is True:
                    errors.append(
                        f"No corresponding casesuite found: {value['suite']['suite_id']}")
                    return errors, -1, None
                return errors, 0, (suite, {"api": value.get('exec_args', {}), "common": value.get('exec_strategy', {})})

            # check project info
            else:
                project_info = value["project"]
                if project_info["line"] and project_info["subline"] and project_info["feature"] and project_info['name'] and project_info['repo']["cases_forder"]:
                    executor_type = self._check_executor(project_info['repo'])
                    line = ProductLine.query.filter_by(
                        name=project_info["line"]).one()
                    subline = SubLine.query.filter_by(
                        name=project_info["subline"], product_line_id=line.id).one()
                    feature = Feature.query.filter_by(
                        name=project_info["feature"], sub_line_id=subline.id).one()
                    projects = Project.query.filter_by(
                        name=project_info['name'], feature_id=feature.id, deleted=False, status='active').all()
                    if len(projects) < 1:
                        return errors, 1, (line, subline, feature, executor_type)
                    else:
                        project = projects[0]
                        suites = Casesuite.query.filter_by(
                            name=self.webhook_suite, deleted=False, project_id=project.id).all()
                        if len(suites) < 1:
                            return errors, 2, (project,)
                        else:
                            return errors, 3, (suites[0],)

                else:
                    errors.append(f"project info error")

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            errors.append(str(err))
        return errors, -1, None

    @classmethod
    def create_suite(self, user, request_body, project):
        group_ids = []
        forder = request_body["project"]['repo']['cases_forder']
        subforders = forder.split(os.sep)
        current_app.logger.info(f"forder: {forder}, subforders: {subforders}")
        mun_group = None
        me = None
        for subforder in subforders:
            current_app.logger.info(f"subforder: {subforder}")
            if not subforder:
                continue
            if mun_group is None:
                mun_group = Group.query.filter_by(
                    name=project.name, project_id=project.id, deleted=False).one()
                current_app.logger.info(
                    f"update mun_group to: {mun_group.name, mun_group.id}")
            me = Group.query.filter_by(
                name=subforder, project_id=project.id, mum_id=mun_group.id, deleted=False).one()
            mun_group = me
        group_ids.append(me.id)

        suite_dict = {
            "noti": request_body["suite"]['noti'],
            "is_manual": False,
            "run_all_config": {
                "run_all": [{
                    "id": group_id,
                    "type": "group"
                } for group_id in group_ids]
            },
            "plan": {
                "sequence": {},
                "dependency": {},
                "must_serial": []
            },
            "schedule": {
                "status": "disabled",
            },
            "author": user,
            "name": self.webhook_suite,
            "project_id": project.id,
            "runtime_config": {
                "common": request_body["exec_strategy"],
                "api": request_body["exec_args"]
            }
        }

        Casesuite.post_check(suite_dict)
        casesuite = casesuite_schema.load(
            utils.del_id_none(suite_dict))
        casesuite.save()
        return casesuite

    @classmethod
    def get_data(self, user, runtime_config):
        data = {
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "author": user,
            "code_coverage": runtime_config.get("code_coverage", {}),
            "official_mobile": runtime_config.get("official_mobile", {}),
            "official_web": runtime_config.get("official_web", {}),
            "api": runtime_config.get("api", {}),
            "common": runtime_config.get("common", {}),
        }
        return data

    @classmethod
    def merge_runtime_config(cls, dict1, dict2):
        if not isinstance(dict1, dict) or not isinstance(dict2, dict):
            return dict1
        for key, info in dict2.items():
            if key in dict1:
                if isinstance(dict1[key], dict):
                    dict1[key] = cls.merge_runtime_config(dict1[key], info)
                elif isinstance(dict1[key], list):
                    dict1[key].extend(info)
                else:
                    dict1[key] = info
            else:
                dict1[key] = info
        return dict1

    @classmethod
    def wait_import(self, project_id, timeout=30 * 60):
        finish = False
        process = Process(project_id=project_id)
        while timeout:
            if process.check_finish():
                finish = True
                break
            else:
                time.sleep(10)
                timeout -= 10
        return finish

    def run_suite(self, suite_obj, data):
        result_hd = MyRedis(current_app.config['URL_FOR_RESULT'])
        record_id = int(datetime.now().timestamp())
        error = ExecMgr.run_suite_v2(
            suite_id=suite_obj.id, data=data, record_id=record_id)
        if error:
            raise Exception(error)
        return utils.get_result_id(result_hd, record_id, timeout=10)

    def run(self, user, status_code, extra, request_body):
        if status_code in [0, ]:  # run suite directly
            suite_obj = extra[0]
            runtime_config = copy.deepcopy(suite_obj.runtime_config)
            runtime_config = SuiteRunForWebhooksView.merge_runtime_config(
                runtime_config, extra[1])
            current_app.logger.info(
                f"suite_obj: {suite_obj}, runtime_config: {runtime_config}")
            ret = self.run_suite(
                suite_obj, self.get_data(user, runtime_config))
            return None, ret

        # need pull the project 1st, then create a suite automately
        elif status_code in [1, ]:
            project_info = {
                "name": request_body["project"]['name'],
                "description": "webhook auto created",
                "author": user,
                "extra": {
                    "executors": {
                        extra[3]: request_body["project"]['repo'][extra[3]]
                    }
                },
                ""
                "public_project": False,
                "feature_id": extra[2].id
            }
            project = ProjectsView.create_project(project_info)
            # pull
            ok, _ = git_core(project.id, user)
            if not ok:
                error = "import case error"
                current_app.logger.error(error)
                return error, None
            else:
                if self.wait_import(project.id) is False:
                    return "import case not finish", None

            # create suite
            suite_obj = self.create_suite(user, request_body, project)

            # run
            ret = self.run_suite(suite_obj, data=self.get_data(
                user, suite_obj.runtime_config))
            return None, ret

        elif status_code in [2, ]:  # the project already exist, but no suite
            # pull
            ok, _ = git_core(extra[0].id, user)
            if not ok:
                error = "import case error"
                current_app.logger.error(error)
                return error, None
            else:
                if self.wait_import(extra[0].id) is False:
                    return "import case not finish", None

            # create suite
            suite_obj = self.create_suite(user, request_body, extra[0])
            # run
            ret = self.run_suite(suite_obj, data=self.get_data(
                user, suite_obj.runtime_config))
            return None, ret

        elif status_code in [3, ]:  # run suite directly
            suite_obj = extra[0]
            ret = self.run_suite(suite_obj, self.get_data(
                user, suite_obj.runtime_config))
            return None, ret

        else:
            return 'request body error', None

    def post(self):
        try:
            user = request.headers.get('email', 'webhook')
            request_body = request.get_json()
            request_args = HookRequestArgs().dump(request.args)
            callback = request.headers.get("Ci-Flow-Callback", "")
            if request_args.get("skip", False) is True:
                common_pipeline_callback.queue(
                    callback, 1, message="action skipped")
                return resp_return('SKIP')

            if callback:
                current_app.logger.info(
                    f"get run suite request from webhook, callback is: {callback}")
                if request_args.get("sync", True) is False:
                    common_pipeline_callback.queue(
                        callback, 1, message="action has been taken")

                webhook_parser.queue(
                    user, request_body, callback, request_args["threshold"], timeout=24.5 * 60 * 60, result_ttl=24 * 60 * 60)

                return resp_return('EXECUTE_OK')

            else:
                errors, status_code, extra = self.post_check(
                    request_body)
                current_app.logger.info(
                    f"""errors: {errors}
                    status_code: {status_code}
                    extra: {extra}""")

                if errors:
                    return resp_return('COMMON_ERROR', new_msg='\n'.join(errors))

                error, ret = self.run(user, status_code, extra, request_body)
                if error:
                    return resp_return('COMMON_ERROR', new_msg=error)
                else:
                    return resp_return('EXECUTE_OK', append=ret)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class LogsClearView(BaseResource):
    def get(self, month):
        try:
            clean_logs.queue(days=month * 30, timeout=24 * 60 * 60)
            return resp_return('EXECUTE_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SuiteRerunView(BaseResource):
    decorators = [limiter.limit(
        config.SUITE_LIMIT_PATTERN, key_func=limiter_by_path)]

    def post(self, id):
        try:
            suite_result = SuiteResult.query.get(id)
            if not suite_result:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding suite result found!")

            data = suite_result.extra.get('exec_data', {})
            if not data:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding configuration found!")

            user = request.headers.get('email')
            if not user:
                current_app.logger.error(
                    f"some gays want to run suite: {id} without login!")
                return resp_return('NO_LOGIN')

            case_suite = Casesuite.query.get(suite_result.casesuite_id)
            if not case_suite:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding case suite found!")

            data['author'] = user
            error = ExecMgr.run_suite_v2(suite_id=case_suite.id, data=data)
            if error:
                return resp_return('COMMON_ERROR', new_msg=error)
            else:
                return resp_return('EXECUTE_OK')
        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg={str(err)})


class CaseRerunView(BaseResource):
    decorators = [limiter.limit(
        config.CASE_LIMIT_PATTERN, key_func=limiter_by_path)]

    def post(self, id):
        try:
            case_result = CaseResult.query.get(id)
            if not case_result:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding case result found!")

            suiteresult_id = case_result.suiteresult_id
            suite_result = SuiteResult.query.get(
                suiteresult_id) if suiteresult_id else None
            if suite_result:
                data = suite_result.extra.get('exec_data', {})
            else:
                data = case_result.details[0].get('exec_data', {})

            if not data:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding configuration found!")

            user = request.headers.get('email')
            if not user:
                current_app.logger.error(
                    f"some gays want to run suite: {id} without login!")
                return resp_return('NO_LOGIN')

            data['author'] = user
            errmsg = ExecMgr.run_case_v2(
                case_instance=case_result.case, data=data)

            if not errmsg:
                return resp_return('EXECUTE_OK')
            else:
                return resp_return('RUN_ERROR', new_msg=errmsg)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg={str(err)})


class SuiteRetryView(BaseResource):
    decorators = [limiter.limit(
        config.SUITERETRY_LIMIT_PATTERN, key_func=limiter_by_path)]

    def post(self, id):
        try:
            suite_result = SuiteResult.query.get(id)
            if not suite_result:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding suite result found!")

            exec_data = suite_result.extra.get('exec_data', {})
            if not exec_data:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding configuration found!")

            user = request.headers.get('email')
            if not user:
                current_app.logger.error(
                    f"some gays want to run suite: {id} without login!")
                return resp_return('NO_LOGIN')

            case_suite = Casesuite.query.get(suite_result.casesuite_id)
            if not case_suite:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding case suite found!")

            json_data = request.get_json()
            retry_cases = json_data.get("retry_cases", [])
            exec_data['author'] = user
            error = ExecMgr.run_suite_v2(
                suite_id=case_suite.id, data=exec_data, suiteresult_id=id, retry=True, retry_cases=retry_cases)
            if error:
                return resp_return('COMMON_ERROR', new_msg=error)
            else:
                return resp_return('EXECUTE_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg={str(err)})


class ManualPlanView(BaseResource):
    def post(self, id):
        try:
            json_data = request.get_json()
            user = request.headers.get('email')
            if not user:
                current_app.logger.error(
                    f"some gays want to run suite: {id} without login!")
                return resp_return('NO_LOGIN')

            case_suite = Casesuite.query.get(id)
            if case_suite:
                json_data['author'] = user
                suite_result = SuiteResult(**{
                    "runner": user,
                    "author": case_suite.author,
                    "casesuite_name": case_suite.name,
                    "project_name": case_suite.project.name,
                    "env_name": json_data.get("api", {}).get("env", {}).get("name", "test-env"),
                    "total": 0,
                    "casesuite_id": id,
                    "status": "pending",
                    "extra": {"exec_data": json_data},
                    "debug_mode": True
                })
                suite_result.save()
                ExecMgr.run_manual_plan(suite_result.id, json_data)

                return resp_return('EXECUTE_OK', suite_result.id)

            else:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding casesuite found!")

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, id):
        try:
            suite_result = SuiteResult.query.get(id)
            if not suite_result:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding suite result found!")

            user = request.headers.get('email')
            if not user or user != suite_result.runner:
                return resp_return('UPDATE_NOT_ALLOW', new_msg='You do not have permission to finish the suite result.')

            suite_result.status = 'done'
            suite_result.save()
            goc_profile.queue(id, timeout=30 * 60, result_ttl=24 * 60 * 60)

            return resp_return('EXECUTE_OK', new_msg="Coverage data being acquired.")

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


@myrq.job('callback')
def webhook_parser(user, request_body, callback, threshold):

    # 'https://space.shopee.io/apis/pipeline_ci/openapi/trigger/shopee-marketplace_core-promotion-qa-internal_platforms-ws__38550/build/31288/job/179398/plugin/75115'
    runtime_args = Pipeline.pipeline_query(callback)
    if not runtime_args:
        return Pipeline.pipeline_callback(callback, 2, errors="pipeline query field")

    # args replace
    request_body = parser(request_body, runtime_args)

    errors, status_code, extra = SuiteRunForWebhooksView.post_check(
        request_body)
    current_app.logger.info(
        f"""errors: {errors}
        status_code: {status_code}
        extra: {extra}""")

    if errors:
        return Pipeline.pipeline_callback(callback, 2, errors=errors)

    if status_code in [0, ]:  # run suite directly
        suite_obj = extra[0]
        runtime_config = copy.deepcopy(suite_obj.runtime_config)
        runtime_config = SuiteRunForWebhooksView.merge_runtime_config(
            runtime_config, extra[1])
        current_app.logger.info(
            f"suite_obj: {suite_obj}, runtime_config: {runtime_config}")
        ret = run_suite(
            suite_obj, SuiteRunForWebhooksView.get_data(user, runtime_config))

    # need pull the project 1st, then create a suite automately
    elif status_code in [1, ]:
        project_info = {
            "name": request_body["project"]['name'],
            "description": "webhook auto created",
            "author": user,
            "extra": {
                "executors": {
                    extra[3]: request_body["project"]['repo'][extra[3]]
                }
            },
            ""
            "public_project": False,
            "feature_id": extra[2].id
        }
        project = ProjectsView.create_project(project_info)
        # pull
        ok, _ = git_core(project.id, user)
        if not ok:
            error = "import case error"
            current_app.logger.error(error)
            return Pipeline.pipeline_callback(callback, 2, errors=error)
        else:
            if SuiteRunForWebhooksView.wait_import(project.id) is False:
                return Pipeline.pipeline_callback(callback, 2, errors="import case not finish")

        # create suite
        suite_obj = SuiteRunForWebhooksView.create_suite(
            user, request_body, project)

        # run
        ret = run_suite(suite_obj, data=SuiteRunForWebhooksView.get_data(
            user, suite_obj.runtime_config))

    elif status_code in [2, ]:  # the project already exist, but no suite
        # pull
        ok, _ = git_core(extra[0].id, user)
        if not ok:
            error = "import case error"
            current_app.logger.error(error)
            return Pipeline.pipeline_callback(callback, 2, errors=errors)
        else:
            if SuiteRunForWebhooksView.wait_import(extra[0].id) is False:
                current_app.logger.error("import case not finish")
                return Pipeline.pipeline_callback(callback, 2, errors="import case not finish")

        # create suite
        current_app.logger.info(f"to create suite for {extra[0]}")
        suite_obj = SuiteRunForWebhooksView.create_suite(
            user, request_body, extra[0])
        # run
        current_app.logger.info(f"to run suite: {suite_obj.name}")
        ret = run_suite(suite_obj, data=SuiteRunForWebhooksView.get_data(
            user, suite_obj.runtime_config))

    elif status_code in [3, ]:  # run suite directly
        suite_obj = extra[0]
        ret = run_suite(suite_obj, SuiteRunForWebhooksView.get_data(
            user, suite_obj.runtime_config))

    else:
        return Pipeline.pipeline_callback(callback, 2, errors='request body error')

    try:
        suite_result_id = ret.get('suite_result_id')
        suiteresult = SuiteResult.query.get(suite_result_id)
        extra = {
            "sulte_name": suiteresult.casesuite_name,
            "sulte_id": suiteresult.casesuite_id,
            "sulte_status": suiteresult.status,
            "total_cases": suiteresult.total,
            "success_rate": suiteresult.success_rate,
            "suite_result_link": f"{current_app.config['FE_SUITERESULT']}{suite_result_id}"
        }
        current_app.logger.warn(
            f"""pipeline done for suite {suiteresult.casesuite_id}
                callback: {callback}
                request_body: {request_body}
                extra: {extra}""")
        return Pipeline.pipeline_callback(callback, 1 if suiteresult.success_rate >= threshold else 2, **extra)
    except Exception as err:
        return Pipeline.pipeline_callback(callback, 2, errors=str(err))


def run_suite(suite_obj, data):
    '''
    ret = {
        "result_id": 123,
        "error": ""
    }'''

    result_hd = MyRedis(current_app.config['URL_FOR_RESULT'])
    record_id = int(datetime.now().timestamp()) + suite_obj.id * 1000

    _run_suite_v2(suite_obj.id, data, record_id)
    return utils.get_result_id(result_hd, record_id, timeout=10)
