# -*- coding: utf-8 -*-
# @Time    : 2022/4/13
# @Author  : Jiaxin Chen

import json
from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck
from marshmallow import ValidationError, fields, post_load


class PostWomenTemplate(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'postwomantemplate'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    description = db.Column(db.Text, nullable=True,
                            default='Please give me some words...')
    request = db.Column(db.JSON, nullable=False)
    is_demo = db.Column(db.Boolean, default=False)

    # for http
    protocol = db.Column(db.String(127), nullable=True)
    method = db.Column(db.String(127), nullable=True)
    url = db.Column(db.String(127), nullable=True)
    headers = db.Column(db.JSON, nullable=True)

    api_id = db.Column(db.Integer, db.ForeignKey('spexapi.id'), nullable=True)
    api = db.relationship('SpexApi', backref=db.backref('pw_templates', lazy=True), lazy='select',
                          cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    @classmethod
    def save_check(cls, data):
        if 'name' in data and not data['name']:
            raise ValidationError(f'name cannot be empty!')

        if data.get('name', '') and \
                len(cls.query.filter_by(
                    api_id=data["api_id"], name=data["name"], protocol=data["protocol"], deleted=False).all()) > 0:
            if data.get('origin_name') and data['name'] != data['origin_name']:
                # put
                raise ValidationError(f'name has existed!')
            elif not data.get('origin_name'):
                # post
                raise ValidationError(f'name has existed!')

        if data.get('is_demo', False) \
                and len(cls.query.filter_by(
                    api_id=data["api_id"], is_demo=True, protocol=data['protocol'], deleted=False).all()) > 0:
            raise ValidationError(f'demo has existed!')

    def post_save(self, ):
        self.save_check({
            "api_id": self.api_id,
            "name": self.name,
            "is_demo": self.is_demo,
            "protocol": self.protocol
        })

        super().save()

    def put_save(self, data):
        for item in ['request', 'headers']:
            if data.get(item) and isinstance(data[item], str):
                data[item] = json.loads(data[item])

        self.save_check({
            "api_id": self.api_id,
            "origin_name": self.name,
            "protocol": self.protocol or 'spex',
            ** data
        })

        super().put_save(data)


class PostWomenTemplatesSchema(ma.ModelSchema):
    class Meta:
        model = PostWomenTemplate
        fields = ('id', 'name', 'author', 'description', 'updated_time', 'request',
                  'is_demo', 'method', 'url', 'headers', 'protocol')

    request = fields.Function(lambda obj: json.dumps(obj.request, indent=2))
    headers = fields.Function(lambda obj: json.dumps(obj.headers, indent=2) if obj.protocol == 'http' else '{}')
    protocol = fields.Function(lambda obj: 'http' if obj.protocol and obj.protocol == 'http' else 'spex')


class PostWomenTemplateDetailSchema(ma.ModelSchema):
    class Meta:
        model = PostWomenTemplate
        fields = ('id', 'name', 'description', 'topic', 'request', 'url', 'method', 'headers')

    topic = fields.Function(lambda obj: obj.api.topic)
    request = fields.Function(lambda obj: json.dumps(obj.request, indent=2))
    headers = fields.Function(lambda obj: json.dumps(obj.headers if obj.headers else {}, indent=2))


class PostWomenTemplateSchema(ma.Schema):
    name = fields.String()
    author = fields.String()
    description = fields.String()
    request = fields.String()
    api_id = fields.Integer()
    is_demo = fields.Boolean()
    protocol = fields.String()
    method = fields.String()
    url = fields.String()
    headers = fields.String()

    @post_load
    def make_template(self, data, **kwargs):
        req = json.loads(data.get('request', '{}'))
        data['request'] = req
        headers = json.loads(data.get('headers', '{}'))
        data['headers'] = headers
        template = PostWomenTemplate(**data)
        return template


postwomen_templates_schema = PostWomenTemplatesSchema()
postwomen_template_detail_schema = PostWomenTemplateDetailSchema()
postwomen_template_schema = PostWomenTemplateSchema()
