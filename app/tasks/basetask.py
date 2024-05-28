# -*- coding: utf-8 -*-
# @Time    : 2020-09-09
# @Author  : GongXun


import uuid
import os
from app.commons import utils, get_config

current_env = get_config()


class BaseTask:

    @classmethod
    def init_task_v2(cls):
        return {
            "action": "",
            "channel_id": uuid.uuid4().hex,
            "case_id": 0,
            "case_name": "",
            "case_category": "",
            "case_type": "",
            "steps": [],
            "case_extra": {},
            "caseresult_id": None,
            "suiteresult_id": None,
            "project_id": 0,
            "project_name": "",
            "project_path": "",
            "product_line_name": "",
            "host": current_env.WEB_HOST,
            "py_modules": "",
            "logfile": "",
            "executor_type": "",
            "executor_env": "",
            "executor_path": "",
            "env": "test",
            "author": "",
            "runner": "",
            'inputs': {},
            'outputs': {},
            'timeout': 60,
            "use_file_as_inputs": False,
            "runtime_args": None
        }

    @classmethod
    def init_result(cls):
        return {
            "status": "pending",
            "errors": "",
            "request": {},
            "response": {},
        }

    @staticmethod
    def _get_attr_from_extra(project_instance, attr, category=None):
        if project_instance.extra:
            if "executors" in project_instance.extra:
                return project_instance.extra.get("executors", {}).get(category, {}).get(attr, "")
            else:
                return project_instance.extra.get(attr, "")
        else:
            return ""

    @staticmethod
    def _get_executor_path(project_instance, category=None):
        if project_instance.extra:
            if "executors" in project_instance.extra:
                the_path = os.path.join(
                    project_instance.get_product_path(), "executors", category)
            else:
                the_path = os.path.join(
                    project_instance.get_product_path(), 'executor')
            if not os.path.exists(the_path):
                os.makedirs(the_path)
            return the_path
        else:
            return ""
