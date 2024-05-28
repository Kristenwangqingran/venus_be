# -*- coding: utf-8 -*-
# @Time    : 2021/1/24
# @Author  : Chen Jiaxin

from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck
from marshmallow import fields


class SpexServiceGroup(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'spexservicegroup'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    description = db.Column(db.Text, nullable=True, default='Please give me some words...')
    path = db.Column(db.String(127), nullable=True)
    space_id = db.Column(db.Integer, nullable=True)
    info = db.Column(db.JSON, nullable=True)

    mum_id = db.Column(db.Integer, db.ForeignKey('spexservicegroup.id'), nullable=True)
    mum = db.relationship('SpexServiceGroup', backref=db.backref(
        'children', lazy='select'), remote_side='SpexServiceGroup.id', lazy='select')


class SpexServiceGroupSchema(ma.ModelSchema):
    class Meta:
        model = SpexServiceGroup
        fields = ('author', 'created_time', 'updated_time', 'id', 'name', 'space_id', 'mum_id',
                  'path', 'description', 'info')


class SpexServiceGroupDetailSchema(ma.ModelSchema):
    class Meta:
        model = SpexServiceGroup
        fields = ('id', 'name', 'create_time', 'update_time', 'type')

    create_time = fields.Method("get_create_time")
    update_time = fields.Method("get_update_time")
    type = fields.Method("get_type")

    def get_create_time(self, obj):
        return obj.info.get("create_time", "-")

    def get_update_time(self, obj):
        return obj.info.get("update_time", "-")

    def get_type(self, obj):
        return "group"


spex_service_group_schema = SpexServiceGroupSchema()
spex_service_group_detail_schema = SpexServiceGroupDetailSchema()
