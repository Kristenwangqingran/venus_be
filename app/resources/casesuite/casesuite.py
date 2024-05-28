# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : XunGong
import calendar
import copy
import datetime
import json
import random
import traceback

from flask import request, current_app
from sqlalchemy.orm.attributes import flag_modified

import app.commons.utils as utils
from app.commons import aps
from app.commons import ma, resp_return
from app.libs import ExecUtils
from app.models import Casesuite, casesuite_schema, Case, simplecase_schema, Env, Group, Project
from app.resources import BaseResource
from app.tasks import modify_notification


class RequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    name = ma.String()
    project_id = ma.Integer()
    author = ma.String()
    is_manual = ma.Boolean(default=False)


class CasesuitesView(BaseResource):
    def get(self, ):
        try:
            query_args = RequestArgs().dump(request.args)
            is_manual = query_args.pop('is_manual')
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        param = self.get_common_params(query_args, Casesuite)
        if is_manual:
            query = Casesuite.query.filter(*param, Casesuite.is_manual == True)
        else:
            query = Casesuite.query.filter(
                *param, (Casesuite.is_manual == None) | (Casesuite.is_manual == False))
        suites = query.order_by(Casesuite.updated_time.desc()).paginate(
            page=query_args["page"], per_page=query_args["per_page"], error_out=False)

        results = casesuite_schema.dump(suites.items, many=True)
        for result in results:
            result['job'] = aps.MYASP.get_job(str(result['id']))
        return resp_return('QUERY_SUCCESS', results, suites.total)

    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        if not json_data:
            return resp_return('JSON_ERROR')

        try:
            Casesuite.post_check(json_data)
            json_data['author'] = request.headers.get('email', 'no-user')
            casesuite = casesuite_schema.load(utils.del_id_none(json_data))
            casesuite.save()

            # start schedule
            if casesuite.schedule and casesuite.schedule.get('status', "disabled") == "enabled":
                task_dict = casesuite.schedule['time_info']
                kwargs = {
                    "suite_id": casesuite.id,
                    "data": {
                        "author": request.headers.get('email', 'no-user'),
                        "code_coverage": casesuite.runtime_config.get("code_coverage", {}),
                        "official_mobile": casesuite.runtime_config.get("official_mobile", {}),
                        "official_web": casesuite.runtime_config.get("official_web", {}),
                        "api": casesuite.runtime_config.get("api", {}),
                        "common": casesuite.runtime_config.get("common", {})
                    }
                }

                aps.MYASP.add_task(
                    task_id=str(casesuite.id), task_name='run_suite', trigger=casesuite.schedule['trigger'],
                    kwargs=kwargs, task_dict=task_dict)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
        else:
            return resp_return('CREATE_SUCCESS', casesuite.id)


