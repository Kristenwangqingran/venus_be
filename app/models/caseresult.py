# -*- coding: utf-8 -*-
# @Time    : 2020/8/25
# @Author  : GongXun

import os
import shutil
import traceback
import threading
from flask import current_app
from .mixins import TimestampMixin, TaskStatus, TaskStatus_DONE, CASE_UNPASS_REASON
from app.commons import db, ma, utils
import copy
from .suiteresult import SuiteResult
from marshmallow import ValidationError, fields
import re
from .project import Project
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.dialects.postgresql import JSON


class CaseResult(TimestampMixin, db.Model):
    LOCK = threading.Lock()
    normal = {
        "author": "kobe",
        "status": "running",
        "env_name": "env1",
        "details": [],
        "case_id": 1
    }
    details_normal = {
        "in_out": {
            "config_vars": {},
            "export_vars": {}
        },
        "log": "",
        "html_file": "",
        "steps": [
            {
                "name": "step1",
                "status": "success",
                "request": {},
                "response": {},
                "validators": [
                    {
                        "comparator": "equal",
                        "check": "status_code",
                        "check_value": None,
                        "expect_value": None,
                        "message": None,
                        "check_result": None
                    },
                ],
                "errors": "error msg"
            },
        ]
    }
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(127), nullable=False,
                       default=TaskStatus["pending"])
    reason = db.Column(db.String, nullable=True)
    env_name = db.Column(db.String, nullable=False)

    # 详细信息
    details = db.Column(JSON, nullable=False, default=details_normal)

    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=True)
    case_name = db.Column(db.String(256), nullable=True)
    group_name = db.Column(db.String(127), nullable=True)
    debug_mode = db.Column(db.Boolean, default=False)
    # mobile app information
    device_info = db.Column(db.JSON, nullable=True, default={})
    app_info = db.Column(db.JSON, nullable=True, default={})
    performance_info = db.Column(db.JSON, nullable=True, default={})
    item_results = db.Column(db.JSON, nullable=True, default=[])

    suiteresult_id = db.Column(
        db.Integer, db.ForeignKey('suite_result.id'), nullable=True)
    suiteresult = db.relationship('SuiteResult', backref=db.backref('caseresults', lazy='dynamic'),
                                  lazy='select', cascade="save-update, merge, refresh-expire, expunge",
                                  single_parent=True)
    comments = db.Column(db.Text, nullable=True)
    duration = db.Column(db.Float, nullable=True)
    run_time = db.Column(db.DateTime, nullable=True)
    done_time = db.Column(db.DateTime, nullable=True)

    # worker
    worker = db.Column(db.JSON, nullable=True)
    runner = db.Column(db.String(64), nullable=True)

    def save(self):
        with self.LOCK:
            try:
                flag_modified(self, "details")
                super().save()
                self.init_dir()

                if self.status == "error" and not self.reason:
                    self.reason = CASE_UNPASS_REASON['ERROR']["case_error"]

                if self.debug_mode and self.status == "pass":
                    self.debug_mode = False

                if self.details and isinstance(self.details, list):
                    details = copy.deepcopy(self.details)
                    details_tmp = details[0]
                    for item in ['log', 'html_file', 'log_path']:
                        if details_tmp.get(item, None):
                            details_tmp[item] = re.sub(
                                r'.*instance', current_app.instance_path, details_tmp[item])
                            if os.path.exists(details_tmp[item]):
                                if self.get_absolute_logdir() in details_tmp[item]:
                                    if self.get_absolute_logdir() == details_tmp[item]:
                                        details_tmp[item] = os.path.join(
                                            current_app.config['TOMCAT_HOST'], self.get_relative_logdir())

                                    else:
                                        details_tmp[item] = os.path.join(
                                            current_app.config['TOMCAT_HOST'], self.get_relative_logdir(), os.path.basename(details_tmp[item]))

                                else:
                                    if os.path.isdir(details_tmp[item]):
                                        shutil.copytree(details_tmp[item], os.path.join(
                                            self.get_absolute_logdir(), os.path.basename(details_tmp[item])))
                                    else:
                                        shutil.copy(details_tmp[item],
                                                    self.get_absolute_logdir())

                                    details_tmp[item] = os.path.join(
                                        current_app.config['TOMCAT_HOST'], self.get_relative_logdir(), os.path.basename(details_tmp[item]))

                    self.details = details
                # Prevent device_info to be None and flag_modified got error
                if self.device_info is None:
                    self.device_info = {}

                if self.worker and self.details and "show_name" not in self.device_info:
                    main_device_value = ""
                    main_device_id = ""
                    devices = self.details[0].get("exec_data", {}).get(
                        "runtime_args", {}).get("official_mobile", [])
                    for device in devices:
                        if "main_device" in device.get("name", ""):
                            main_device_value = device.get("value", "")
                            break

                    if main_device_value:
                        for lock_device in self.worker.get("locked_devices", []):
                            if lock_device.get("type", "") == main_device_value:
                                main_device_id = lock_device.get("udid", "")
                                break
                    if main_device_id and main_device_value:
                        self.device_info.update(
                            {"id": main_device_id, "show_name": main_device_value})

                if self.worker and self.status in TaskStatus_DONE and self.worker.get('locked_devices', []) and \
                        self.worker.get('locked_devices_released', True) is False:
                    self.worker['locked_devices_released'] = True
                    from app.libs import workermgr
                    for item in self.worker['locked_devices']:
                        workermgr.release_device(item['udid'])
                flag_modified(self, "worker")
                flag_modified(self, "device_info")
                super().save()

                if self.suiteresult:
                    case_ids = self.suiteresult.extra["cases"].get(
                        str(self.case_id), [])
                    if self.id not in case_ids:
                        case_ids.append(self.id)
                    self.suiteresult.extra["cases"][str(
                        self.case_id)] = case_ids
                    if not self.debug_mode and self.suiteresult.debug_mode:
                        self.suiteresult.debug_mode = False

                    if self.device_info and self.device_info.get("id", ""):
                        if self.suiteresult.device_info:
                            device_case_results = self.suiteresult.device_info.get(
                                self.device_info["id"], [])
                            if self.id not in device_case_results:
                                device_case_results.append(self.id)
                            self.suiteresult.device_info[self.device_info["id"]
                                                         ] = device_case_results
                        else:
                            self.suiteresult.device_info = {
                                self.device_info["id"]: [self.id]}
                    self.suiteresult.save()
                    # self.suiteresult.update_statistics(self.status)

            except Exception:
                super().save()
                current_app.logger.error(
                    f"[{self.id}]{traceback.format_exc()}")

            finally:
                from app.commons import RunLogger
                if self.status in TaskStatus_DONE:
                    logger = RunLogger(self.id, self.get_absolute_logdir())
                    logger.release()

    @classmethod
    def post_check(cls, data):
        errors = []
        for k, v in cls.normal.items():
            if k in data:
                if isinstance(data[k], type(v)):
                    pass
                else:
                    errors.append(
                        f"{k}: value has wrong type! [{type(data[k])} != {type(v)}]")
            else:
                errors.append(f"{k} missed!")

        if errors:
            raise ValidationError(errors)

    def put_check(self, data):
        errors = []
        for k, v in self.normal.items():
            if k in data:
                if isinstance(data[k], type(v)):
                    pass
                else:
                    errors.append(
                        f"{k}: value has wrong type! [{type(data[k])} != {type(v)}]")

        if errors:
            raise ValidationError(errors)

    def init_dir(self):
        project = Project.query.get(self.case.project_id)
        project_dir = project.get_log_path()
        case_dir = os.path.join(
            project_dir, utils.ensure_dirname(self.case.name))
        if not os.path.exists(case_dir):
            os.makedirs(case_dir, exist_ok=True)

        result_dir = os.path.join(case_dir, str(self.id))
        if not os.path.exists(result_dir):
            os.makedirs(result_dir, exist_ok=True)

    def get_absolute_logdir(self):
        project = Project.query.get(self.case.project_id)
        log_dir = os.path.join(project.get_log_path(),
                               utils.ensure_dirname(self.case.name), str(self.id))
        return log_dir

    def get_relative_logdir(self):
        return os.path.join(utils.ensure_dirname(self.case.project_id), utils.ensure_dirname(self.case.name), str(self.id))


class CaseResultsSchema(ma.ModelSchema):

    class Meta:
        model = CaseResult
        fields = ('author', 'created_time', 'updated_time', 'id', 'status', 'reason',
                  'env_name', 'case_id', 'case_name', 'group_name',
                  'suiteresult_id', 'comments', 'runner', 'duration', 'debug_mode',
                  'app_info', 'device_info', 'performance_info', 'item_results', 'apis')

    apis = fields.Method("get_apis")

    def get_apis(self, obj):
        return obj.case.apis


caseresults_schema = CaseResultsSchema()


class CaseResultSchema(ma.ModelSchema):
    class Meta:
        model = CaseResult
        fields = ('author', 'created_time', 'updated_time', 'id', 'status', 'reason',
                  'env_name', 'details', 'case_id', 'case_name', 'group_name',
                  'suiteresult_id', 'comments', 'worker', 'runner', 'duration', 'debug_mode',
                  'app_info', 'device_info', 'performance_info', 'item_results', 'apis')

    apis = fields.Method("get_apis")

    def get_apis(self, obj):
        return obj.case.apis


caseresult_schema = CaseResultSchema()
