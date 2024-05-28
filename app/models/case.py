# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Arrow

from .mixins import ExecutorType, PriorityType, CaseType
from app.commons import db, ma
from marshmallow import validates, ValidationError, fields
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
from psycopg2.errors import UniqueViolation
from .project import Project
from .caseresult import CaseResult
from .group import Group
from .common_check import CommonCheck


class Case(CommonCheck, db.Model):
    __table_args__ = (
        db.UniqueConstraint('project_id', 'group_id', 'name',
                            name='case_unique_peer_project'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=True,
                            default='Please give me some words...')

    category = db.Column(db.String(32), nullable=False,
                         default=ExecutorType["pfc"])
    manual_case_id = db.Column(db.Integer, nullable=True, default=0)
    timeout = db.Column(db.Integer, nullable=True, default=1800)

    type = db.Column(db.String(32), nullable=True)

    priority = db.Column(db.String(16), nullable=False,
                         default=PriorityType["P0"])
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=True)
    project = db.relationship('Project', backref=db.backref('cases', lazy=True), lazy='select',
                              cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    caseresults = db.relationship('CaseResult', backref=db.backref(
        'case', lazy=True), lazy='select', cascade="all, delete-orphan", passive_deletes=True)

    group_id = db.Column(
        db.Integer, db.ForeignKey('group.id'), nullable=True)
    group = db.relationship('Group', backref=db.backref('cases', lazy=True), lazy='select',
                            cascade="save-update, merge, refresh-expire, expunge", single_parent=True)
    base_group = db.Column(db.String, nullable=True)

    extra = db.Column(db.JSON, nullable=False, default={})

    inputs = db.Column(db.JSON, nullable=True, default={})
    outputs = db.Column(db.JSON, nullable=True, default={})
    is_draft = db.Column(db.Boolean, nullable=True, default=True)

    apis = db.Column(MutableList.as_mutable(
        ARRAY(db.String)), nullable=True, default=[])

    @classmethod
    def post_check(cls, data):

        if data.get("name", None) is None or data.get("project_id", None) is None or data.get("group_id", None) is None:
            raise ValidationError(f'name or project or group arg missing!')
        else:
            items = cls.query.filter(
                cls.project_id == data["project_id"], cls.group_id == data["group_id"], cls.name == data["name"]).all()
            for item in items:
                if item.deleted == True:
                    item.rdelete()
                else:
                    raise UniqueViolation(f'Resource already exists!')

        if data.get("category", None) is None or data["category"].lower() not in ExecutorType:
            raise ValidationError(f'category no exist!')

        if data.get("group_id", None) and Group.query.filter_by(id=data["group_id"], project_id=data["project_id"]).count() != 1:
            raise ValidationError(f'group no exist!')

    def put_check(self, data):
        if data.get("category", None) and data["category"].lower() not in ExecutorType:
            raise ValidationError(f'category no exist!')

        if data.get("group_id", None) is None or Group.query.filter_by(id=data["group_id"], project_id=data.get('project_id', self.project_id)).count() != 1:
            raise ValidationError(f'group no exist!')

    def get_base_group(self):
        self.save()
        if self.base_group:
            return self.base_group

        ret = ''
        groups = self.group.get_grandmas(self.group_id)
        if len(groups) > 1:
            target_group_id = groups[-2]
            target_group = Group.query.get(target_group_id)
            ret = target_group.name
        elif len(groups) == 1:
            target_group_id = self.group_id
            target_group = Group.query.get(target_group_id)
            ret = target_group.name
        else:
            ret = self.project.name

        self.base_group = ret
        self.save()
        return ret


class CaseSchema(ma.ModelSchema):
    class Meta:
        model = Case
        fields = ('author', 'created_time', 'updated_time', 'id', 'name', 'description', 'category',
                  'type', 'priority', 'project_id', 'group_id', 'extra', "inputs", "outputs", "timeout",
                  "manual_case_id", 'is_draft', 'apis')


case_schema = CaseSchema()


class SimpleCaseSchema(ma.ModelSchema):
    class Meta:
        model = Case
        fields = ('author', 'created_time', 'updated_time', 'id', 'name', 'description', 'category',
                  'type', 'priority', 'project_id', 'group_id', "inputs", "outputs", "manual_case_id", "apis")

    apis = fields.Function(lambda obj: obj.apis if obj.apis else [])


simplecase_schema = SimpleCaseSchema()