class CasesuiteView(BaseResource):

    def __find_case_form_list_by_id(self, cases, case_id):
        for i, case in enumerate(cases):
            if case['id'] == case_id:
                cases.pop(i)
                return case, case_id
        return None, case_id

    def get(self, id):
        casesuite = Casesuite.query.filter_by(id=id).first()
        if casesuite:
            result = casesuite_schema.dump(casesuite)
            if casesuite.case_id_list:
                cases = Case.query.filter(Case.id.in_(
                    casesuite.case_id_list), Case.deleted == False).all()
                cases = simplecase_schema.dump(cases, many=True)

                # empty_pz = []
                # case_id_list = casesuite.case_id_list
                # for i, case_id in enumerate(case_id_list):
                #     cases = Case.query.filter(
                #         Case.id == case_id, Case.deleted == False).all()
                #     if cases:
                #         result["cases"].append(case_schema.dump(cases[0]))
                #         # result["cases"].append(cases[0].name)
                #     else:
                #         empty_pz.append(i)
                real_id_list = []
                for case_id in casesuite.case_id_list:
                    if not cases:
                        break
                    case, _id = self.__find_case_form_list_by_id(
                        cases, case_id)
                    if case:
                        real_id_list.append(_id)

                result["case_id_list"] = real_id_list
                # casesuite.case_id_list = real_id_list
                # casesuite.save()

            # if result['schedule'] and result['schedule'].get('env_id', None):
            #     env = Env.query.filter_by(id=result['schedule']['env_id']).all()
            #     result['schedule']['env_name'] = env[0].name if env else ''

            result['job'] = aps.MYASP.get_job(str(casesuite.id))
            return resp_return('QUERY_SUCCESS', result)
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding casesuite found!")

    def put(self, id):
        json_data = request.get_json()
        if not json_data:
            return resp_return('JSON_ERROR')

        casesuite = Casesuite.query.filter_by(id=id).first()
        if casesuite:
            try:
                user = request.headers.get('email') if not json_data.get(
                    "admin") else casesuite.author
                pre_author = casesuite.author
                if casesuite.author != user:
                    json_data['author'] = user
                # Sync case id list and sequence/dependency info
                if 'case_id_list' in json_data:
                    plan = casesuite.plan if 'plan' not in json_data else json_data['plan']
                    pre_case_list = casesuite.case_id_list
                    for case_id in pre_case_list:
                        if case_id not in json_data['case_id_list']:
                            if str(case_id) in plan.get('dependency', {}):
                                plan['dependency'].pop(str(case_id))
                            if str(case_id) in plan.get('sequence', {}):
                                plan['sequence'].pop(str(case_id))
                    json_data['plan'] = plan
                    flag_modified(casesuite, 'plan')

                if 'run_all_config' in json_data:
                    if not json_data['run_all_config'].get('cross_project', False):
                        temp_list = [casesuite.project_id]
                        projects = Project.query.filter(
                            Project.public_project == True, Project.deleted == False).all()
                        for project in projects:
                            temp_list.append(project.id)
                        group_list = []
                        for project_id in temp_list:
                            groups = Group.query.filter(Group.project_id == project_id,
                                                        Group.deleted == False).order_by(Group.updated_time.desc()).all()
                            for group in groups:
                                group_list.append(group.id)
                        temp_list.extend(group_list)
                        for run_all in json_data['run_all_config'].get('run_all', []):
                            if run_all.get('id', -1) not in temp_list:
                                json_data['run_all_config']['run_all'].remove(
                                    run_all)

                self.common_put(casesuite, json_data)

                if casesuite.schedule and casesuite.schedule.get('status', "") == "enabled":
                    task_dict = casesuite.schedule['time_info']
                    kwargs = {
                        "suite_id": id,
                        "data": {
                            "author": request.headers.get('email', 'no-user'),
                            "code_coverage": casesuite.runtime_config.get("code_coverage", {}),
                            "official_mobile": casesuite.runtime_config.get("official_mobile", {}),
                            "official_web": casesuite.runtime_config.get("official_web", {}),
                            "api": casesuite.runtime_config.get("api", {}),
                            "common": casesuite.runtime_config.get("common", {})
                        }
                    }
                    aps.MYASP.modify_task(
                        task_id=str(casesuite.id), task_name='run_suite', trigger=casesuite.schedule['trigger'],
                        kwargs=kwargs, task_dict=task_dict)

                elif casesuite.schedule and casesuite.schedule.get('status', "") == "disabled":
                    try:
                        aps.MYASP.remove_task(task_id=str(casesuite.id))
                    except Exception:
                        current_app.logger.error(traceback.format_exc())
                        pass

                if pre_author != user:
                    modify_notification.queue(casesuite.name, user, pre_author)
                return resp_return('UPDATE_SUCCESS')

            except Exception as err:
                current_app.logger.error(traceback.format_exc())
                return resp_return('DB_ERROR', new_msg=str(err))

        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding casesuite found!")

    def delete(self, id):
        casesuite = Casesuite.query.filter_by(id=id).first()
        if casesuite:
            try:

                casesuite.delete()

                if casesuite.schedule:
                    try:
                        aps.MYASP.remove_task(task_id=str(casesuite.id))
                    except Exception:
                        current_app.logger.error(traceback.format_exc())
                        pass

            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding casesuite found!")


class CasesuitePageView(BaseResource):
    def get(self, id):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')
        casesuite = Casesuite.query.filter_by(id=id).first()
        if casesuite:
            result = {}
            cases_list = []
            count = 0
            if casesuite.case_id_list:
                page = int(query_args.get("page", 1))
                per_page = int(query_args.get("per_page", 20))
                start = (page - 1) * per_page
                end = start + per_page
                total = Case.query.filter(Case.id.in_(
                    casesuite.case_id_list)).filter_by(deleted=False)
                count = total.count()
                cases = simplecase_schema.dump(total, many=True)[start:end]

                for case_id in casesuite.case_id_list:
                    if not cases:
                        break
                    for i, case in enumerate(cases):
                        if case['id'] == case_id:
                            cases_list.append(case)
                            cases.pop(i)

            result["cases"] = cases_list
            result["total"] = count

            return resp_return('QUERY_SUCCESS', result)

        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding casesuite found!")


