# -*- coding: utf-8 -*-
# @Time    : 2021/1/24
# @Author  : Chen Jiaxin

from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck


class SpexApi(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = "spexapi"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    description = db.Column(db.Text, nullable=True, default='Please give me some words...')
    topic = db.Column(db.String(127), nullable=False)
    req_name = db.Column(db.String(127), nullable=False)
    request = db.Column(db.JSON, nullable=True)
    resp_name = db.Column(db.String(127), nullable=False)
    response = db.Column(db.JSON, nullable=True)
    errors = db.Column(db.JSON, nullable=True)
    health_degree = db.Column(db.Float, nullable=True, default=0)

    service_id = db.Column(db.Integer, db.ForeignKey('spexservice.id'), nullable=True)
    service = db.relationship('SpexService', backref=db.backref('apis', lazy=True), lazy='select',
                              cascade="save-update, merge, refresh-expire, expunge", single_parent=True)


class SpexApiSchema(ma.ModelSchema):
    class Meta:
        model = SpexApi
        fields = ('author', 'created_time', 'updated_time', 'id', 'name', 'description',
                  'topic', 'req_name', 'resp_name', 'request', 'response', 'errors', 'health_degree', 'service_id')


class SpexApiOverviewSchema(ma.ModelSchema):
    class Meta:
        model = SpexApi
        fields = ('id', 'name', 'health_degree')


spex_api_schema = SpexApiSchema()
spex_api_overview_schema = SpexApiOverviewSchema()
