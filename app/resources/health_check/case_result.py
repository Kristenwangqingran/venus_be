# -*- coding: utf-8 -*-
# @Time    : 2022/9/13
# @Author  : Jiaxin Chen


import traceback
from app.resources import BaseResource
from flask import request, current_app
from app.commons import resp_return, ma
from app.models import HcCaseResult
from app.models import HcPlanResult, hc_plan_result_schema, HcPlan


class HcCaseResultsRequestArgs(ma.Schema):
    plan_result_id = ma.Integer(default=0)
    case_type = ma.String(default='')


class HcCaseResultsView(BaseResource):
    def get(self, ):
        try:
            try:
                query_args = HcCaseResultsRequestArgs().dump(request.args)
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            if query_args['plan_result_id'] == 0 or query_args['case_type'] == '':
                return resp_return('PARAM_INVALID', new_msg=f'param is not right')

            case_status = ['pass', 'fail', 'error']
            ret = {
                "total_num": 0,
                "pass_num": 0,
                "fail_num": 0,
                "error_num": 0,
                "cases": {
                    "fail": [],
                    "error": [],
                    "pass": []
                }
            }
            query = HcCaseResult.query.filter(HcCaseResult.plan_result_id == query_args['plan_result_id'],
                                              HcCaseResult.status.in_(
                                                  case_status),
                                              HcCaseResult.deleted == False)
            if query_args['case_type'] == 'All':
                results = query.all()

            else:
                case_type = query_args['case_type'].replace('_', " ")
                results = query.filter_by(case_type=case_type).all()

            for result in results:
                ret['cases'][result.status.lower()].append({
                    "id": result.case.id,
                    "case_result_id": result.id,
                    "case_name": result.case.name
                })
            for s in case_status:
                ret[f'{s}_num'] = len(ret['cases'][s])
                ret['total_num'] += ret[f'{s}_num']

            return resp_return('QUERY_SUCCESS', ret)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HcCaseResultView(BaseResource):
    def get(self, case_result_id):
        try:
            case_result = HcCaseResult.query.get(case_result_id)
            plan_result = HcPlanResult.query.get(case_result.plan_result_id)
            api_type = case_result.case.api_type

            result_json = {}
            if case_result:
                result_json["case_detail"] = {
                    "api_id": case_result.case.api.id if api_type == 'spex' else case_result.case.http_api.id,
                    "case_id": case_result.case.id,
                    "template_id": case_result.case.template_id,
                    "api_type": api_type,
                    "topic": plan_result.plan.topic if api_type == 'spex' else plan_result.http_plan.topic,
                    "service_name": plan_result.plan.service.name if api_type == 'spex' else "",
                    "project_id": plan_result.http_plan.http_project_id if api_type == 'http' else 0,
                    "api_id": case_result.case.api.id,
                    "api_name": case_result.case.api.name if api_type == 'spex' else case_result.case.http_api.name,
                    "case_name": case_result.case.name,
                    "status": case_result.status,
                    "request": case_result.case.request,
                    "actual_response": case_result.response,
                    "actual_errCode": case_result.error_code,
                    "expect_response": case_result.case.expect_response,
                    "expect_errCode": case_result.case.expect_errcode,
                    "fixed": case_result.fixed if case_result.fixed in (True, False) else False
                }
            return resp_return('QUERY_SUCCESS', result_json)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, case_result_id):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            case_result = HcCaseResult.query.get(case_result_id)
            case_result.put_save(json_data)
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