class CasesuiteSetTopView(BaseResource):
    def put(self, id):
        json_data = request.get_json()
        if not json_data:
            return resp_return('JSON_ERROR')

        casesuite = Casesuite.query.filter_by(id=id).first()
        if casesuite:
            try:
                top_case_id = json_data['case_id']
                case_id_list = casesuite.case_id_list
                case_id_list.remove(top_case_id)
                case_id_list.insert(0, top_case_id)
                casesuite.case_id_list = case_id_list
                flag_modified(casesuite, "case_id_list")
                casesuite.save()
                return resp_return('UPDATE_SUCCESS')

            except Exception as err:
                current_app.logger.error(traceback.format_exc())
                return resp_return('DB_ERROR', new_msg=str(err))

        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding casesuite found!")


class EditCaseExecDepView(BaseResource):
    def get(self):
        args = request.args.to_dict()
        if args is None:
            return resp_return('JSON_ERROR')

        try:
            cases, result = [], []
            suite_id = args.get('suite_id', None)
            if suite_id:
                suite_id = int(suite_id)
            case_ids = args.get('case_ids', None)
            if case_ids:
                case_ids = [int(case_id) for case_id in case_ids.split(',')]

            # case的input和output参数
            if case_ids:
                cases = Case.query.filter(Case.id.in_(
                    case_ids), Case.deleted == False).all()
            elif suite_id:
                casesuite = Casesuite.query.filter_by(id=suite_id).first()
                if casesuite and casesuite.case_id_list:
                    cases = Case.query.filter(Case.id.in_(
                        casesuite.case_id_list), Case.deleted == False).all()

            if not cases:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding data found!")

            cases = simplecase_schema.dump(cases, many=True)
            for case in cases:
                inputs_dict = case['inputs']
                outputs_dict = case['outputs']
                inputs_param = []
                outputs_param = []
                if inputs_dict:
                    if isinstance(inputs_dict, list):
                        for input_dict in inputs_dict:
                            temp_dict = {'name': input_dict['name'],
                                         'description': input_dict.get('description', '')}
                            inputs_param.append(temp_dict)
                    else:
                        for input_key in inputs_dict.keys():
                            inputs_param.append(
                                {'name': input_key, 'description': ''})
                if outputs_dict:
                    if isinstance(outputs_dict, list):
                        for output_dict in outputs_dict:
                            temp_dict = {'name': output_dict['name'],
                                         'description': output_dict.get('description', '')}
                            outputs_param.append(temp_dict)
                    else:
                        for output_key in outputs_dict.keys():
                            outputs_param.append(
                                {'name': output_key, 'description': ''})
                result.append({'case_id': case['id'], 'case_name': case['name'],
                               'inputs': inputs_param, 'outputs': outputs_param})

            return resp_return('QUERY_SUCCESS', result)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('DB_ERROR', new_msg=str(err))


class SuiteCloneView(BaseResource):
    def post(self, id):

        suite = Casesuite.query.filter_by(id=id).first()
        if suite:
            email = request.headers.get(
                'email', '')
            result = casesuite_schema.dump(suite)
            result['author'] = email if email else result['author']
            result.pop('id')
            result['name'] += '-' + str(random.randint(1000, 9999)) + 'copy'
            new_suite = casesuite_schema.load(utils.del_id_none(result))
            new_suite.save()

            if new_suite.schedule and new_suite.schedule.get('status', "disabled") == "enabled":
                task_dict = new_suite.schedule['time_info']
                kwargs = {
                    "suite_id": new_suite.id,
                    "data": {
                        "author": request.headers.get('email', 'no-user'),
                        "code_coverage": new_suite.runtime_config.get("code_coverage", {}),
                        "official_mobile": new_suite.runtime_config.get("official_mobile", {}),
                        "official_web": new_suite.runtime_config.get("official_web", {}),
                        "api": new_suite.runtime_config.get("api", {}),
                        "common": new_suite.runtime_config.get("common", {})
                    }
                }
                aps.MYASP.add_task(
                    task_id=str(new_suite.id), task_name='run_suite', trigger=new_suite.schedule['trigger'],
                    kwargs=kwargs, task_dict=task_dict)

            return resp_return('CLONE_SUCCESS', {'id': new_suite.id})
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding casesuite found!")


class PlanVerifyView(BaseResource):
    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        if not json_data:
            return resp_return('JSON_ERROR')

        try:
            _, _, errors = ExecUtils.parse_plan(json_data)
            if errors:
                return resp_return('JSON_ERROR', new_msg=errors)
            else:
                return resp_return('COMMON_OK')

        except Exception as err:
            return resp_return('JSON_ERROR', new_msg=str(err))


