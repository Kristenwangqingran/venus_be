# -*- coding: utf-8 -*-
# @Time    : 2022/8/15
# @Author  : Li cheng


from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck
from .spexapi import SpexApi
from .http_api import HttpApi
from .hc_template import HcTemplate


class HcCase(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'hccase'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    case_type = db.Column(db.String(127), nullable=True)
    field_name = db.Column(db.String(127), nullable=True)
    field_type = db.Column(db.String(127), nullable=True)
    request = db.Column(db.JSON, nullable=True)
    expect_response = db.Column(db.JSON, nullable=True)
    expect_errcode = db.Column(db.JSON, nullable=True)

    api_id = db.Column(db.Integer, db.ForeignKey('spexapi.id'), nullable=True)
    api = db.relationship('SpexApi', backref=db.backref('cases', lazy=True), lazy='select',
                          cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    api_type = db.Column(db.String(127), nullable=True, default='spex')
    # for http
    http_api_id = db.Column(db.Integer, db.ForeignKey('http_api.id'), nullable=True)
    http_api = db.relationship('HttpApi', backref=db.backref('cases', lazy=True), lazy='select',
                               cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    template_id = db.Column(db.Integer, db.ForeignKey('hctemplate.id'), nullable=True)
    template = db.relationship('HcTemplate', backref=db.backref('cases', lazy=True), lazy='select',
                               cascade="save-update, merge, refresh-expire, expunge", single_parent=True)


class HcCaseSchema(ma.ModelSchema):
    class Meta:
        model = HcCase
        fields = ('id', 'name', 'case_type', 'field_name', 'field_type', 'created_time', 'updated_time',
                  'request', 'expect_response', 'expect_errcode')


hc_case_schema = HcCaseSchema()
