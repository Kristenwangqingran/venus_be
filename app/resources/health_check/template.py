# -*- coding: utf-8 -*-
# @Time    : 2022/2/28
# @Author  : Jiaxin Chen

import traceback
from app.resources import BaseResource
from flask import request, current_app
from app.commons import resp_return, ma
from app.models import HcTemplate, hc_template_schema, hc_templates_schema, hc_template_detail_schema, SpexApi, \
    http_template_schema, http_template_detail_schema, HttpApi, HttpEnv


class SpexTemplatesRequestArgs(ma.Schema):
    topic = ma.String()
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=10)


class SpexTemplatesView(BaseResource):
    def get(self, api_id):
        try:
            try:
                query_args = SpexTemplatesRequestArgs().dump(request.args)
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            templates = HcTemplate.query.filter_by(api_id=api_id, deleted=False).order_by(HcTemplate.id).paginate(
                page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            result = hc_templates_schema.dump(templates.items, many=True)
            return resp_return('QUERY_SUCCESS', result, templates.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class AddSpexTemplateView(BaseResource):
    def post(self):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            json_data['author'] = request.headers.get('email', 'no-user')
            json_data['api_type'] = "spex"

            HcTemplate.post_check(json_data)
            template = hc_template_schema.load(json_data)
            template.save()
            return resp_return('CREATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexTemplateView(BaseResource):
    def get(self, template_id):
        try:
            template = HcTemplate.query.get(template_id)
            if not template:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding template found!")

            info = hc_template_detail_schema.dump(template)

            return resp_return('QUERY_SUCCESS', info)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, template_id):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            template = HcTemplate.query.get(template_id)
            if not template:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding template found!")

            template.put_check(json_data)
            template.save()
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self, template_id):
        try:
            template = HcTemplate.query.get(template_id)
            if not template:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding template found!")

            if template.is_default:
                return resp_return('COMMON_ERROR', new_msg="Default template can not be deleted!")

            template.delete()
            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SpexBasicTemplateView(BaseResource):
    def get(self, api_id):
        try:
            from app.commons.hc_gen_case import default_template
            api = SpexApi.query.get(api_id)
            fields = default_template(
                api.request, api.response, list(api.errors.values()))
            updated = False
            for template in api.templates:
                if template.is_default:
                    template.put_check({
                        "name": "basic",
                        "type": "basic",
                        "is_default": True,
                        "fields": fields,
                        "api_id": api.id
                    })
                    template.save()
                    updated = True
            if not updated:
                template = HcTemplate(**{
                    "name": "basic",
                    "type": "basic",
                    "is_default": True,
                    "fields": fields,
                    "api_id": api.id
                })
                template.save()
            return resp_return('CREATE_SUCCESS', fields)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpTemplatesRequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=10)


class HttpTemplatesView(BaseResource):
    def get(self, api_id):
        try:
            try:
                query_args = HttpTemplatesRequestArgs().dump(request.args)
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            templates = HcTemplate.query.filter_by(http_api_id=api_id, deleted=False).order_by(HcTemplate.id).paginate(
                page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            result = hc_templates_schema.dump(templates.items, many=True)
            return resp_return('QUERY_SUCCESS', result, templates.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class AddHttpTemplateView(BaseResource):
    def post(self):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            json_data['author'] = request.headers.get('email', 'no-user')
            json_data['api_type'] = "http"

            HcTemplate.post_check_for_http(json_data)
            template = http_template_schema.load(json_data)
            template.save()
            return resp_return('CREATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpTemplateView(BaseResource):
    def get(self, template_id):
        try:
            template = HcTemplate.query.get(template_id)
            if not template:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding template found!")

            info = http_template_detail_schema.dump(template)

            return resp_return('QUERY_SUCCESS', info)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, template_id):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            template = HcTemplate.query.get(template_id)
            if not template:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding template found!")

            template.put_check(json_data)
            template.save()
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self, template_id):
        try:
            template = HcTemplate.query.get(template_id)
            if not template:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding template found!")

            if template.is_default:
                return resp_return('COMMON_ERROR', new_msg="Default template can not be deleted!")

            template.delete()
            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class ApiTemplateView(BaseResource):
    def get(self, ):
        try:
            templates = HcTemplate.query.filter(
                HcTemplate.type != "basic").all()
            ret = {}
            for template in templates:
                api_id = template.api_id
                if api_id not in ret:
                    api = SpexApi.query.get(api_id)
                    ret[api_id] = {
                        "api_path": f"{api.service.name}.{api.service.path}",
                        "api_name": api.name,
                        "topic": api.topic,
                        "user_templates": [],
                        "templates_num": 0
                    }
                ret[api_id]["user_templates"].append({
                    "id": template.id,
                    "name": template.name
                })
                ret[api_id]["templates_num"] += 1
            return resp_return('QUERY_SUCCESS', ret)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
