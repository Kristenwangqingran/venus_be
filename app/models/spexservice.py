# -*- coding: utf-8 -*-
# @Time    : 2021/1/24
# @Author  : Chen Jiaxin

from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck
from marshmallow import fields
from sqlalchemy.orm.attributes import flag_modified


class SpexService(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'spexservice'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    description = db.Column(db.Text, nullable=True, default='Please give me some words...')
    path = db.Column(db.String(127), nullable=True)
    topics = db.Column(db.ARRAY(db.String(127)), nullable=True)
    test_topic = db.Column(db.String(127), nullable=True)
    uat_topic = db.Column(db.String(127), nullable=True)
    live_topic = db.Column(db.String(127), nullable=True)
    space_id = db.Column(db.Integer, nullable=True)
    info = db.Column(db.JSON, nullable=True)
    params = db.Column(db.JSON, nullable=True)

    group_id = db.Column(db.Integer, db.ForeignKey('spexservicegroup.id'), nullable=True)
    group = db.relationship('SpexServiceGroup', backref=db.backref('services', lazy=True), lazy='select',
                            cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    def delete(self, ):
        for api in self.apis:
            api.delete()
        db.session.flush()
        self.deleted = True
        db.session.add(self)
        db.session.commit()

    def save(self, ):
        if self.params:
            flag_modified(self, "params")
        super().save()


class SpexServiceSchema(ma.ModelSchema):
    class Meta:
        model = SpexService
        fields = ('author', 'created_time', 'updated_time', 'id', 'name', 'description',
                  'topics', 'test_topic', 'uat_topic', 'live_topic', 'group_id', 'path', 'space_id', 'info')


class SpexServiceQuerySchema(ma.ModelSchema):
    class Meta:
        fields = ('id', 'name', 'path')


class SpexServiceDetailSchema(ma.ModelSchema):
    class Meta:
        fields = ('id', 'name', 'error_code_range', 'create_time', 'update_time', 'type')

    error_code_range = fields.Method("get_error")
    create_time = fields.Method("get_create_time")
    update_time = fields.Method("get_update_time")
    type = fields.Method("get_type")

    def get_error(self, obj):
        return obj.info.get("error_code_range", {})

    def get_create_time(self, obj):
        return obj.info.get("create_time", "-")

    def get_update_time(self, obj):
        return obj.info.get("update_time", "-")

    def get_type(self, obj):
        return "service"


spex_service_schema = SpexServiceSchema()
spex_service_query_schema = SpexServiceQuerySchema()
spex_service_detail_schema = SpexServiceDetailSchema()
