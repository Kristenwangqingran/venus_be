# -*- coding: utf-8 -*-
# @Time    : 2020/8/27
# @Author  : GongXun

from .mixins import TimestampMixin
from app.commons import db, ma
from marshmallow import Schema, fields, validate, validates, ValidationError
from psycopg2.errors import UniqueViolation
from .common_check import CommonCheck


class Page(CommonCheck, TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint('project_id', 'name',
                            name='page_unique_peer_project'),
    )
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    description = db.Column(db.Text, nullable=True,
                            default='Please give me some words...')
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)

    mum_id = db.Column(
        db.Integer, db.ForeignKey('page.id'), nullable=True)
    mum = db.relationship('Page', backref=db.backref(
        'children', lazy='select'), remote_side='Page.id', lazy='select')

    @classmethod
    def post_check(cls, data):
        super().post_check(data)

        if data.get("mum_id", None) and Page.query.filter_by(id=data["mum_id"], project_id=data["project_id"]).count() != 1:
            raise ValidationError(f'Mum no exists!')

    def put_check(self, data):
        super().put_check(data)

        if data.get("mum_id", None):
            if Page.query.filter_by(id=data["mum_id"], project_id=self.project_id).count() < 1:
                raise ValidationError(f'Mum no exists!')
            elif data["mum_id"] == self.id:
                raise ValidationError(f'Mum can not be self!')
            else:
                grandmas = self.get_grandmas(data["mum_id"])
                if self.id in grandmas:
                    raise ValidationError(f'Cycle detected!')

    def get_grandmas(self, id):
        results = []
        item = Page.query.get(id)
        if item.mum:
            results.append(item.mum_id)
            results += self.get_grandmas(item.mum_id)

        return results


class PageSchema(ma.ModelSchema):
    class Meta:
        model = Page
        fields = ('author', 'created_time', 'updated_time', 'id',
                  'name', 'description', 'mum_id', 'project_id')


page_schema = PageSchema()
