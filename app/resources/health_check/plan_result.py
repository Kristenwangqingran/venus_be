# -*- coding: utf-8 -*-
# @Time    : 2022/2/28
# @Author  : Jiaxin Chen

import traceback
from app.resources import BaseResource
from flask import request, current_app
from app.commons import resp_return, ma
from app.models import HcPlanResult, hc_plan_result_schema, HcPlan
from sqlalchemy import desc


class PlanResultsRequestArgs(ma.Schema):
    plan_name = ma.String(default='')
    plan_id = ma.Integer(default=0)
    http_plan_id = ma.Integer(default=0)
    type = ma.String(default='spex')
    runner = ma.String(default='')
    status = ma.String(default='')
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=10)


class HcPlanResultsView(BaseResource):
    def get(self, ):
        try:
            try:
                query_args = PlanResultsRequestArgs().dump(request.args)
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            if query_args["type"] == "http":
                query = HcPlanResult.query.filter_by(
                    api_type="http", deleted=False)
            else:
                query = HcPlanResult.query.filter(
                    (HcPlanResult.api_type == None) | (
                        HcPlanResult.api_type == "spex"),
                    HcPlanResult.deleted == False)

            if query_args['plan_name'] != '' and (query_args['plan_id'] != 0 or query_args['http_plan_id'] != 0):
                return resp_return('PARAM_INVALID', new_msg=f'Cannot specify both id and name')

            if query_args['plan_id'] != 0:
                results = query.filter_by(plan_id=query_args['plan_id'], deleted=False).order_by(
                    desc(HcPlanResult.updated_time)).paginate(
                    page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            elif query_args["http_plan_id"] != 0:
                results = query.filter_by(http_plan_id=query_args['http_plan_id'], deleted=False).order_by(
                    desc(HcPlanResult.updated_time)).paginate(
                    page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            elif query_args['plan_name'] or query_args['runner'] or query_args['status']:
                results = query.filter(
                    HcPlanResult.status.ilike(f'%{query_args["status"]}%'),
                    HcPlanResult.runner.ilike(f'%{query_args["runner"]}%'),
                    HcPlanResult.deleted == False)
                if query_args['plan_name']:
                    plans = HcPlan.query.filter(HcPlan.name.ilike(
                        f'%{query_args["plan_name"]}%')).all()
                    plans_id = [plan.id for plan in plans]

                    results = results.filter(HcPlanResult.plan_id.in_(plans_id),
                                             HcPlanResult.deleted == False)
                results = results.order_by(
                    desc(HcPlanResult.updated_time)).paginate(
                    page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            else:
                results = query.order_by(
                    desc(HcPlanResult.updated_time)).paginate(
                    page=query_args["page"], per_page=query_args["per_page"], error_out=False)

            result = hc_plan_result_schema.dump(results.items, many=True)
            return resp_return('QUERY_SUCCESS', result, results.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HcPlanResultView(BaseResource):
    def put(self, planresult_id):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            plan_result = HcPlanResult.query.get(planresult_id)
            if not plan_result:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding plan result found!")

            plan_result.put_check(json_data)
            plan_result.save()
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HcPlanResultDetailView(BaseResource):
    def get(self, plan_result_id):
        try:
            case_status = ['pass', 'fail', 'error']
            result_json = {
                "total_num": 0,
                "pass_num": 0,
                "fail_num": 0,
                "error_num": 0,
                "categories": {}
            }

            plan_result = HcPlanResult.query.get(plan_result_id)
            result_info = hc_plan_result_schema.dump(plan_result)
            if not plan_result:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding plan result found!")

            for case_result in plan_result.case_results:
                status = case_result.status.lower()
                if status not in case_status:
                    continue

                case_type = case_result.case_type
                if case_type not in result_json['categories']:
                    result_json['categories'][case_type] = {
                        "total_num": 0,
                        "pass_num": 0,
                        "fail_num": 0,
                        "error_num": 0
                    }
                result_json[f'{status}_num'] += 1
                result_json['categories'][case_type][f'{status}_num'] += 1

            for case_type in result_json['categories']:
                for s in case_status:
                    result_json['categories'][case_type]['total_num'] += \
                        result_json['categories'][case_type][f'{s}_num']

            for s in case_status:
                result_json['total_num'] += result_json[f'{s}_num']
            result_all = {}
            result_all.update(result_info)
            result_all.update(result_json)
            return resp_return('QUERY_SUCCESS', result_all)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
