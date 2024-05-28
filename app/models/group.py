# -*- coding: utf-8 -*-
# @Time    : 2020/8/27
# @Author  : GongXun

from .mixins import TimestampMixin
from app.commons import db, ma
from marshmallow import Schema, fields, validate, validates, ValidationError
from psycopg2.errors import UniqueViolation
from .common_check import CommonCheck


class Group(CommonCheck, TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint('project_id', 'name', 'mum_id',
                            name='group_unique_peer_project'),
    )
    name = db.Column(db.String(127), nullable=False)
    description = db.Column(db.Text, nullable=True,
                            default='Please give me some words...')
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)

    mum_id = db.Column(
        db.Integer, db.ForeignKey('group.id'), nullable=True)
    mum = db.relationship('Group', backref=db.backref(
        'children', lazy='select'), remote_side='Group.id', lazy='select')

    @classmethod
    def post_check(cls, data):
        if data.get("mum_id", None) and Group.query.filter_by(id=data["mum_id"], project_id=data["project_id"]).count() != 1:
            raise ValidationError(f'Mum Group no exists!')

    def put_check(self, data):
        if data.get("mum_id", None):
            if Group.query.filter_by(id=data["mum_id"], project_id=self.project_id).count() < 1:
                raise ValidationError(f'Mum Group no exists!')
            elif data["mum_id"] == self.id:
                raise ValidationError(f'Mum Group can not be self!')
            else:
                grandmas = self.get_grandmas(data["mum_id"])
                if self.id in grandmas:
                    raise ValidationError(f'Group cycle detected!')

    def get_grandmas(self, group_id):
        results = []
        group = Group.query.get(group_id)
        if group.mum:
            results.append(group.mum_id)
            results += self.get_grandmas(group.mum_id)

        return results


class GroupSchema(ma.ModelSchema):
    class Meta:
        model = Group
        fields = ('author', 'created_time', 'updated_time', 'id',
                  'name', 'description', 'mum_id', 'project_id')


group_schema = GroupSchema()
