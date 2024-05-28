# -*- coding: utf-8 -*-
# @Time    : 2022/2/28
# @Author  : Jiaxin Chen

from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck
from marshmallow import ValidationError, fields, INCLUDE
from . import SpexApi, HcTemplate, SpexService
from .http_project import HttpProject
from .http_env import HttpEnv


class HcPlan(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'hcplan'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    topic = db.Column(db.String(127), nullable=False)
    command = db.Column(db.ARRAY(db.String(127)), nullable=True)
    env = db.Column(db.String, nullable=False)
    config_key = db.Column(db.String(127), nullable=False)
    server_name = db.Column(db.String(127), nullable=True)
    params = db.Column(db.JSON, nullable=True, default={})

    service_id = db.Column(db.Integer, db.ForeignKey('spexservice.id'), nullable=True)
    service = db.relationship('SpexService', backref=db.backref('plans', lazy=True), lazy='select',
                              cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

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
        if not data.get('service_id', None):
            raise ValidationError(f"service_id is required!")

        if not data.get('name', None):
            raise ValidationError(f"name is required!")

        if cls.query.filter_by(service_id=data["service_id"], name=data["name"], deleted=False).all():
            raise ValidationError(f'name has existed!')

        if not data.get("config_key", None):
            raise ValidationError(f'Config key is required!')

        if not data.get("server_name", None):
            raise ValidationError(f'server_name is required!')

        data['params'] = cls._get_params(data)

    def put_check(self, data):
        name = data.get("name", "")
        if name and name != self.name and self.__class__.query.filter_by(name=name, deleted=False).all():
            raise ValidationError(f'name has existed!')

        for k, v in data.items():
            if k == 'params':
                setattr(self, k, self._get_params(data))
            else:
                setattr(self, k, v)

    def save(self):
        service = SpexService.query.get(self.service_id)
        apis_name = list(map(lambda name: name.replace(f'{service.path}.{service.name}', ''), self.command))
        templates = HcTemplate.query.join(SpexApi, HcTemplate.api_id == SpexApi.id).filter(
            SpexApi.service_id == self.service_id,
            SpexApi.topic == self.topic,
            SpexApi.name.in_(apis_name)
        ).all()
        if not self.params:
            plan_param = None
        elif self.params.get('pfb'):
            plan_param = 'pfb'
        else:
            plan_param = 'cid'
        for template in templates:
            if not template.params:
                template_param = None
            elif template.params.get('pfb'):
                template_param = 'pfb'
            else:
                template_param = 'cid'
            if plan_param and template_param and plan_param != template_param:
                raise ValidationError(f"Conflict: plan param is {plan_param} "
                                      f"while {template.api.name} template {template.name} is {template_param}")
        super().save()


class HttpPlan(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'http_plan'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    apis = db.Column(db.ARRAY(db.Integer), nullable=True)

    env_id = db.Column(db.Integer, db.ForeignKey('http_env.id'))
    env = db.relationship('HttpEnv', backref=db.backref('plans', lazy=True), lazy='select',
                          cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    http_project_id = db.Column(db.Integer, db.ForeignKey('http_project.id'))
    http_project = db.relationship('HttpProject', backref=db.backref('plans', lazy=True), lazy='select',
                                   cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    @classmethod
    def post_check(cls, data):
        if not data.get('name', None):
            raise ValidationError(f"name is required!")

        if cls.query.filter_by(http_project_id=data["http_project_id"], name=data["name"], deleted=False).all():
            raise ValidationError(f'name has existed!')

    def put_check(self, data):
        name = data.get("name", "")
        if name and name != self.name and self.__class__.query.filter_by(name=name, deleted=False).all():
            raise ValidationError(f'name has existed!')

        for k, v in data.items():
            setattr(self, k, v)

    def generate_url_and_header(self, api_path, api_params, api_headers):
        for param in api_params:
            if param.get('example'):
                api_path = api_path.replace('{' + param['name'] + '}', param['example'])
        url = self.env.domain + api_path

        final_header = {h['name']: h['value'] for h in self.env.headers}
        for header in api_headers:
            final_header[header['name']] = header['value']
        header = final_header

        return url, header

    def rdelete(self):
        for plan_result in self.results:
            plan_result.rdelete()
        super().rdelete()


class SpexPlansSchema(ma.ModelSchema):
    class Meta:
        model = HcPlan
        fields = ('id', 'name', 'author', 'updated_time')


class HttpPlansSchema(ma.ModelSchema):
    class Meta:
        model = HttpPlan
        fields = ('id', 'name', 'author', 'updated_time')


class HcPlanDetailSchema(ma.ModelSchema):
    class Meta:
        unknown = INCLUDE
        model = HcPlan
        fields = ('name', 'author', 'service_id', 'service_name', 'service_path', 'topic', 'command',
                  'env', 'server_name', 'config_key', 'params')

    service_name = fields.Method("_get_service_name")
    service_path = fields.Method("_get_service_path")
    params = fields.Method("get_params")

    def get_params(self, obj):
        ret = {
            "requestType": dict()
        }
        if obj.params:
            param_type = list(obj.params.keys())[0]
            param_value = list(obj.params.values())[0]
            ret["requestType"] = {
                "type": param_type,
                "value": param_value
            }
        return ret

    def _get_service_name(self, obj):
        return obj.service.name

    def _get_service_path(self, obj):
        return obj.service.path


class HttpPlanDetailSchema(ma.ModelSchema):
    class Meta:
        unknown = INCLUDE
        model = HttpPlan
        fields = ('name', 'author', 'env_id', 'http_project_id', 'http_project_name', 'apis')

    http_project_name = fields.Method("_get_http_project_name")

    def _get_http_project_name(self, obj):
        return obj.http_project.name


hc_plans_schema = SpexPlansSchema()
hc_plan_detail_schema = HcPlanDetailSchema()
http_plans_schema = HttpPlansSchema()
http_plan_detail_schema = HttpPlanDetailSchema()
