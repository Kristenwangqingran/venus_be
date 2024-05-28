# -*- coding: utf-8 -*-
# @Time    : 2022/4/14
# @Author  : Jiaxin Chen


import traceback
from flask import current_app, request
from app.commons import resp_return, ma
from app.resources import BaseResource
from app.models import PostWomenTemplate, postwomen_templates_schema, postwomen_template_detail_schema, \
    postwomen_template_schema


class TemplatesRequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=10)
    name = ma.String(default='')
    author = ma.String(default='')


class PostWomenTemplatesView(BaseResource):
    def get(self, api_id):
        try:
            try:
                query_args = TemplatesRequestArgs().dump(request.args)
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            result = PostWomenTemplate.query.filter(
                PostWomenTemplate.api_id == api_id,
                PostWomenTemplate.deleted == False,
                PostWomenTemplate.name.ilike(f'%{query_args["name"]}%'),
                PostWomenTemplate.author.ilike(f'%{query_args["author"]}%')
            ).order_by(PostWomenTemplate.updated_time.desc()).all()
            templates = postwomen_templates_schema.dump(result, many=True)

            demo_template = []
            other_templates = []
            for template in templates:
                if template['is_demo']:
                    demo_template.append(template)
                else:
                    other_templates.append(template)

            all_templates = demo_template + other_templates
            start = (query_args['page'] - 1) * query_args['per_page']
            end = (start + 1) * query_args['per_page']

            return resp_return('QUERY_SUCCESS', all_templates[start: end], len(all_templates))

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class PostWomenTemplateView(BaseResource):
    def get(self, id):
        try:
            template = PostWomenTemplate.query.get(id)
            if not template:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding template found!")

            info = postwomen_template_detail_schema.dump(template)

            return resp_return('QUERY_SUCCESS', info)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, id):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            template = PostWomenTemplate.query.get(id)
            if not template:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding template found!")

            if request.headers.get('email', 'no-user') != template.author:
                return resp_return('AUTH_FAILED', new_msg='You do not have the permission to modify!')

            template.put_save(json_data)
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self, id):
        try:
            template = PostWomenTemplate.query.get(id)
            if not template:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding template found!")

            if request.headers.get('email', 'no-user') != template.author:
                return resp_return('AUTH_FAILED', new_msg='You do not have the permission to delete!')

            template.delete()
            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class AddTemplateView(BaseResource):
    def post(self, ):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            json_data['author'] = request.headers.get('email', 'no-user')

            template = postwomen_template_schema.load(json_data)
            template.post_save()

            return resp_return('CREATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
