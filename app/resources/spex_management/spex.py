# -*- coding: utf-8 -*-
# @Time    : 2021/1/24
# @Author  : Chen Jiaxin


import os
import time
import base64
import traceback
from app.resources import BaseResource
from flask import request, current_app
from app.commons import resp_return, ma, get_empty_value, utils
from app.libs import get_spex_api, SpaceTokenManagement
from app.models import SpexServiceGroup, SpexService, SpexApi, spex_service_query_schema, spex_api_overview_schema, \
    spex_service_group_detail_schema, spex_service_detail_schema, HcPlanResult


class SpexMenuView(BaseResource):
    def get(self, group_id):
        try:
            if group_id == 0:
                group_id = None

            groups = []
            for group in SpexServiceGroup.query.filter_by(mum_id=group_id, deleted=False).all():
                groups.append({
                    "group_id": group.id,
                    "name": group.name,
                    "space_id": group.space_id,
                    "type": "group"
                })
            groups.sort(key=lambda x: x["name"])

            services = []
            for service in SpexService.query.filter_by(group_id=group_id, deleted=False).all():
                services.append({
                    "service_id": service.id,
                    "name": service.name,
                    "space_id": service.space_id,
                    "type": "service"
                })
            services.sort(key=lambda x: x["name"])

            return resp_return('QUERY_SUCCESS', groups + services)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexGroupInfo(BaseResource):
    def get(self, group_id):
        try:
            group = SpexServiceGroup.query.get(group_id)
            if not group:
                return resp_return('NOFOUND_ERROR', new_msg='Not found group')

            children_groups = spex_service_group_detail_schema.dump(
                group.children, many=True)
            services = spex_service_detail_schema.dump(
                group.services, many=True)

            return resp_return('QUERY_SUCCESS', children_groups + services)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexTopicView(BaseResource):
    def get(self, service_id):
        try:
            service = SpexService.query.get(service_id)
            if not service:
                return resp_return('NOFOUND_ERROR')
            return resp_return('QUERY_SUCCESS', service.topics)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexApiRequestArgs(ma.Schema):
    topic = ma.String(default='master')
    name = ma.String(default='')
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=10)


