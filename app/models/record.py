# -*- coding: utf-8 -*-
# @Time    : 2020/8/4
# @Author  : Arrow

from .mixins import TimestampMixin
from app.commons import db, ma
from marshmallow import Schema, fields, validate, validates, ValidationError
from psycopg2.errors import UniqueViolation
from .common_check import CommonCheck


class Record(CommonCheck, TimestampMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    model = db.Column(db.String(127), nullable=False)
    method = db.Column(db.String(127), nullable=False)
    path = db.Column(db.String(127), nullable=False)
    original_data = db.Column(db.JSON, nullable=True)
    update_data = db.Column(db.JSON, nullable=True)
    request_data = db.Column(db.JSON, nullable=True)


class RecordSchema(ma.ModelSchema):
    class Meta:
        model = Record
        fields = ('author', 'created_time', 'id',
                  'name', 'model', 'method', 'path', 'original_data', 'update_data', 'request_data')


record_schema = RecordSchema()
