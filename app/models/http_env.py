# -*- coding: utf-8 -*-
# @Time    : 2022/07/18
# @Author  : Chen Jiaxin

from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck
from .http_project import HttpProject


class HttpEnv(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'http_env'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    domain = db.Column(db.String(127), nullable=False)
    headers = db.Column(db.ARRAY(db.JSON), nullable=True)
    yapi_id = db.Column(db.String(127), nullable=False, index=True)

    http_project_id = db.Column(db.Integer, db.ForeignKey('http_project.id'))
    http_project = db.relationship('HttpProject', backref=db.backref('envs', lazy=True), lazy='select',
                                   cascade="save-update, merge, refresh-expire, expunge", single_parent=True)


class HttpEnvsSchema(ma.ModelSchema):
    class Meta:
        model = HttpEnv
        fields = ('id', 'name')


class HttpEnvDetailSchema(ma.ModelSchema):
    class Meta:
        model = HttpEnv
        fields = ('id', 'name', 'domain', 'headers')


http_envs_schema = HttpEnvsSchema()
http_env_detail_schema = HttpEnvDetailSchema()
