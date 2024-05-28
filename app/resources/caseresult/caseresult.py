# -*- coding: utf-8 -*-
# @Time    : 2020/8/24
# @Author  : GongXun
from flask import request, current_app
from app.commons import ma, resp_return
import app.commons.utils as utils
from app.resources import BaseResource
from sqlalchemy import String
import datetime
from app.models import CaseResult, caseresult_schema, caseresults_schema, Case, SuiteResult, Project, Env, \
    TaskStatus_DONE, Group
import sqlalchemy
from app.models import CaseResult, caseresult_schema, Case, SuiteResult, Project, \
    Env, TaskStatus_DONE, Group
import datetime
from app.models import CASE_UNPASS_REASON


class TheRequestArgs(ma.Schema):
    suiteresult_id = ma.Integer(required=True)
    status = ma.String()
    author = ma.String()
    group_name = ma.String()
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=10)


class TheCaseResultsView(BaseResource):
    def get(self, ):
        try:
            query_args = TheRequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        param = self.get_common_params(query_args, CaseResult)
        query = CaseResult.query.filter(*param)

        caseresults = query.order_by(CaseResult.updated_time.desc()).paginate(
            page=query_args["page"], per_page=query_args["per_page"], error_out=False)
        result_list = caseresults_schema.dump(caseresults.items, many=True)

        return resp_return('QUERY_SUCCESS', result_list, caseresults.total)


class RequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    case_id = ma.Integer()
    case_name = ma.String()
    reason = ma.String()
    status = ma.String()
    project_id = ma.Integer()
    suiteresult_id = ma.Integer()
    organized = ma.String()
    author = ma.String()
    runner = ma.String()
    group_name = ma.String()
    order_by = ma.String()
    recent = ma.Integer(default=1)
    api = ma.String()


