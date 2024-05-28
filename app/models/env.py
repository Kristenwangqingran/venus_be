# -*- coding: utf-8 -*-
# @Time    : 2020/8/4
# @Author  : Arrow

from .mixins import TimestampMixin
from app.commons import db, ma
from marshmallow import Schema, fields, validate, validates, ValidationError
from psycopg2.errors import UniqueViolation
from .common_check import CommonCheck


class Env(CommonCheck, TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint('project_id', 'name',
                            name='env_unique_peer_project'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    description = db.Column(db.Text, nullable=True,
                            default='Please give me some words...')
    host = db.Column(db.String(127), nullable=False)

    DBs = db.Column(db.JSON, nullable=True)
    extra = db.Column(db.JSON, nullable=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=True)


class EnvSchema(ma.ModelSchema):
    class Meta:
        model = Env
        fields = ('author', 'created_time', 'updated_time', 'id',
                  'name', 'description', 'extra', 'project_id', 'host', 'DBs')


env_schema = EnvSchema()
