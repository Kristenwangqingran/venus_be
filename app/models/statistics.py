# -*- coding: utf-8 -*-
# @Time    : 2022/3/17
# @Author  : Chen Jiaxin

from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck


class Statistic(CommonCheck, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=True)
    project_data = db.Column(db.JSON, nullable=True)
    author_data = db.Column(db.JSON, nullable=True)
    project_exec_data = db.Column(db.JSON, nullable=True)
    author_exec_data = db.Column(db.JSON, nullable=True)


class StatisticSchema(ma.ModelSchema):
    class Meta:
        model = Statistic
        fields = ('id', 'project_data', 'author_data')


class ExecStatSchema(ma.ModelSchema):
    class Meta:
        model = Statistic
        fields = ('id', 'project_exec_data', 'author_exec_data')


statistic_schema = StatisticSchema()
exec_stat_schema = ExecStatSchema()
