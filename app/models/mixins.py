# -*- coding: utf-8 -*-
# @Time    : 2020-08-03
# @Author  : GongXun


import re
import copy
from datetime import datetime
from app.commons import db
from marshmallow import ValidationError
from psycopg2.errors import UniqueViolation


class TimestampMixin(object):
    id = db.Column(db.Integer, primary_key=True)

    author = db.Column(db.String(64), nullable=True, default='no-one')

    created_time = db.Column(
        db.DateTime, nullable=False, default=datetime.now, index=True)
    updated_time = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now, index=True)

    deleted = db.Column(db.Boolean, default=False, index=True)

    def put_check(self, data):
        if data.get("project_id", None) or data.get("name", None):
            items = self.__class__.query.filter(self.__class__.project_id == data.get(
                "project_id", self.project_id), self.__class__.name == data.get("name", self.name)).all()
            for item in items:
                if item.id != self.id:
                    if item.deleted == True:
                        item.rdelete()
                    else:
                        raise UniqueViolation(f'Resource already exists!')

    @classmethod
    def post_check(cls, data):
        if data.get("name", None) is None or data.get("project_id", None) is None:
            raise ValidationError(f'name or project arg missing!')
        else:
            items = cls.query.filter(
                cls.project_id == data["project_id"], cls.name == data["name"]).all()
            for item in items:
                if item.deleted == True:
                    item.rdelete()
                else:
                    raise UniqueViolation(f'Resource already exists!')

    def put_save(self, data):
        for k, v in data.items():
            if k in ('id', 'created_time', 'updated_time'):
                continue
            elif isinstance(v, (dict, list)):
                tmp_v = copy.deepcopy(v)
                setattr(self, k, tmp_v)
            else:
                setattr(self, k, v)
        self.save()

    def set_created_time(self):
        self.created_time = datetime.now()

    def save(self):
        with db.auto_commit_db():
            db.session.add(self)

    def delete(self):
        self.deleted = True
        self.save()

    def rdelete(self):
        with db.auto_commit_db():
            db.session.delete(self)


CaseType = {
    "TopoAndroid": "TopoAndroid",
    "TopoIos": "TopoIos",
    "TopoMobile": "TopoMobile",
    "TopoAndroidIos": "TopoAndroidIos",
    "TopoIosAndroid": "TopoIosAndroid",
    "TopoTwoAndroid": "TopoTwoAndroid",
    "TopoTwoIos": "TopoTwoIos",
    "TopoTwoMobile": "TopoTwoMobile",
    "TopoHttp": "TopoHttp",
    "TopoSpex": "TopoSpex",
    "TopoWeb": "TopoWeb",
    "TopoLib": "TopoLib"
}


MobileCaseType = ["TopoAndroid", "TopoIos", "TopoMobile", "TopoAndroidIos", "TopoIosAndroid", "TopoTwoAndroid",
                  "TopoTwoIos", "TopoTwoMobile"]


CaseType_to_ARGS = {
    "TopoAndroid": ('android_main_device_id', ),
    "TopoIos": ('ios_main_device_id', ),
    "TopoMobile": ('android_main_device_id', 'ios_main_device_id'),
    "TopoAndroidIos": ('android_main_device_id', 'ios_sub_device_id'),
    "TopoIosAndroid": ('ios_main_device_id', 'android_sub_device_id'),
    "TopoTwoAndroid": ('android_main_device_id', 'android_sub_device_id'),
    "TopoTwoIos": ('ios_main_device_id', 'ios_sub_device_id'),
    "TopoTwoMobile": ('android_main_device_id', 'android_sub_device_id', 'ios_main_device_id', 'ios_sub_device_id'),
    "TopoHttp": [],
    "TopoSpex": [],
    "TopoWeb": [],
    "TopoLib": []
}
ALL_Device_ARGS = ('android_main_device_id', 'android_sub_device_id',
                   'ios_main_device_id', 'ios_sub_device_id')

MAX_CaseType = "TopoTwoAndroid"


MateType = {
    "CMD": "CMD",
    "CMDDEMO": "CMDDEMO",
    "API": "API",
    "APIDEMO": "APIDEMO",
    "CASE": "CASE",
}


TaskStatus = {
    "pending": "pending",
    "running": "running",
    "pass": "pass",
    "fail": "fail",
    "error": "error",
    "skip": "skip",
    "canceled": "canceled",
    "done": "done",
    "timeout": "timeout"
}
TaskStatus_DONE = ("done", "pass", "error", "fail",
                   "skip", "timeout", "canceled")
TaskStatus_UNSUCCESS = ("error", "fail", "timeout")


TaskStatus_UNDONE = ("pending", "running")


PriorityType = {
    "P0": "P0",
    "P1": "P1",
    "P2": "P2",
    "P3": "P3"
}


ExecutorType = {
    "spex": "spex",
    "official": "official",
    "rpc": "rpc",
    "py": "py",
    "pfc": "pfc"
}

OFFICIAL_ExecutorType = ("official",)
OFFICIAL_ENVType = ('mobile',)
THR_ExecutorType = ("rpc", "py", "spex", "pfc")


CT_map = {
    "application/x-www-form-urlencoded": 1,
    "application/json": 2,
    "multipart/form-data": 3,
    "text/xml": 4,
}

TC_map = {
    1: "application/x-www-form-urlencoded",
    2: "application/json",
    3: "multipart/form-data",
    4: "text/xml",
}

ValidateMethod = ["eq", "lt", "le", "gt",
                  "ge", "ne", "str_eq", "len_eq", "len_gt", "len_ge", "len_lt", "len_le", "contains"]


Xfile_default_version = 'auto-v1.0'
Xfile_version_pattern = re.compile(r"(auto-v)([.\d]+)")


BUG_STATUS = {
    "ONGOING": "ONGOING",
    "DONE": "DONE",
    "PENDING": "PENDING"
}

APP_TYPE = {
    "Android": "Android",
    "IOS": "IOS"
}

REGION = {
    "SG": "SG",
    "VN": "VN"
}

DEFAULT_CASE_TIMEOUT = 1800

CASE_UNPASS_REASON = {
    "ERROR": {
        "case_error": "case_error",
        "system_error": "system_error"
    },
    "FAIL": {
        "dependency_issue": "dependency_fail",
        "environmental_issue": "environmental_issue",
        "script_issue": "script_issue",
        "platform_issue": "platform_issue",
        "business_issue": "business_issue"
    }
}

Run_Log_Type = {
    "case": "case",
    "suite": "suite"
}


REGIONs = (
    "SG",
    "VN",
    "TH",
    "TW",
    "ID",
    "MY",
    "PH",
    "BR",
    "MX",
    "CO",
    "CL",
    "PL",
    "ES",
    "FR",
    "IN",
)
PLATFORMs = ('ios', 'android')

APPTYPEs = ("ShopeePay", "Merchant",
            "SeaBank",
            "Shopee",
            "SeaTalk",
            "Sea Mattermost",
            "ShopeePay")

HTTP_TYPE = {
    "string": "STRING",
    "integer": "INT32",
    "boolean": "BOOL",
    "number": "NUMBER"
}
