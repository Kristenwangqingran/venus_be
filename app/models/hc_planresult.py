# -*- coding: utf-8 -*-
# @Time    : 2022/2/28
# @Author  : Jiaxin Chen

import os
from flask import current_app
from .mixins import TimestampMixin, TaskStatus
from app.commons import db, ma
from .common_check import CommonCheck
from marshmallow import fields
from app.models import Run_Log_Type


class HcPlanResult(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'hcplanresult'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(127), nullable=False,
                       default=TaskStatus["pending"])
    runner = db.Column(db.String(127), nullable=False)
    html = db.Column(db.String(127), nullable=False)

    total = db.Column(db.Integer, nullable=False, default=0)
    pass_num = db.Column(db.Integer, nullable=False, default=0)
    fail_num = db.Column(db.Integer, nullable=False, default=0)

    finish_rate = db.Column(db.Float, nullable=True)

    extra = db.Column(db.JSON, nullable=True, default={})
    api_type = db.Column(db.String(127), default="spex")

    plan_id = db.Column(db.Integer, db.ForeignKey('hcplan.id'), nullable=True)
    plan = db.relationship('HcPlan', backref=db.backref('results', lazy=True), lazy='select',
                           cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    http_plan_id = db.Column(db.Integer, db.ForeignKey('http_plan.id'), nullable=True)
    http_plan = db.relationship('HttpPlan', backref=db.backref('results', lazy=True), lazy='select',
                           cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    def put_check(self, data):
        for k, v in data.items():
            setattr(self, k, v)
        self.save()


class HcPlanResultsSchema(ma.ModelSchema):
    class Meta:
        model = HcPlanResult
        fields = ('id', 'name', 'runner', 'created_time', 'updated_time', 'finish_rate',
                  'status', 'html', 'plan_name', 'plan_id', 'logs', 'api_type')

    api_type = fields.Function(lambda obj: obj.api_type if obj.api_type else "spex")
    plan_id = fields.Function(lambda obj: obj.http_plan.id if obj.http_plan else obj.plan.id)
    plan_name = fields.Method("get_plan_name")
    logs = fields.Method("get_logs")

    def get_plan_name(self, obj):
        return obj.http_plan.name if obj.http_plan_id else obj.plan.name

    def get_logs(self, obj):
        logs = []
        base_dir = os.path.join(current_app.instance_path, current_app.config['LOG_FOLDER'])
        be_log = os.path.join(base_dir, Run_Log_Type["suite"], f'HC{str(obj.id)}.log')
        executor_log = os.path.join(base_dir, current_app.config['HC_PATH'], str(obj.id), 'run.log')
        for index, log_info in enumerate([["BE_log", be_log], ["EXEC_log", executor_log]]):
            if os.path.exists(log_info[1]):
                logs.append({
                    "key": index,
                    "title": log_info[0],
                    "url": log_info[1].replace(base_dir, current_app.config['TOMCAT_HOST'])
                })
        return logs


hc_plan_result_schema = HcPlanResultsSchema()
