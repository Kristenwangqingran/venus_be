# -*- coding: utf-8 -*-
# @Time    : 2020/8/6
# @Author  : Arrow
from flask import current_app
from .mixins import TimestampMixin
from app.commons import db, ma
from marshmallow import Schema, fields, validate, validates, ValidationError
from psycopg2.errors import UniqueViolation
from .page import Page
from .project import Project
from .common_check import CommonCheck


class Element(CommonCheck, TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint('project_id', 'alias',
                            name='alias_unique_peer_project'),
    )

    alias = db.Column(db.String(200), nullable=False)
    memo = db.Column(db.String(200), nullable=True)
    locator = db.Column(db.JSON, nullable=False, default={})

    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=True)
    project = db.relationship('Project', backref=db.backref('elements', lazy=True), lazy='select',
                              cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    page_id = db.Column(
        db.Integer, db.ForeignKey('page.id'), nullable=True)
    page = db.relationship('Page', backref=db.backref('elements', lazy=True), lazy='select',
                           cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    @classmethod
    def post_check(cls, data):
        if data.get("page_id", None) and Page.query.filter_by(id=data["page_id"], project_id=data["project_id"]).count() != 1:
            raise ValidationError(f'page no exist!')
        else:
            items = Element.query.filter(
                Element.project_id == data["project_id"], Element.alias == data["alias"]).all()
            for item in items:
                if item.deleted == True:
                    item.rdelete()
                else:
                    raise UniqueViolation(f'Resource already exists!')

    def put_check(self, data):

        if data.get("page_id", None) and Page.query.filter_by(id=data["page_id"], project_id=data.get('project_id', self.project_id)).count() != 1:
            raise ValidationError(f'page no exist!')
        else:
            items = Element.query.filter(
                Element.project_id == data.get("project_id", self.project_id), Element.alias == data.get("alias", self.alias)).all()
            for item in items:
                if item.id != self.id:
                    if item.deleted == True:
                        item.rdelete()
                    else:
                        raise UniqueViolation(f'Resource already exists!')


class ElementSchema(ma.ModelSchema):
    class Meta:
        model = Element
        fields = ('author', 'created_time', 'updated_time', 'id',
                  'alias', 'memo', 'locator', 'project_id', 'page_id')

    @validates('locator')
    def validate_locator(self, value):
        normal = {
            # "xpath": "",
            # "id": "",
            # "css_selector": "",
            # "class_name": "",
        }
        errors = []
        for k, v in normal.items():
            if k in value:
                if isinstance(value[k], type(v)):
                    pass
                else:
                    errors.append(
                        f"{k}: value has wrong type! [{type(value[k])} != {type(v)}]")
            else:
                errors.append(f"{k} missed!")

        if errors:
            raise ValidationError(errors)


element_schema = ElementSchema()
