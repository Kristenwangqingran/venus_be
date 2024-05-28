# -*- coding: utf-8 -*-
# @Time    : 2022/8/15
# @Author  : Li cheng


from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck
from marshmallow import fields
from .hc_case import HcCase
from .hc_planresult import HcPlanResult


class HcCaseResult(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'hccaseresult'
    id = db.Column(db.Integer, primary_key=True)
    case_type = db.Column(db.String(127), nullable=True)
    status = db.Column(db.String(127), nullable=False)
    runner = db.Column(db.String(127), nullable=False)
    response = db.Column(db.JSON, nullable=True)
    error_code = db.Column(db.JSON, nullable=True)
    fixed = db.Column(db.Boolean, default=False)

    case_id = db.Column(db.Integer, db.ForeignKey('hccase.id'), nullable=True)
    case = db.relationship('HcCase', backref=db.backref('cases', lazy=True), lazy='select',
                           cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    plan_result_id = db.Column(db.Integer, db.ForeignKey('hcplanresult.id'), nullable=True)
    plan_result = db.relationship('HcPlanResult', backref=db.backref('case_results', lazy=True), lazy='select',
                                  cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    def put_save(self, data):
        self.fixed = True
        super().put_save(data)


class HcCaseResultSchema(ma.ModelSchema):
    class Meta:
        model = HcCaseResult
        fields = ('id', 'plan_result_id', 'case_id', 'status', 'runner', 'case_start_time', 'case_finish_time',
                  'response')

    fixed = fields.Function(lambda obj: obj.fixed if obj.fixed in (True, False) else False)


hc_case_result_schema = HcCaseResultSchema()
