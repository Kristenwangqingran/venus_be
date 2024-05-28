# -*- coding: utf-8 -*-
# @Time    : 2020/8/7
# @Author  : Arrow

from flask import request, current_app
import uuid
from app.commons import ma, resp_return
import app.commons.utils as utils
from app.resources import BaseResource
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
import sqlalchemy
import marshmallow
from app.models import Element, element_schema, Page


class RequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    alias = ma.String()
    memo = ma.String()
    project_id = ma.Integer()
    page_id = ma.Integer()
    page_id_list = ma.String()
    author = ma.String()


class ElementsView(BaseResource):
    def get(self, ):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', f'{str(err.args)}')

        page_id_list = query_args.pop('page_id_list', None)
        param = self.get_common_params(query_args, Element)
        if page_id_list:
            param.append(Element.page_id.in_(
                page_id_list.strip(',').split(',')))

        query = Element.query.filter(*param)

        items = query.order_by(Element.updated_time.desc()).paginate(
            page=query_args["page"], per_page=query_args["per_page"], error_out=False)
        result = element_schema.dump(items.items, many=True)

        # need to improve the performance
        for item in result:
            if item.get('page_id', None):
                item['page_name'] = Page.query.get(item['page_id']).name

        return resp_return('QUERY_SUCCESS', result, items.total)

    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', f'{str(err.args)}')

        if not json_data:
            return resp_return('JSON_ERROR')

        try:
            Element.post_check(json_data)
            item = element_schema.load(utils.del_id_none(json_data))
            item.save()

        except Exception as err:
            return resp_return('COMMON_ERROR', new_msg=str(err))
        else:
            return resp_return('CREATE_SUCCESS')


class ElementView(BaseResource):
    def get(self, id):

        item = Element.query.filter_by(id=id).first()
        if item:
            result = element_schema.dump(item)

            return resp_return('QUERY_SUCCESS', result)
        else:
            return resp_return('NOFOUND_ERROR')

    def put(self, id):
        json_data = request.get_json()
        if not json_data:
            return resp_return('JSON_ERROR')
        item = Element.query.filter_by(id=id).first()
        if item:
            try:
                self.common_put(item, json_data)

            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('UPDATE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR')

    def delete(self, id):
        item = Element.query.filter_by(id=id).first()
        if item:
            try:
                item.delete()
            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR')
