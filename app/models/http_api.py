# -*- coding: utf-8 -*-
# @Time    : 2022/07/18
# @Author  : Chen Jiaxin

import json
from flask import current_app
from .mixins import TimestampMixin, HTTP_TYPE
from app.commons import db, ma
from .common_check import CommonCheck
from .http_menu import HttpMenu


class HttpApi(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'http_api'
    id = db.Column(db.Integer, primary_key=True)
    yapi_id = db.Column(db.Integer, nullable=False, index=True)
    name = db.Column(db.String(127), nullable=False)
    method = db.Column(db.String(127), nullable=False)
    path = db.Column(db.String(127), nullable=False)
    desc = db.Column(db.String(), nullable=True)
    headers = db.Column(db.ARRAY(db.JSON), nullable=True, default=[])
    params = db.Column(db.ARRAY(db.JSON), nullable=True, default=[])
    queries = db.Column(db.ARRAY(db.JSON), nullable=True, default=[])
    body = db.Column(db.JSON, nullable=True, default={})
    response = db.Column(db.JSON, nullable=True, default={})
    errors = db.Column(db.JSON, nullable=True, default={})

    http_menu_id = db.Column(db.Integer, db.ForeignKey('http_menu.id'))
    http_menu = db.relationship('HttpMenu', backref=db.backref('apis', lazy=True), lazy='select',
                                cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    http_project_id = db.Column(db.Integer, db.ForeignKey('http_project.id'))
    http_project = db.relationship('HttpProject', backref=db.backref('apis', lazy=True), lazy='select',
                                   cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    def rdelete(self):
        for template in self.templates:
            template.rdelete()
        super().rdelete()

    @classmethod
    def _parse_array(cls, item):
        array_type = item[0]['type']
        children = item[0]['children']
        if array_type == 'object':
            ret = [cls.get_r_for_health_check(children)]
        elif array_type == 'array':
            ret = [cls._parse_array(children)]
        else:
            ret = [HTTP_TYPE[array_type]]
        return ret

    @classmethod
    def get_r_for_health_check(cls, items):
        ret_dict = {}
        for item in items:
            k = item['name']
            t = item['type']
            if t in HTTP_TYPE:
                if t == 'integer' and item['desc'].find("int64") + item['desc'].find("INT64") >= -1:
                    ret_dict[k] = 'INT64'
                else:
                    ret_dict[k] = HTTP_TYPE[t]
            elif t == 'array':
                ret_dict[k] = cls._parse_array(item["children"])
            elif t == 'object':
                ret_dict[k] = cls.get_r_for_health_check(item['children'])
        return ret_dict

    @classmethod
    def parse_error_code(cls, response):
        errors = {}
        for item in response.get('children', []):
            if item['name'] in ['err_code']:
                err_str = item.get('desc', '{}')
                if err_str:
                    try:
                        errors = json.loads(err_str)
                    except Exception:
                        current_app.logger.error(f"Fail to get error code")
        return errors

    def get_path_with_params(self, ):
        path = self.path
        for param in self.params:
            if param.get('example'):
                path = path.replace('{' + param['name'] + '}', param['example'])
        return path

    def get_header_dict(self, ):
        return {h['name']: h['value'] for h in self.headers}

    def get_query_dict(self, ):
        return {h['name']: h.get('example', '') for h in self.queries}


class HttpApisSchema(ma.ModelSchema):
    class Meta:
        model = HttpApi
        fields = ('id', 'name')


class HttpApiDetailSchema(ma.ModelSchema):
    class Meta:
        model = HttpApi
        fields = ('method', 'path', 'headers', 'params', 'queries', 'body', 'response', 'errors')


http_apis_schame = HttpApisSchema()
http_api_detail_schema = HttpApiDetailSchema()
