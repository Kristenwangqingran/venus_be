# -*- coding: utf-8 -*-
# @Time    : 2022/2/28
# @Author  : Jiaxin Chen

import traceback
from app.resources import BaseResource
from flask import request, current_app
from app.commons import resp_return, ma
from app.models import HcPlan, hc_plans_schema, hc_plan_detail_schema, \
    HttpPlan, http_plans_schema, http_plan_detail_schema
import app.commons.utils as utils
from sqlalchemy import desc


class PlansRequestArgs(ma.Schema):
    service_id = ma.Integer(default=0)
    plan_name = ma.String(default='')
    author = ma.String(default='')
    type = ma.String(default='spex')
    http_project_id = ma.Integer(default=0)
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=10)


class HcPlansView(BaseResource):
    def get(self, ):
        try:
            try:
                query_args = PlansRequestArgs().dump(request.args)
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            if query_args['type'] == 'spex':
                if query_args['service_id'] != 0:
                    plans = HcPlan.query.filter(
                        HcPlan.service_id == query_args['service_id'],
                        HcPlan.name.ilike(f'%{query_args["plan_name"]}%'),
                        HcPlan.author.ilike(f'%{query_args["author"]}%'),
                        HcPlan.deleted == False).order_by(desc(HcPlan.updated_time)).paginate(
                        page=query_args["page"], per_page=query_args["per_page"], error_out=False)
                else:
                    plans = HcPlan.query.filter(
                        HcPlan.name.ilike(f'%{query_args["plan_name"]}%'),
                        HcPlan.author.ilike(f'%{query_args["author"]}%'),
                        HcPlan.deleted == False).order_by(desc(HcPlan.updated_time)).paginate(
                        page=query_args["page"], per_page=query_args["per_page"], error_out=False)

                result = hc_plans_schema.dump(plans.items, many=True)
            else:
                # http
                if query_args['http_project_id'] != 0:
                    plans = HttpPlan.query.filter(
                        HttpPlan.http_project_id == query_args['http_project_id'],
                        HttpPlan.name.ilike(f'%{query_args["plan_name"]}%'),
                        HttpPlan.author.ilike(f'%{query_args["author"]}%'),
                        HttpPlan.deleted == False).order_by(desc(HttpPlan.updated_time)).paginate(
                        page=query_args["page"], per_page=query_args["per_page"], error_out=False)
                else:
                    plans = HttpPlan.query.filter(
                        HttpPlan.name.ilike(f'%{query_args["plan_name"]}%'),
                        HttpPlan.author.ilike(f'%{query_args["author"]}%'),
                        HttpPlan.deleted == False).order_by(desc(HttpPlan.updated_time)).paginate(
                        page=query_args["page"], per_page=query_args["per_page"], error_out=False)

                result = http_plans_schema.dump(plans.items, many=True)

            return resp_return('QUERY_SUCCESS', result, plans.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class AddSpexPlanView(BaseResource):
    def post(self):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            json_data['author'] = request.headers.get('email', 'no-user')

            HcPlan.post_check(json_data)
            plan = hc_plan_detail_schema.load(utils.del_id_none(json_data))
            plan.save()
            return resp_return('CREATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class AddHttpPlanView(BaseResource):
    def post(self):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            json_data['author'] = request.headers.get('email', 'no-user')

            HttpPlan.post_check(json_data)
            plan = http_plan_detail_schema.load(utils.del_id_none(json_data))
            plan.save()
            return resp_return('CREATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexPlanView(BaseResource):
    def get(self, plan_id):
        try:
            plan = HcPlan.query.get(plan_id)
            if not plan:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding plan found!")

            info = hc_plan_detail_schema.dump(plan)
            return resp_return('QUERY_SUCCESS', info)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, plan_id):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            plan = HcPlan.query.get(plan_id)
            if not plan:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding plan found!")

            plan.put_check(json_data)
            plan.save()
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self, plan_id):
        try:
            plan = HcPlan.query.get(plan_id)
            if not plan:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding plan found!")

            plan.delete()
            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpPlanView(BaseResource):
    def get(self, plan_id):
        try:
            plan = HttpPlan.query.get(plan_id)
            if not plan:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding plan found!")

            info = http_plan_detail_schema.dump(plan)
            return resp_return('QUERY_SUCCESS', info)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, plan_id):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            plan = HttpPlan.query.get(plan_id)
            if not plan:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding plan found!")

            plan.put_check(json_data)
            plan.save()
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self, plan_id):
        try:
            plan = HttpPlan.query.get(plan_id)
            if not plan:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding plan found!")

            plan.delete()
            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexConfigView(BaseResource):
    def get(self, ):
        data = {
            "service_name": 'app.tcp_server',
            "config_key": '9d167d37d80016fb4f16f7acaec7cc0ea3bcb92d20694eb6c9bc5771ff2cbc48'
        }
        return resp_return('QUERY_SUCCESS', data)