class CaseResultsView(BaseResource):

    def get_common_params(self, args, classobj):
        params = [getattr(classobj, 'deleted') == False]
        for key, value in args.items():
            if (value or isinstance(value, bool) or (isinstance(value, int) and value == 0)) and key not in {'page',
                                                                                                             'per_page'}:
                if key in {'author', 'case_name', 'group_name'}:
                    params.append(
                        getattr(classobj, key).ilike("%" + value + "%"))
                else:
                    params.append(getattr(classobj, key) == value)
        return params

    def get(self, ):
        try:
            query_args = RequestArgs().dump(request.args)
            project_id = query_args.pop('project_id', None)
            product_line_id = query_args.pop('product_line_id', None)
            organized = query_args.pop("organized", None)
            suiteresult_id = query_args.get('suiteresult_id', None)
            order_by = query_args.pop('order_by', None)
            case_id = query_args.pop("case_id", None)
            recent = query_args.pop("recent", None)
            api = query_args.pop('api', '')

        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        if not case_id and not project_id and not suiteresult_id:
            return resp_return('QUERY_SUCCESS', [], 0)

        param = self.get_common_params(query_args, CaseResult)
        query = CaseResult.query.filter(*param)
        now = datetime.datetime.now()
        delta = datetime.timedelta(days=recent*30)
        time_line = (now-delta).strftime("%Y-%m-%d")

        if product_line_id and organized:
            # TODO 这里跟product_line相关的统计代码需要重写
            return resp_return('NOFOUND_ERROR', new_msg="TODO。team表废除，跟product_line相关的统计代码暂未实现。")

        elif case_id:
            query = query.filter(CaseResult.case_id ==
                                 case_id, CaseResult.updated_time > time_line)

        elif project_id:
            query = query.join(Case, CaseResult.case_id == Case.id).filter(
                Case.project_id == project_id, CaseResult.updated_time > time_line)

        elif product_line_id:
            query = query.join(Case, CaseResult.case_id == Case.id).join(
                Project, Case.project_id == Project.id).filter(Project.product_line_id == product_line_id)

        order_by_list = []
        if order_by:
            for i in order_by.split(','):
                order_by_list.append(getattr(CaseResult, i).desc())
        else:
            order_by_list.append(CaseResult.updated_time.desc())

        if suiteresult_id:
            # Collapsed retry case results
            suite_result_instance = SuiteResult.query.get(suiteresult_id)
            cases_results = suite_result_instance.extra.get("cases", {})
            if not cases_results:
                return resp_return('QUERY_SUCCESS', [], 0)
            valid_result = []
            for i in cases_results.values():
                if i:
                    valid_result.append(i[-1])
            query = query.filter(CaseResult.id.in_(valid_result))

            if api:
                query = query.join(Case, CaseResult.case_id == Case.id).filter(
                    Case.apis.contains([api]))

            caseresults = query.order_by(*order_by_list).paginate(
                page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            result = caseresults_schema.dump(caseresults.items, many=True)

            results = []
            for case_result in result:
                history_results = suite_result_instance.extra.get(
                    "cases", {}).get(str(case_result["case_id"]), [0])

                history = []

                if not suite_result_instance.extra.get("muti_param", False) and len(history_results) > 1:
                    for history_result_id in history_results[-2::-1]:
                        history_result = caseresult_schema.dump(
                            CaseResult.query.get(history_result_id))
                        history.append({
                            "id": history_result['id'],
                            "case_name": history_result['case_name'],
                            "author": history_result['author'],
                            "reason": history_result['reason'],
                            "duration": history_result['duration'],
                            "status": history_result['status'],
                            "log": history_result['details'][0].get("log", "") if history_result['details'] else "",
                            "html_file": history_result['details'][0].get("html_file", "") if history_result[
                                'details'] else "",
                            "updated_time": history_result['updated_time']
                        })
                case_result['children'] = history
                results.append(case_result)
            return resp_return('QUERY_SUCCESS', results, caseresults.total)

        else:
            caseresults = query.order_by(*order_by_list).limit(query_args["per_page"]).offset(
                (query_args["page"] - 1) * query_args["per_page"]
            ).all()
            result = caseresults_schema.dump(caseresults, many=True)

        return resp_return('QUERY_SUCCESS', result, len(result))

    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        if not json_data:
            return resp_return('JSON_ERROR')

        try:
            t1 = datetime.datetime.now()
            if 'env_id' in json_data:
                case = Case.query.get(json_data['case_id'])
                env = Env.query.get(json_data['env_id'])

                caseresult_info = {
                    "author": request.headers.get('email', 'no-user'),
                    "status": "running",
                    "env_name": env.name,
                    "case_id": case.id,
                    "details": [{}]
                }
            else:
                caseresult_info = json_data

            CaseResult.post_check(caseresult_info)
            caseresult = caseresult_schema.load(
                utils.del_id_none(caseresult_info))
            caseresult.save()
            t2 = datetime.datetime.now()
            current_app.logger.info(f"[{caseresult.id}]post use : {t2 - t1}")

        except Exception as err:
            return resp_return('COMMON_ERROR', new_msg=str(err))
        else:
            return resp_return('CREATE_SUCCESS',
                               append={"id": caseresult.id, "logpath": caseresult.get_absolute_logdir()})


class CaseResultView(BaseResource):
    def get(self, id):

        caseresult = CaseResult.query.filter_by(id=id).first()
        if caseresult:
            result = caseresult_schema.dump(caseresult)
            return resp_return('QUERY_SUCCESS', result)
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding caseresult found!")

    def put(self, id):
        json_data = request.get_json()
        if not json_data:
            return resp_return('JSON_ERROR')

        caseresult = CaseResult.query.filter_by(id=id).first()
        if caseresult:
            try:
                if caseresult.status in TaskStatus_DONE:
                    json_data.pop('status')

                if json_data.get('details', []):
                    json_data['details'][0]['exec_data'] = caseresult.details[0].get(
                        'exec_data', {})
                self.common_put_for_caseresult(caseresult, json_data)

            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('UPDATE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding caseresult found!")

    def delete(self, id):
        caseresult = CaseResult.query.filter_by(id=id).first()
        if caseresult:
            try:
                caseresult.rdelete()
            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding caseresult found!")


class CaseReasonsView(BaseResource):
    def get(self, ):
        try:
            return resp_return("QUERY_SUCCESS", CASE_UNPASS_REASON)
        except Exception as err:
            return resp_return('COMMON_ERROR', new_msg=str(err))


class CaseReasonView(BaseResource):
    def put(self, ):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            reasons = json_data.get("reason", {})
            err = ''
            for reason, result_id_list in reasons.items():
                for case_result_id in result_id_list:
                    case_result = CaseResult.query.filter_by(
                        id=case_result_id).first()
                    if case_result:
                        case_result.reason = reason
                        case_result.save()
                    else:
                        err += f'Not found case result[id: {case_result_id}] \n'

            if not err:
                return resp_return('UPDATE_SUCCESS')
            else:
                return resp_return('NOFOUND_ERROR', new_msg=err)

        except Exception as err:
            return resp_return('COMMON_ERROR', new_msg=str(err))


class CaseNameSuiteNameView(BaseResource):
    def get(self):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        project_id = query_args.get('project_id', None)
        if not project_id:
            return resp_return('QUERY_SUCCESS', {})

        case_results = CaseResult.query.join(Case, CaseResult.case_id == Case.id).filter(
            Case.project_id == project_id).all()
        result = {'case_names': [], 'suite_names': []}
        for case_result in case_results:
            if case_result.case_name and case_result.case_name not in result['case_names']:
                result['case_names'].append(case_result.case_name)
            if case_result.suiteresult and case_result.suiteresult.casesuite_name not in result['suite_names']:
                result['suite_names'].append(
                    case_result.suiteresult.casesuite_name)

        return resp_return('QUERY_SUCCESS', result)


class CaseHTMLView(BaseResource):

    def get(self, id):
        caseresult = CaseResult.query.filter_by(id=id).first()
        if caseresult:
            html = None
            if caseresult.details and isinstance(caseresult.details, list) and caseresult.details[0].get('html_file'):
                return resp_return('QUERY_SUCCESS', {"html_file": caseresult.details[0]['html_file']})
            else:
                return resp_return('QUERY_SUCCESS', new_msg="no html found!")

        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding caseresult found!")


class CaseDeviceView(BaseResource):

    def get(self, id):
        caseresult = CaseResult.query.filter_by(id=id).first()
        if caseresult:
            result = {
                "worker": caseresult.worker,
                "runtime_args": None
            }
            if caseresult.details and isinstance(caseresult.details, list) and caseresult.details[0].get('html_file'):
                result['runtime_args'] = caseresult.details[0].get('exec_data')
            return resp_return('QUERY_SUCCESS', result)
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding caseresult found!")


class CaseItemResultView(BaseResource):
    def get(self, case_result_id):
        case_result = CaseResult.query.filter_by(id=case_result_id).first()
        if case_result:
            return resp_return('QUERY_SUCCESS', case_result.item_results)
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding caseresult found!")