class SpexServiceApisView(BaseResource):
    def get(self, service_id):
        try:
            try:
                query_args = SpexApiRequestArgs().dump(request.args)
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            apis = SpexApi.query.order_by(SpexApi.id).filter(
                SpexApi.service_id == service_id,
                SpexApi.deleted == False,
                SpexApi.topic == query_args['topic'],
                SpexApi.name.ilike(f"%{query_args['name']}%")).paginate(
                    page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            data = spex_api_overview_schema.dump(apis.items, many=True)

            return resp_return('QUERY_SUCCESS', data, apis.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexApiListView(BaseResource):
    def get(self, ):
        try:
            service_name = request.args.get('service_name', '')
            topic = request.args.get('topic', '')
            path, name = service_name.rsplit('.', 1)
            service = SpexService.query.filter_by(path=path, name=name).first()
            if not service:
                return resp_return('NOFOUND_ERROR', new_msg='Service not found')

            api_list = [
                f'{service_name}.{api.name}' for api in service.apis if api.topic == topic]
            return resp_return('QUERY_SUCCESS', api_list)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexApiView(BaseResource):
    def put(self, planresult_id):
        try:
            planresult = HcPlanResult.query.get(planresult_id)
            if not planresult:
                return resp_return('NOFOUND_ERROR', new_msg='not found plan result!')

            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            apis = planresult.plan.service.apis
            for api_name, health_degree in json_data.items():
                flag = False
                for api in apis:
                    if api.name == api_name:
                        api.health_degree = health_degree
                        api.save()
                        flag = True
                if not flag:
                    current_app.logger.error(
                        f"Can't update health_degree for {api_name}!")

            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexDetailView(BaseResource):
    def get(self, api_id):
        try:
            api = SpexApi.query.get(api_id)
            if not api:
                return resp_return('NOFOUND_ERROR')
            data = {
                "req_name": api.req_name,
                "resp_name": api.resp_name,
                "request": api.request,
                "response": api.response
            }
            return resp_return('QUERY_SUCCESS', data)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexUpdateView(BaseResource):
    def post(self):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            stm = SpaceTokenManagement()
            token = stm.get_token_from_space()
            if not token:
                return resp_return('COMMON_ERROR', new_msg=f'No token')

            service_name = json_data.get('service_name')
            if service_name:
                path, name = service_name.rsplit('.', 1)
                service = SpexService.query.filter(
                    SpexService.path == path,
                    SpexService.name == name
                ).first()
                if service:
                    space_id_dict = {"services": [str(service.space_id)]}
                    topics = json_data.get('topics', [])
                    if topics:
                        space_id_dict['topics'] = {
                            str(service.space_id): topics}
                else:
                    return resp_return('NOFOUND_ERROR', new_msg=f'{service_name} not found!')
            else:
                space_id_dict = json_data.get('space_id_dict', {})
            update_all = json_data.get('update_all', False)

            process_id = int(time.time())

            get_spex_api.queue(token=token, space_id_dict=space_id_dict, update_all=update_all,
                               process_id=process_id, author=request.headers.get(
                                   'email', 'Unknown'),
                               timeout=24 * 60 * 60, result_ttl=24 * 60 * 60)

            return resp_return('EXECUTE_OK', process_id)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class ServiceRequestArgs(ma.Schema):
    service_name = ma.String(default='')
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=10)


class SpexServiceView(BaseResource):
    def get(self):
        try:
            try:
                query_args = ServiceRequestArgs().dump(request.args)
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            if query_args['service_name'] != '':
                services = SpexService.query.filter(SpexService.deleted == False,
                                                    SpexService.name.ilike(f"%{query_args['service_name']}%")).order_by(
                    SpexService.id).paginate(
                    page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            else:
                services = SpexService.query.filter_by(deleted=False).order_by(
                    SpexService.id).paginate(
                    page=query_args["page"], per_page=query_args["per_page"], error_out=False)

            data = spex_service_query_schema.dump(services.items, many=True)
            return resp_return('QUERY_SUCCESS', data, services.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexApisRequestArgs(ma.Schema):
    name = ma.String(required=True)
    topic = ma.String(required=False)
    with_default = ma.Boolean(default=False)


class SpexApisView(BaseResource):
    def _replace_default_value(self, r):
        if isinstance(r, str):
            if r == 'BYTES':
                return base64.b64encode(b'').decode('utf-8')
            return get_empty_value(r)
        elif isinstance(r, list):
            return [self._replace_default_value(item) for item in r]
        elif isinstance(r, dict):
            return {
                k: self._replace_default_value(v) for k, v in r.items()
            }

    def get(self):
        try:
            try:
                query_args = SpexApisRequestArgs().dump(request.args)
                query_name = query_args["name"]
                with_default = query_args["with_default"]
                if query_name.count('.'):
                    *service_name, api_name = query_name.split('.')
                    current_app.logger.info(
                        f"service_name: {service_name}, api_name: {api_name}")
                else:
                    service_name = None
                    api_name = query_name

                if not api_name or not service_name:
                    return resp_return('NOFOUND_ERROR')

            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            data = []
            dataset = SpexApi.query.filter(SpexApi.deleted == False)
            if query_args.get("topic"):
                dataset = SpexApi.query.filter(
                    SpexApi.topic == query_args["topic"])
            if service_name:
                dataset = dataset.join(SpexService, SpexApi.service_id == SpexService.id).filter(
                    SpexService.name == service_name[-1], SpexService.path == '.'.join(service_name[:-1]))

            all_apis = dataset.filter(SpexApi.name == api_name).all()
            # for api in SpexApi.query.filter(SpexApi.deleted == False, SpexApi.name.ilike("%" + query_args["name"] + "%")).all():
            for api in all_apis:
                data.append({
                    "name": api.name,
                    "id": api.id,
                    "topic": api.topic,
                    "service_name": f"{api.service.path}.{api.service.name}",
                    "service_id": api.service_id,
                    "request": self._replace_default_value(api.request) if with_default else api.request,
                    "response": self._replace_default_value(api.response) if with_default else api.response
                })

            return resp_return('QUERY_SUCCESS', data, len(data))

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexApiErrorsView(BaseResource):
    def get(self, api_id):
        try:
            api = SpexApi.query.get(api_id)
            if not api:
                return resp_return('NOFOUND_ERROR')

            return resp_return('QUERY_SUCCESS', api.errors)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexApiv2RequestArgs(ma.Schema):
    service = ma.String(required=False)
    topic = ma.String(required=False)
    name = ma.String(required=True)
    with_default = ma.Boolean(default=False)


class SpexApisv2View(SpexApisView):

    def get(self):
        try:
            try:
                query_args = SpexApiv2RequestArgs().dump(request.args)
                with_default = query_args["with_default"]

            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            data = []
            dataset = SpexApi.query.filter(SpexApi.deleted == False)
            if query_args.get("topic"):
                dataset = SpexApi.query.filter(
                    SpexApi.topic == query_args["topic"])

            if query_args.get("service"):
                service_name = query_args.get("service").split('.')
                dataset = dataset.join(SpexService, SpexApi.service_id == SpexService.id).filter(
                    SpexService.name == service_name[-1], SpexService.path == '.'.join(service_name[:-1]))

            all_apis = dataset.filter(SpexApi.name == query_args['name']).all()
            for api in all_apis:
                data.append({
                    "name": api.name,
                    "id": api.id,
                    "topic": api.topic,
                    "service_name": f"{api.service.path}.{api.service.name}",
                    "service_id": api.service_id,
                    "request": self._replace_default_value(api.request) if with_default else api.request,
                    "response": self._replace_default_value(api.response) if with_default else api.response
                })

            return resp_return('QUERY_SUCCESS', data, len(data))

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexPbView(BaseResource):
    def get(self, ):
        try:
            service = request.args.get('service')
            topic = request.args.get('topic')
            pb_dir = os.path.join("instance", current_app.config['PB_DIR'],
                                  utils.ensure_dirname(service),
                                  utils.ensure_dirname(os.path.join(topic)))
            pb_file = os.path.join(pb_dir, 'gen', 'py',
                                   utils.ensure_dirname(service) + '_pb2.py')
            s = ''
            with open(pb_file, 'r', encoding='utf-8') as f:
                s = f.readlines()

            return resp_return('QUERY_SUCCESS', s)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class PfbView(BaseResource):
    def get(self, api_id):
        try:
            api = SpexApi.query.get(api_id)
            pfbs = []
            if api.service.params:
                pfbs = api.service.params.get('pfb', [])

            return resp_return('QUERY_SUCCESS', pfbs)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self, api_id):
        try:
            json_data = request.get_json()
            del_pfb = json_data.get('pfb', '')
            api = SpexApi.query.get(api_id)
            pfbs = api.service.params.get('pfb', [])
            if del_pfb in pfbs:
                pfbs.remove(del_pfb)
                api.service.params = {"pfb": pfbs}
                api.service.save()

            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
