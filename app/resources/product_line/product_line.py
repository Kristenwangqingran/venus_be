# -*- coding: utf-8 -*-
# @Time    : 2021/06/02
# @Author  : minhao.zhang


import json
import traceback
from flask import request, current_app

from app import MyRedis
from app.models import Member, ProductLine, product_line_schema, Feature
from app.resources import BaseResource
from app.commons import ma, resp_return, get_config
from app.libs import sync_product_line

import requests

CONF = get_config()


def get_productlines():
    data = None
    key = "productlines"
    # 先通过缓存查找
    try:
        hd = MyRedis(CONF.REDIS['URL_FOR_PRODUCTLINES'])

        data = hd.get(key)
        data = json.loads(data) if data else {}
    except Exception as e:
        current_app.logger.warning(f"cacha error! {str(e)}")
        # 缓存没有再通过接口查找
    if not data:
        try:
            CAP_PRODUCTLINE_URL = f"{current_app.config['CAP_URL']}/api/productline"
            hd = MyRedis(CONF.REDIS['URL_FOR_PRODUCTLINES'])
            r = requests.get(url=CAP_PRODUCTLINE_URL)
            r.raise_for_status()
            data = r.json()["data"]["items"]
            # 存个缓存
            hd.set(key, json.dumps(data), ex=5 * 60 * 60)
        except Exception as e:
            return resp_return("SERVER_AVALIABLE", f"cap request err! {str(e)}")
    return data


class ProductLinesView(BaseResource):
    def get(self, ):
        try:
            product_lines = ProductLine.query.filter_by(deleted=False).all()
            ret = product_line_schema.dump(product_lines, many=True)

            return resp_return('QUERY_SUCCESS', ret)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def post(self, ):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            json_data['platform'] = 'venus'
            ProductLine.post_check(json_data)
            product_line = product_line_schema.load(json_data)
            product_line.save()
            return resp_return('CREATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class ProductLineView(BaseResource):
    def get(self, product_line_id):
        try:
            product_line = ProductLine.query.get(product_line_id)
            if not product_line:
                return resp_return('NOFOUND_ERROR', new_msg='Not found product line!')

            ret = product_line_schema.dump(product_line)

            return resp_return('QUERY_SUCCESS', ret)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, product_line_id):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            product_line = ProductLine.query.get(product_line_id)
            if not product_line:
                return resp_return('NOFOUND_ERROR', new_msg='Not found product line!')

            product_line.put_save(json_data)
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self, product_line_id):
        try:
            product_line = ProductLine.query.get(product_line_id)
            if not product_line:
                return resp_return('NOFOUND_ERROR', new_msg='Not found product line!')

            product_line.delete()

            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class RequestArgs(ma.Schema):
    id = ma.Integer(required=True)
    product_line_id = ma.Integer(required=True)
    sub_line = ma.String(required=True)
    feature = ma.String(required=True)
    product_line = ma.String(required=True)
    department_id = ma.Integer(required=True)
    department_name = ma.String(required=True)


class ProductsView(BaseResource):

    def get(self, ):
        args = request.args
        product_line = ProductLine.query.get(args.get("product_line_id", None))
        if not product_line:
            return resp_return('NOFOUND_ERROR', new_msg='Not found product line!')

        features = []
        for sub_line in product_line.sub_lines:
            if sub_line.name == args.get("sub_line", None):
                features = [{"feature": feature.name, "feature_id": feature.id}
                            for feature in sub_line.features if not feature.deleted]

        return resp_return('QUERY_SUCCESS', features, len(features))


class SyncProductLineView(BaseResource):
    def post(self, ):
        try:
            sync_product_line()
            return resp_return('EXECUTE_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class ProductsSelectorView(BaseResource):

    def get(self, ):
        try:
            email = request.headers.get("email")
            member = Member.query.filter_by(email=email, deleted=False).first()
            if not member:
                return resp_return('NOFOUND_ERROR', new_msg='menber not exists in database!')

            result = []
            if 'leader' not in member.role or email in current_app.config['ADMIN']:
                visited = []
                for feature in member.features:
                    if not feature.deleted:
                        product_line = feature.sub_line.product_line
                        if not product_line.deleted and product_line.id not in visited:
                            belong_sub_line = feature.sub_line.name
                            result.append({
                                "product_line_id": product_line.id,
                                "product_line": product_line.name,
                                "children": [{"product_line": belong_sub_line}] +
                                            [{"product_line": sub_line.name}
                                             for sub_line in product_line.sub_lines if not sub_line.deleted
                                             and sub_line.name != belong_sub_line]
                            })
                            visited.append(product_line.id)

                if email in current_app.config['ADMIN']:
                    features = Feature.query.filter_by(deleted=False).all()
                    for feature in features:
                        if not feature.deleted:
                            product_line = feature.sub_line.product_line
                            if not product_line.deleted and product_line.id not in visited:
                                result.append({
                                    "product_line_id": product_line.id,
                                    "product_line": product_line.name,
                                    "children": [{"product_line": sub_line.name}
                                                 for sub_line in product_line.sub_lines if not sub_line.deleted]
                                })
                                visited.append(product_line.id)

            else:
                # for leader
                departments = list(set([p.department for p in member.product_lines if not p.deleted]))
                for department in departments:
                    product_lines = ProductLine.query.filter_by(department=department, deleted=False).all()
                    for product_line in product_lines:
                        result.append({
                            "product_line_id": product_line.id,
                            "product_line": product_line.name,
                            "children": [{"product_line": sub_line.name}
                                         for sub_line in product_line.sub_lines if not sub_line.deleted]
                        })

            return resp_return('QUERY_SUCCESS', result)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class DepartmentView(BaseResource):
    def get(self, ):
        try:
            product_lines = ProductLine.query.filter_by(deleted=False).all()
            departments = list(set([p.department for p in product_lines]))
            return resp_return('QUERY_SUCCESS', departments)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
