# -*- coding: utf-8 -*-
# @Time    : 2020-08-04
# @Author  : GongXun


import copy
import os
import uuid

from flask import request, g, jsonify
from flask_restful import Resource, current_app
from app.commons import db, utils, ma


def limiter_by_path():
    if request.method in ("OPTIONS",):
        return uuid.uuid4().hex
    else:
        current_app.logger.info(f"request.path: {request.path}")
        return str(request.path)


def limiter_by_project():
    if request.method in ("OPTIONS",):
        return uuid.uuid4().hex
    else:
        current_app.logger.info(f"request.body: {request.get_json()}")
        return str(request.get_json())


def limiter_by_user():
    ret = "nobody"
    current_app.logger.info(f"g.email: {g.email}")
    if g.user:
        ret = str(g.user)
    return ret


# can deside the rate by user, promotion user can use more
def rate_limit_for_user():
    return "15/day;5/hour;1/10minute"


def index_ratelimit_error_responder_for_user(request_limit):
    return jsonify({"code": 400, "message": f"you call the api too many times, take a break~"})


class BaseResource(Resource):

    def get_common_params(self, args, classobj):
        params = [getattr(classobj, 'deleted') == False]
        for key, value in args.items():
            if (value or isinstance(value, bool) or (isinstance(value, int) and value == 0)) and key not in {'page', 'per_page'}:
                if key in {'name', 'author', 'priority', 'category', 'type'}:
                    params.append(
                        getattr(classobj, key).ilike("%" + value + "%"))
                else:
                    params.append(getattr(classobj, key) == value)
        return params

    def delete_old_resource(self, resource):
        db.session.delete(resource)
        db.session.flush()

    # can handle headers and data
    def FEtoBE_headers(self, headers):
        if isinstance(headers, list):
            new_headers = {}
            for item in headers:
                new_headers[item['key']] = item['value']
            return new_headers
        else:
            return headers

    def BEtoFE_headers(self, headers):
        new_headers = []
        for k, v in headers.items():
            new_headers.append({'key': k, 'value': v})
        return new_headers

    def del_emptys(self, alist):
        ret = []
        for item in alist:
            if item:
                ret.append(item)
        return ret

    @staticmethod
    def common_put(obj, json_data):
        obj.put_check(json_data)
        for k, v in json_data.items():
            if k in ('id', 'created_time', 'updated_time'):
                continue
            elif isinstance(v, (dict, list)):
                tmp_v = copy.deepcopy(v)
                setattr(obj, k, tmp_v)
            else:
                setattr(obj, k, v)

        obj.deleted = False
        obj.save()

    @staticmethod
    def common_put_for_member(obj, json_data):
        obj.put_check(json_data)
        for k, v in json_data.items():
            if k in ('id', 'created_time', 'updated_time'):
                continue
            elif isinstance(v, (dict, list)):
                tmp_v = copy.deepcopy(v)
                setattr(obj, k, tmp_v)
            else:
                setattr(obj, k, v)

        obj.save()

    @staticmethod
    def common_put_for_caseresult(obj, json_data):
        obj.put_check(json_data)
        for k, v in json_data.items():
            if k in ('id', 'created_time', 'updated_time'):
                continue
            elif isinstance(v, (dict, list)):
                if k == 'worker':
                    tmp_v = copy.deepcopy(getattr(obj, k))
                    tmp_v.update(v)
                else:
                    tmp_v = copy.deepcopy(v)
                setattr(obj, k, tmp_v)
            else:
                setattr(obj, k, v)

        obj.deleted = False
        obj.save()

    def common_put_for_project(self, obj, json_data):
        obj.put_check(json_data)
        for k, v in json_data.items():
            if k in ('id', 'created_time', 'updated_time'):
                continue
            elif k in ('name') and v != getattr(obj, k):
                current_app.logger.info(
                    f"modify project: {obj.name}: {k} form {getattr(obj, k)} to {v}")

                # 修改project name时，有两个以project name命名的对象也需要修改
                if k == 'name':
                    for i in range(len(obj.case_groups)):
                        group = obj.case_groups[i]
                        # 只需要修改根结点
                        if not group.mum_id:
                            group.name = v
                            group.save()

                # 如果是原来的路径命名，需要根据新的路径命名规则新建路径，复制原来路径下的所有文件到新路径下，并删除原来的路径
                if os.path.join(obj.get_product_line_name(), obj.name) in obj.get_product_path():
                    old_product_path = obj.get_product_path()
                    new_product_path = old_product_path.replace(
                        os.path.join(obj.get_product_line_name(), obj.name), str(obj.id))
                    utils.send_cmd(
                        f'ln -s {old_product_path} {new_product_path}')

                    # log路径与product路径保持一致，使用id命名
                    old_log_path = obj.get_log_path()
                    new_log_path = old_log_path.replace(
                        os.path.join(obj.product_line_name, obj.name), str(obj.id))
                    old_log_path = os.path.join(old_log_path, '.')
                    utils.send_cmd(f'cp -r  {old_log_path} {new_log_path}')

                setattr(obj, k, v)

            elif isinstance(v, (dict, list)):
                tmp_v = copy.deepcopy(v)
                setattr(obj, k, tmp_v)
            else:
                setattr(obj, k, v)

        obj.deleted = False
        obj.save()

    def common_check(self, value, normal):
        errors = []
        for k, v in normal.items():
            if k in value:
                if not isinstance(value[k], type(v)):
                    errors.append(
                        f"{k}: value has wrong type! [{type(value[k])} != {type(v)}]")
            else:
                errors.append(f"{k} missed!")

        return errors

    def _convert_type(self, validators):
        method_map = {
            "int": int,
            "float": float,
            "string": str,
            "bool": bool,
            "array": eval,
            "json": eval
        }
        result = []
        for item in validators:
            if item['expectType'] in ("int", "float", "string", "array", "json"):
                item["expect"] = method_map[item['expectType']](item["expect"])

            elif item['expectType'] in ("bool", ):
                if item["expect"] in ("", "0", 0):
                    item["expect"] = False
                else:
                    item["expect"] = True

            result.append(item)
        return result


class OpenAPIRequestArgs(ma.Schema):
    skip = ma.Bool(default=False)
    sync = ma.Bool(default=True)
    lazy = ma.Bool(default=False)
