# -*- coding: utf-8 -*-
# @Time    : 2022/07/20
# @Author  : Chen Jiaxin


import time
import traceback
from app.resources import BaseResource
from flask import request, current_app
from app.libs import HttpApiManagement, get_http_api, update_http_api
from app.commons import resp_return, ma
from app.models import HttpProject, HttpApi, http_projects_schema, http_menus_schame, http_apis_schame, \
    http_api_detail_schema, HttpEnv, http_envs_schema, http_env_detail_schema


class HttpProjectsView(BaseResource):
    def get(self, ):
        try:
            projects = http_projects_schema.dump(
                HttpProject.query.filter_by(deleted=False).all(), many=True)

            return resp_return('QUERY_SUCCESS', projects)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpProjectView(BaseResource):
    def put(self, project_id):
        try:
            project = HttpProject.query.get(project_id)
            if not project:
                return resp_return('NOFOUND_ERROR', new_msg='Not found project!')

            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            project.put_save(json_data)

            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self, project_id):
        try:
            project = HttpProject.query.get(project_id)
            if not project:
                return resp_return('NOFOUND_ERROR', new_msg='Not found project!')

            project.rdelete()

            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpMenuView(BaseResource):
    def get(self, project_id):
        try:
            project = HttpProject.query.get(project_id)
            if not project:
                return resp_return('NOFOUND_ERROR', new_msg='Not found project!')

            menus = http_menus_schame.dump(project.menus, many=True)

            return resp_return('QUERY_SUCCESS', menus)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpApisRequestArgs(ma.Schema):
    project_id = ma.Integer(default=0)
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=10)


class HttpApisView(BaseResource):
    def get(self, ):
        try:
            try:
                query_args = HttpApisRequestArgs().dump(request.args)
                query_args["menus"] = request.args.getlist("menus")
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            if query_args["project_id"] != 0:
                apis = HttpApi.query.filter_by(http_project_id=query_args["project_id"]).paginate(
                    page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            elif query_args["menus"]:
                apis = HttpApi.query.filter(
                    HttpApi.http_menu_id.in_(query_args["menus"])
                ).paginate(
                    query_args["page"], query_args["per_page"], error_out=False
                )
            else:
                apis = HttpApi.query.paginate(
                    page=query_args["page"], per_page=query_args["per_page"], error_out=False)

            ret = http_apis_schame.dump(apis.items, many=True)

            return resp_return('QUERY_SUCCESS', ret, apis.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpApiDetailView(BaseResource):
    def get(self, api_id):
        try:
            api = HttpApi.query.get(api_id)
            if not api:
                return resp_return('NOFOUND_ERROR', new_msg='Not found api!')

            ret = http_api_detail_schema.dump(api)

            return resp_return('QUERY_SUCCESS', ret)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpEnvRequestArgs(ma.Schema):
    yapi_url = ma.String(default='')
    project_id = ma.Integer(default=0)
    yapi_project_token = ma.String(default='')


class HttpEnvsView(BaseResource):
    def get(self, ):
        try:
            try:
                query_args = HttpEnvRequestArgs().dump(request.args)
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            if query_args["project_id"]:
                project = HttpProject.query.get(query_args["project_id"])
                if not project:
                    return resp_return('NOFOUND_ERROR', new_msg='Not found project!')

                env_list = http_envs_schema.dump(project.envs, many=True)

            else:
                http_mgr = HttpApiManagement(
                    query_args["yapi_project_token"], yapi_url=query_args["yapi_url"])
                env_list = http_mgr.get_env_list()

            return resp_return('QUERY_SUCCESS', env_list)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpEnvDetailView(BaseResource):
    def get(self, env_id):
        try:
            env = HttpEnv.query.get(env_id)
            if not env:
                return resp_return('NOFOUND_ERROR', new_msg='Not found env!')

            env_info = http_env_detail_schema.dump(env)

            return resp_return('QUERY_SUCCESS', env_info)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpUpdateView(BaseResource):
    def post(self, ):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            project_id_list = json_data.get('project_id_list')
            yapi_project_token = json_data.get('yapi_project_token')
            yapi_url = json_data.get('yapi_url')
            s_type = json_data.get("type", "add")

            process_id = int(time.time())

            if s_type == "add":
                if not all([yapi_project_token, yapi_url]):
                    return resp_return('PARAM_INVALID', new_msg=f'Need yapi url, project id and token!')

                yapi_project = HttpProject.query.filter_by(
                    yapi_url=yapi_url, token=yapi_project_token).first()
                if yapi_project:
                    return resp_return('UNIQUE_ERROR', new_msg=f"Project exist!")

                get_http_api.queue(yapi_project_token=yapi_project_token,
                                   process_id=process_id,
                                   yapi_url=yapi_url,
                                   author=request.headers.get(
                                       'email', 'Unknown'),
                                   timeout=24 * 60 * 60, result_ttl=24 * 60 * 60)

            elif s_type == "update":
                if not project_id_list:
                    return resp_return('PARAM_INVALID', new_msg=f'Update need id!')

                update_http_api.queue(project_id_list=project_id_list,
                                      process_id=process_id,
                                      timeout=24 * 60 * 60, result_ttl=24 * 60 * 60)

            else:
                return resp_return('PARAM_INVALID', new_msg=f'Unknown type!')

            return resp_return('EXECUTE_OK', process_id)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpApiErrorsView(BaseResource):
    def get(self, api_id):
        try:
            api = HttpApi.query.get(api_id)
            if not api:
                return resp_return('NOFOUND_ERROR')

            return resp_return('QUERY_SUCCESS', api.errors)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
