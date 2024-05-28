# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Arrow

from flask import request, current_app
from collections import defaultdict
from app.commons import db, ma, resp_return
import app.commons.utils as utils
from app.resources import BaseResource
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
import sqlalchemy
import marshmallow
from app.models import Page, page_schema, Element, element_schema


class RequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    name = ma.String()
    project_id = ma.Integer()
    mum_id = ma.Integer()
    organized = ma.String()


class PagesView(BaseResource):
    def get(self, ):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', f'{str(err.args)}')
        organized = query_args.pop("organized", None)

        param = self.get_common_params(query_args, Page)
        query = Page.query.filter(*param)

        if organized:
            result = []
            all_pages = defaultdict(dict)
            items = query.order_by(Page.updated_time.desc()).all()
            for item in items:
                all_pages[item.name] = {
                    "title": item.name,
                    "key": item.id,
                    "children": []
                }
            need_del = []
            for item in items:
                if item.mum:
                    all_pages[item.mum.name]["children"].append(
                        all_pages[item.name])
                    need_del.append(item.name)

            for name in need_del:
                all_pages.pop(name)

            result = list(all_pages.values())

            return resp_return('QUERY_SUCCESS', result, len(result))

        else:
            pages = query.order_by(Page.updated_time.desc()).paginate(
                page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            result = page_schema.dump(pages.items, many=True)
            return resp_return('QUERY_SUCCESS', result, pages.total)

    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', f'{str(err.args)}')

        if not json_data:
            return resp_return('JSON_ERROR')

        try:
            Page.post_check(json_data)
            page = page_schema.load(utils.del_id_none(json_data))
            page.save()

        except marshmallow.ValidationError as err:
            return resp_return('JSON_ERROR', err.messages)
        except (UniqueViolation, IntegrityError) as err:
            return resp_return('UNIQUE_ERROR', str(err))
        except sqlalchemy.exc.InvalidRequestError as err:
            return resp_return('DB_ERROR', str(err))
        except Exception as err:
            return resp_return('COMMON_ERROR', str(err))
        else:
            return resp_return('CREATE_SUCCESS')


class PageView(BaseResource):
    def get(self, id):
        item = Page.query.filter_by(id=id).first()
        if item:
            result = page_schema.dump(item)

            return resp_return('QUERY_SUCCESS', result)
        else:
            return resp_return('NOFOUND_ERROR')

    def put(self, id):
        json_data = request.get_json()
        if not json_data:
            return resp_return('JSON_ERROR')

        item = Page.query.filter_by(id=id).first()
        if item:
            try:
                self.common_put(item, json_data)

            except Exception as err:
                return resp_return('DB_ERROR', str(err))
            else:
                return resp_return('UPDATE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR')

    def delete(self, id):
        item = Page.query.filter_by(id=id).first()
        if item:
            try:
                item.delete()
            except Exception as err:
                return resp_return('DB_ERROR', str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR')