class BGView(BaseResource):

    def get(self, ):
        template = {
            "email": {
                "list": [
                ],
                "status": [
                    "fail",
                    "error",
                    "pass",
                    "timeout",
                    "canceled",
                    "skip"
                ],
                "format": "group",
                "details": {
                    "withlink": True,
                    "is_silence": True
                }
            },
            "seatalk": {
                "list": [
                ],
                "status": [
                    "fail",
                    "error",
                    "pass",
                    "timeout",
                    "canceled",
                    "skip"],
                "format": "group",
                "details": {
                    "withlink": True,
                    "is_silence": True
                }
            },
            "mattermost": {
                "list": [
                ],
                "status": [
                    "fail",
                    "error",
                    "pass",
                    "timeout",
                    "canceled",
                    "skip"],
                "format": "group",
                "details": {
                    "withlink": True,
                    "is_silence": True
                }
            },
            "QABOT": {
                "seatalk": [],
                "mattermost": [],
                "status": [
                    "fail",
                    "error",
                    "pass",
                    "timeout",
                    "canceled"
                ],
                "format": "group",
                "details": {
                    "withlink": True,
                    "is_silence": True
                }
            }
        }

        k_map = {
            "emails": "email",
            "seatalks": 'seatalk',
            "mattermosts": 'mattermost'
        }

        allsuites = Casesuite.query.all()
        for suite in allsuites:
            if suite.description:
                des = getattr(suite, 'description', json.dumps(
                    {})) or json.dumps({})
                try:
                    des = json.loads(des)
                except:
                    des = {}

                if not des or not isinstance(des, dict):
                    current_app.logger.warn(
                        f"fuck suite {suite.id} des: {des}")
                    continue

                noti = copy.deepcopy(template)
                for k, v in des.items():
                    if k not in k_map:
                        continue
                    noti[k_map[k]]["list"].extend(v)
                if not suite.noti:
                    suite.noti = {}
                ori_suite = copy.deepcopy(suite.noti)
                noti.update(ori_suite)
                suite.noti = noti
                suite.save()
        return resp_return('QUERY_SUCCESS')


class CronExpressionToDateTime(BaseResource):
    def get(self):
        args = request.args.to_dict()
        if args is None:
            return resp_return('JSON_ERROR')

        cron = args.get('cron', None)
        if not cron:
            return resp_return('PARAMS_ERR')
        minute, hour, day, month, week = cron.split(' ')
        if (day == '?' and week == '?') or (day != '?' and week != '?'):
            return resp_return('PARAMS_ERR', new_msg='Only allowed one type in day and week')

        year = datetime.datetime.now().year
        result = []

        if month == '*':
            month_list = [i for i in range(1, 13)]
        else:
            month_list = [int(i) for i in month.split(',')]

        if hour == '*':
            hour_list = [str(i) if i > 9 else f'0{i}' for i in range(0, 24)]
        else:
            hour_list = [str(i) if i > 9 else f'0{i}' for i in [
                int(j) for j in hour.split(',')]]

        minute_list = [str(i) if i > 9 else f'0{i}' for i in [
            int(j) for j in minute.split(',')]]

        schedule_time = []
        for h in hour_list:
            for m in minute_list:
                schedule_time.append(f'{h}:{m}:00')

        date_list = []
        for month in month_list:
            if day == '*':
                for i in range(1, calendar.monthrange(year, month)[1] + 1):
                    date = str(year) + str("-%02d" % month) + str("-%02d" % i)
                    date_list.append(date)
            elif day != '?':
                for i in day.split(','):
                    date = str(year) + str("-%02d" %
                                           month) + str("-%02d" % int(i))
                    date_list.append(date)
            elif week != '?':
                if week == '*':
                    weeks = [0, 1, 2, 3, 4, 5, 6]
                else:
                    weeks = [int(i) for i in week.split(',')]
                for i in range(1, calendar.monthrange(year, month)[1] + 1):
                    if datetime.datetime(year, month, i).weekday() in weeks:
                        date = str(year) + str("-%02d" %
                                               month) + str("-%02d" % i)
                        date_list.append(date)

        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for date in date_list:
            if len(result) >= 5:
                break
            for t in schedule_time:
                if len(result) >= 5:
                    break
                if date + ' ' + t > current_time:
                    result.append(date + ' ' + t)

        return resp_return('QUERY_SUCCESS', result)
