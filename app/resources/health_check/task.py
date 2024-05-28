# -*- coding: utf-8 -*-
# @Time    : 2022/2/28
# @Author  : Jiaxin Chen

import traceback
from app.resources import BaseResource
from flask import request, current_app
from app.commons import resp_return, ma
from app.libs import health_check, health_check_rerun, spex_auto_check, spex_batch_auto_check, \
    http_auto_check, http_batch_auto_check
from app.models import SpexApi, SpexService, HttpApi, HttpProject


class HcRunView(BaseResource):
    def post(self, plan_id):
        try:
            json_data = request.get_json()
            data = {
                "runner": request.headers.get('email', 'no-user'),
                "env": json_data.get("routing", {}).get("env", "test"),
                "region": json_data.get("routing", {}).get("region", ""),
                "routing_cid": json_data.get("routing", {}).get("routing_cid", ""),
                "pfb": json_data.get("routing", {}).get("pfb", ""),
            }
            health_check.queue(plan_id, data, token=request.headers.get('token'),
                               api_type=json_data.get("api_type", "spex"),
                               timeout=1 * 60 * 60, result_ttl=24 * 60 * 60)
            return resp_return('EXECUTE_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HcRerunView(BaseResource):
    def post(self, plan_id):
        try:
            try:
                json_data = request.get_json()
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            data = {
                "runner": request.headers.get('email', 'no-user'),
            }
            health_check_rerun.queue(plan_id, data, json_data.get("plan_result_id", 0),
                                     token=request.headers.get('token'),
                                     api_type=json_data.get(
                                         "api_type", "spex"),
                                     timeout=1 * 60 * 60, result_ttl=24 * 60 * 60)
            return resp_return('EXECUTE_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexAutoCheckView(BaseResource):
    def post(self, api_id):
        try:
            json_data = request.get_json()
            api = SpexApi.query.get(api_id)
            if not api:
                return resp_return('NOFOUND_ERROR', new_msg='not found api!')

            if not api.templates:
                return resp_return('NOFOUND_ERROR', new_msg='not found useful template!')

            data = {
                "name": f"Autocheck_{api.service.path}.{api.service.name}.{api.name}_{api.topic}",
                "author": request.headers.get('email', 'no-user'),
                "topic": api.topic,
                "command": [f"{api.service.path}.{api.service.name}.{api.name}"],
                "service_id": api.service.id,
                "config_key": "9d167d37d80016fb4f16f7acaec7cc0ea3bcb92d20694eb6c9bc5771ff2cbc48",
                "server_name": 'app.tcp_server',
                "env": json_data.get("routing", {}).get('env', 'test'),
                "region": json_data.get("routing", {}).get('region', ""),
                "routing_cid": json_data.get("routing", {}).get('routing_cid', ""),
                "pfb": json_data.get("routing", {}).get('pfb', ""),
            }
            spex_auto_check.queue(api_id, data, token=request.headers.get('token'),
                                  timeout=1 * 60 * 60, result_ttl=24 * 60 * 60)

            return resp_return('EXECUTE_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpAutoCheckView(BaseResource):
    def post(self, api_id):
        try:
            try:
                json_data = request.get_json()
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            if not json_data.get("env_id"):
                return resp_return('PARAM_INVALID', new_msg=f'Need env')

            api = HttpApi.query.get(api_id)
            if not api:
                return resp_return('NOFOUND_ERROR', new_msg='not found api!')

            if not api.templates:
                return resp_return('NOFOUND_ERROR', new_msg='not found useful template!')

            data = {
                "name": f"Autocheck_{api.http_project.name}.{api.http_menu.name}.{api.name}",
                "author": request.headers.get('email', 'no-user'),
                "env_id": json_data["env_id"],
                "apis": [api_id],
                "http_project_id": api.http_project.id
            }
            http_auto_check.queue(api_id, data, token=request.headers.get('token'),
                                  timeout=1 * 60 * 60, result_ttl=24 * 60 * 60)

            return resp_return('EXECUTE_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexBatchAutoCheckView(BaseResource):
    def post(self, service_id):
        try:
            try:
                json_data = request.get_json()
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            service = SpexService.query.get(service_id)
            plan_name = json_data.get('plan_name')
            topic = json_data.get('topic')
            api_id_list = json_data.get('apis', [])
            if not plan_name:
                return resp_return('PARAM_INVALID', new_msg=f'Need plan name!')

            for plan in service.plans:
                if plan.deleted is False and plan.name == plan_name:
                    return resp_return('PARAM_INVALID', new_msg=f'Duplicate plan name!')

            data = {
                "name": plan_name,
                "author": request.headers.get('email', 'no-user'),
                "topic": topic,
                "command": [],
                "service_id": service_id,
                "config_key": "9d167d37d80016fb4f16f7acaec7cc0ea3bcb92d20694eb6c9bc5771ff2cbc48",
                "server_name": 'app.tcp_server',
                "env": json_data.get("routing", {}).get('env', 'test'),
                "region": json_data.get("routing", {}).get('region', ""),
                "routing_cid": json_data.get("routing", {}).get('routing_cid', ""),
                "pfb": json_data.get("routing", {}).get('pfb', ""),
            }
            spex_batch_auto_check.queue(api_id_list, data, token=request.headers.get('token'),
                                        timeout=1 * 60 * 60, result_ttl=24 * 60 * 60)

            return resp_return('EXECUTE_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpBatchAutoCheckView(BaseResource):
    def post(self, project_id):
        try:
            try:
                json_data = request.get_json()
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            project = HttpProject.query.get(project_id)
            if not project:
                return resp_return('NOFOUND_ERROR', new_msg='Not found project!')

            if not json_data.get("env_id"):
                return resp_return('PARAM_INVALID', new_msg=f'Need env')

            plan_name = json_data.get('plan_name')
            api_id_list = json_data.get('apis', [])
            if not plan_name:
                return resp_return('PARAM_INVALID', new_msg=f'Need plan name!')

            for plan in project.plans:
                if plan.deleted is False and plan.name == plan_name:
                    return resp_return('PARAM_INVALID', new_msg=f'Duplicate plan name!')

            if len(api_id_list) == 0:
                # Empty run all
                api_id_list = [api.id for api in project.apis]

            data = {
                "name": plan_name,
                "author": request.headers.get('email', 'no-user'),
                "apis": api_id_list,
                "env_id": json_data["env_id"],
                "http_project_id": project_id
            }
            http_batch_auto_check.queue(data, token=request.headers.get('token'),
                                        timeout=1 * 60 * 60, result_ttl=24 * 60 * 60)

            return resp_return('EXECUTE_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
