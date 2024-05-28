# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Arrow

from marshmallow import validates, fields, INCLUDE

from app.commons import db, ma
from .common_check import CommonCheck
from .mixins import TimestampMixin


class Casesuite(CommonCheck, TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint('project_id', 'name',
                            name='suite_unique_peer_project'),
    )
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    description = db.Column(db.Text, nullable=True,
                            default='Please give me some words...')
    case_id_list = db.Column(db.JSON, nullable=True, default=[])
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=True)
    # project = db.relationship('Project', backref=db.backref('casesuites', lazy=True), lazy='select',
    #                           cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    # results = db.relationship('SuiteResult', backref=db.backref(
    #     'casesuite', lazy=True), lazy='select', cascade="all, delete-orphan", passive_deletes=True)

    # use for schedule
    schedule = db.Column(db.JSON, nullable=True)
    plan = db.Column(db.JSON, nullable=True, default={})
    noti = db.Column(db.JSON, nullable=True)
    runtime_config = db.Column(db.JSON, nullable=True, default={})
    run_all_config = db.Column(db.JSON, nullable=True, default={})

    # use for testing offline coverage
    is_manual = db.Column(db.Boolean, default=False)


class CasesuiteSchema(ma.ModelSchema):
    class Meta:
        unknown = INCLUDE
        model = Casesuite
        fields = ('author', 'created_time', 'updated_time', 'id',
                  'name', 'description', 'case_id_list', 'project_id', 'schedule', "plan", "noti",
                  'runtime_config', 'is_manual', 'run_all_config')

    is_manual = fields.Function(lambda obj: False if not obj.is_manual else True)

    @validates('plan')
    def validate_plan(self, value):
        template = {
            "sequence": {
                # case_id0: [case_idm, case_idn],
                # case_id1: [case_idx, case_idy],
            },
            "dependency": {
                # case_id0: {
                #     "a": "case_idm.x",
                #     "b": "case_idm.y",
                # }
            },
            "must_serial": [],
            # "run_all_case": ["project_id"]
        }

    # @validates('schedule')
    # def validate_schedule(self, value):
    #     normal = {
    #         'status': "disabled",  # disabled/enabled
    #         'trigger': "interval",  # interval/cron
    #         'time_info': {
    #             # if trigger is interval, only needs seconds
    #             'seconds': 1,

    #             # if trigger is cron, need parts of below info:
    #             'year': 2020,
    #             'month': 1,
    #             'day_of_week': 1,
    #             'day': 1,
    #             'hour': 1,
    #             'minute': 1,
    #             'second': 1
    #         },
    #         'env_id': 0
    #     }
    #     errors = []
    #     if value:
    #         for k, v in normal.items():
    #             if k in value:
    #                 if isinstance(value[k], type(v)):
    #                     pass
    #                 else:
    #                     errors.append(
    #                         f"{k}: value has wrong type! [{type(value[k])} != {type(v)}]")
    #             else:
    #                 errors.append(f"{k} missed!")

    #     if errors:
    #         raise ValidationError(errors)
    #     else:
    #         if value.get('status', '') not in ['disabled', 'enabled']:
    #             errors.append(f"status value wrong: {['disabled', 'enabled']}")

    #         if value.get('trigger', '') not in ['interval', 'cron']:
    #             errors.append(f"status value wrong: {['interval', 'cron']}")

    #         if value.get('trigger', '') == 'interval':
    #             pass

    #         elif value.get('trigger', '') == 'cron':
    #             pass

    #         if errors:
    #             raise ValidationError(errors)


casesuite_schema = CasesuiteSchema()
