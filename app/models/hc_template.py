# -*- coding: utf-8 -*-
# @Time    : 2022/2/28
# @Author  : Jiaxin Chen

import copy
from .mixins import TimestampMixin
from app.commons import db, ma
from app.commons.hc_gen_case import check_template, structurize_template, flatten_template
from .common_check import CommonCheck
from marshmallow import ValidationError, fields, INCLUDE
from sqlalchemy.orm.attributes import flag_modified
from .http_api import HttpApi
from flask import current_app


class HcTemplate(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'hctemplate'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    type = db.Column(db.String(127), nullable=True, default='customised')
    is_default = db.Column(db.Boolean, default=False)
    fields = db.Column(db.JSON, nullable=True)
    params = db.Column(db.JSON, nullable=True, default={})

    api_id = db.Column(db.Integer, db.ForeignKey('spexapi.id'), nullable=True)
    api = db.relationship('SpexApi', backref=db.backref('templates', lazy=True), lazy='select',
                          cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    api_type = db.Column(db.String(127), nullable=True, default='spex')
    # for http
    http_api_id = db.Column(db.Integer, db.ForeignKey('http_api.id'), nullable=True)
    http_api = db.relationship('HttpApi', backref=db.backref('templates', lazy=True), lazy='select',
                               cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    @staticmethod
    def update_old_template(old, new):
        nd = {
            "request": {},
            'error_code_list': new.get('error_code_list', []),
            "response": {},
            "default_request": old.get("default_request", "{}"),
            "combination_rules": old.get("combination_rules", []),
            "user_specified_errors": old.get("user_specified_errors", {})
        }
        old_request = copy.deepcopy(old.get('request', {}))
        new_request = copy.deepcopy(new.get('request', {}))

        for field_name, info in new_request.items():
            nd['request'][field_name] = info
            if field_name in old_request:
                for k in info.keys():
                    if k == 'type':
                        pass
                    if k in old_request[field_name]:
                        nd['request'][field_name][k] = old_request[field_name][k]

        return nd

    @staticmethod
    def _get_params(data):
        params = data.get('params', {}).get('requestType', {})
        ret_params = {}
        if params and params.get('type', "") and params.get('value', ""):
            ret_params = {
                params['type']: params['value']
            }
        return ret_params

    @classmethod
    def post_check(cls, data):
        if cls.query.filter_by(api_id=data["api_id"], name=data["name"], deleted=False).all():
            raise ValidationError(f'name has existed!')

        basic = cls.query.filter_by(api_id=data["api_id"], type="basic").first()
        if not basic:
            raise ValidationError(f'This api do not have basic template!')

        flatten_template(data)
        data['fields'] = {
            "request": data.get("request", {}),
            "response": basic.fields.get("response", {}),
            "error_code_list": basic.fields.get("error_code_list", []),
            "default_request": data.get("default_request", "{}"),
            "combination_rules": data.get("combination_rules", []),
            "user_specified_errors": data.get("user_specified_errors", {})
        }

        err = check_template(data['fields'])
        if err:
            raise ValidationError(f'Template check error: {err}')

        data['params'] = cls._get_params(data)

        if 'request' in data:
            del data['request']

    @classmethod
    def post_check_for_http(cls, data):
        if cls.query.filter_by(http_api_id=data["http_api_id"], name=data["name"], deleted=False).all():
            raise ValidationError(f'name has existed!')

        basic = cls.query.filter_by(http_api_id=data["http_api_id"], type="basic").first()
        if not basic:
            raise ValidationError(f'This api do not have basic template!')

        flatten_template(data)
        data['fields'] = {
            "request": data.get("request", {}),
            "response": basic.fields.get("response", {}),
            "error_code_list": basic.fields.get("error_code_list", []),
            "default_request": data.get("default_request", "{}"),
            "combination_rules": data.get("combination_rules", [])
        }

        err = check_template(data['fields'])
        if err:
            raise ValidationError(f'Template check error: {err}')

        if data['request']:
            del data['request']

    def put_check(self, data):
        name = data.get("name", "")
        check_name = getattr(self, f'put_check_for_{self.api_type if self.api_type else "spex"}')
        check_name(name)

        for k, v in data.items():
            if k == 'request':
                tmp = flatten_template({'request': v})
                self.fields[k] = tmp[k]
            elif k in ['default_request', 'combination_rules', 'user_specified_errors']:
                self.fields[k] = v
            elif k == 'is_default':
                self.is_default = True
                api_instance = self.http_api if self.api_type and self.api_type == "http" else self.api
                for template in api_instance.templates:
                    if template.id == self.id:
                        continue
                    if template.is_default:
                        template.is_default = False
                        template.save()
            elif k == 'params':
                setattr(self, k, self._get_params(data))
            else:
                setattr(self, k, v)

        err = check_template(self.fields)
        if err:
            raise ValidationError(f'Template check error: {err}')
        else:
            if "user_specified_errors" in data:
                for key, value in data["user_specified_errors"].items():
                    for i, item in enumerate(value):
                        try:
                            r_item = int(item)
                        except Exception:
                            r_item = item
                        value[i] = r_item
                    data["user_specified_errors"][key] = value
                self.fields["user_specified_errors"] = data["user_specified_errors"]
        flag_modified(self, "fields")

    def put_check_for_spex(self, name):
        if name and name not in ["basic", self.name] and self.__class__.query.filter_by(
                api_id=self.id, name=name, deleted=False).all():
            raise ValidationError(f'name has existed!')

    def put_check_for_http(self, name):
        if name and name not in ["basic", self.name] and self.__class__.query.filter_by(
                http_api_id=self.id, name=name, deleted=False).all():
            raise ValidationError(f'name has existed!')


class HcTemplateSchema(ma.ModelSchema):
    class Meta:
        unknown = INCLUDE
        model = HcTemplate
        fields = ('author', 'name', 'fields', 'api_id', 'params', 'default_request', 'combination_rules',
                  'user_specified_errors', 'api_type')


class HttpTemplateSchema(ma.ModelSchema):
    class Meta:
        model = HcTemplate
        fields = ('author', 'name', 'fields', 'http_api_id', 'url', 'default_request', 'combination_rules',
                  'user_specified_errors', 'api_type')


class HcTemplatesSchema(ma.ModelSchema):
    class Meta:
        model = HcTemplate
        fields = ('id', 'name', 'type', 'author', 'is_default')


class HcTemplateDetailSchema(ma.ModelSchema):
    class Meta:
        model = HcTemplate
        fields = ('name', 'service_name', 'topic', 'command', 'request', 'default_request',
                  'combination_rules', 'params', 'user_specified_errors')

    service_name = fields.Method("get_service_name")
    topic = fields.Method("get_topic")
    command = fields.Method("get_command")
    request = fields.Method("get_request")
    default_request = fields.Method("get_default_request")
    combination_rules = fields.Method("get_combination_rules")
    params = fields.Method("get_params")
    user_specified_errors = fields.Function(lambda obj: obj.fields.get("user_specified_errors", {}))

    def get_params(self, obj):
        ret = {
            "requestType": {}
        }
        if obj.params:
            param_type = list(obj.params.keys())[0]
            param_value = list(obj.params.values())[0]
            ret["requestType"] = {
                "type": param_type,
                "value": param_value
            }
        return ret

    def get_service_name(self, obj):
        return obj.api.service.name

    def get_topic(self, obj):
        return obj.api.topic

    def get_command(self, obj):
        return obj.api.name

    def get_request(self, obj):
        structurize_template(obj.fields)
        return obj.fields.get("request", {})

    def get_default_request(self, obj):
        return obj.fields.get("default_request", "{}")

    def get_combination_rules(self, obj):
        return obj.fields.get("combination_rules", [])


class HttpTemplateDetailSchema(ma.ModelSchema):
    class Meta:
        model = HcTemplate
        fields = ('name', 'path', 'header', 'query', 'request', 'default_request', 'combination_rules',
                  'user_specified_errors')

    request = fields.Method("get_request")
    path = fields.Function(lambda obj: obj.http_api.get_path_with_params())
    header = fields.Function(lambda obj: obj.http_api.get_header_dict())
    query = fields.Function(lambda obj: obj.http_api.get_query_dict())
    default_request = fields.Function(lambda obj: obj.fields.get("default_request", "{}"))
    combination_rules = fields.Function(lambda obj: obj.fields.get("combination_rules", "{}"))
    user_specified_errors = fields.Function(lambda obj: obj.fields.get("user_specified_errors", {}))

    def get_request(self, obj):
        structurize_template(obj.fields)
        return obj.fields.get("request", {})


hc_template_schema = HcTemplateSchema()
hc_templates_schema = HcTemplatesSchema()
hc_template_detail_schema = HcTemplateDetailSchema()
http_template_schema = HttpTemplateSchema()
http_template_detail_schema = HttpTemplateDetailSchema()
