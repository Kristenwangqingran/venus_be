# -*- coding: utf-8 -*-
# @Time    : 2020/8/5
# @Author  : Arrow

import copy
import os
from flask import current_app
from .mixins import TimestampMixin
from app.commons import db, ma, aps
from marshmallow import fields, ValidationError
from psycopg2.errors import UniqueViolation
from .group import Group
from .env import Env
from .casesuite import Casesuite
from .feature import Feature
from app.commons import get_config

CONF = get_config()


def get_productline(obj):
    product_line = {}
    feature = Feature.query.get(obj.feature_id)
    if feature and not feature.deleted:
        product_line = {
            "product_line": feature.sub_line.product_line.name,
            "sub_line": feature.sub_line.name,
            "feature": feature.name
        }
    return product_line


class Project(TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint('feature_id', 'name', name='unique_peer_feature'),
    )

    ValidStatus = {
        "active": "active",
        "inactive": "inactive"
    }

    manul_cases_count = db.Column(db.Integer, nullable=True)
    auto_cases_count = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(127), nullable=False)
    description = db.Column(db.Text, nullable=True,
                            default='Please give me some words...')
    status = db.Column(db.String(64), nullable=False,
                       default=ValidStatus["active"])

    feature_id = db.Column(db.Integer, nullable=True)

    public_project = db.Column(db.Boolean, default=False)

    # new add to handle the 3rd-party executor
    executor = db.Column(db.String(64), nullable=False,
                         default="default")
    extra = db.Column(db.JSON, nullable=True)
    commit_info = db.Column(db.JSON, nullable=True, default={})

    case_groups = db.relationship('Group', backref=db.backref(
        'project', lazy=True), lazy='select', cascade="all, delete-orphan", passive_deletes=True)

    envs = db.relationship('Env', backref=db.backref(
        'project', lazy=True), lazy='select', cascade="all, delete-orphan", passive_deletes=True)

    suites = db.relationship('Casesuite', backref=db.backref(
        'project', lazy=True), lazy='select', cascade="all, delete-orphan", passive_deletes=True)

    def put_check(self, data):
        from app.models import Feature
        if data.get("feature_id", None) and Feature.query.filter_by(id=data["feature_id"]).count() < 1:
            raise ValidationError(f'feature_id no exist!')

        if data.get("feature_id", None) and data.get("name", None):
            items = self.__class__.query.filter(
                self.__class__.feature_id == data["feature_id"], self.__class__.name == data["name"]).all()
            for item in items:
                if item.id != self.id:
                    if item.deleted == True:
                        item.rdelete()
                    else:
                        raise UniqueViolation(f'Resource already exists!')

    @classmethod
    def post_check(cls, data):
        from app.models import Feature
        if data.get("name", None) is None or data.get("feature_id", None) is None:
            raise ValidationError(f'Name or feature_id missing!')
        elif Feature.query.filter_by(id=data["feature_id"]).count() < 1:
            raise ValidationError(f'feature_id no exist!')
        else:
            items = cls.query.filter(
                cls.feature_id == data["feature_id"], cls.name == data["name"]).all()
            for item in items:
                if item.deleted == True or item.status == 'inactive':
                    item.rdelete()
                else:
                    raise UniqueViolation(f'Resource already exists!')

    def init_dir(self):
        base_dir = os.path.join(current_app.instance_path,
                                current_app.config['PRODUCT_FOLDER'])
        project_dir = os.path.join(base_dir, str(self.id))
        if not os.path.exists(project_dir):
            os.mkdir(project_dir)

        base_dir = os.path.join(current_app.instance_path,
                                current_app.config['LOG_FOLDER'])
        log_dir = os.path.join(base_dir, str(self.id))
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)

    def get_log_path(self):
        base_dir = os.path.join(current_app.instance_path,
                                current_app.config['LOG_FOLDER'])
        log_dir = os.path.join(base_dir, str(self.id))
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        return log_dir

    def get_product_path(self):
        base_dir = os.path.join(current_app.instance_path,
                                current_app.config['PRODUCT_FOLDER'])
        project_dir = os.path.join(base_dir, str(self.id))
        if not os.path.exists(project_dir):
            os.makedirs(project_dir, exist_ok=True)
        return project_dir

    def delete(self):
        if len(self.suites) != 0:
            for case_suite in self.suites:
                if case_suite.schedule and case_suite.schedule.get('status', 'disabled') == "enabled":
                    schedule = copy.deepcopy(case_suite.schedule)
                    schedule['status'] = "disabled"
                    case_suite.schedule = schedule
                    case_suite.save()
                    aps.MYASP.remove_task(task_id=str(case_suite.id))
                case_suite.delete()
        db.session.flush()
        self.deleted = True
        db.session.add(self)
        db.session.commit()

    def rdelete(self):
        if len(self.suites) != 0:
            for case_suite in self.suites:
                if case_suite.schedule and case_suite.schedule.get('status', 'disabled') == "enabled":
                    schedule = copy.deepcopy(case_suite.schedule)
                    schedule['status'] = "disabled"
                    case_suite.schedule = schedule
                    case_suite.save()
                    aps.MYASP.remove_task(task_id=str(case_suite.id))
                case_suite.rdelete()
        for env in self.envs:
            env.rdelete()
        for case_group in self.case_groups:
            case_group.rdelete()
        super().rdelete()

    def get_product_line_name(self):
        result = get_productline(self)
        if result:
            return result.get("product_line")
        else:
            return None

    def get_executor_type(self):
        for executor_type, info in self.extra.get('executors', {}).items():
            if info.get("url"):
                return executor_type

        return None


class ProjectSchema(ma.ModelSchema):
    class Meta:
        model = Project
        fields = ('author', 'created_time', 'updated_time', 'id', 'commit_info',
                  'name', 'description', 'status', 'executor', 'extra', 'manul_cases_count',
                  'auto_cases_count', "feature_id", "productline", "public_project")

    productline = fields.Method("get_productline")

    def get_productline(self, obj):
        productline = get_productline(obj)
        if productline:
            return {"line": productline.get("product_line"),
                    "subline": productline.get('sub_line'),
                    "feature": productline.get('feature')
                    }
        else:
            return None


project_schema = ProjectSchema()


class ProjectsSchema(ma.ModelSchema):
    class Meta:
        model = Project
        fields = ('author', 'created_time', 'updated_time', 'id', 'commit_info',
                  'name', 'description', 'status', 'executor', 'extra', 'manul_cases_count',
                  'auto_cases_count', "feature_id", "public_project")


projects_schema = ProjectsSchema()
