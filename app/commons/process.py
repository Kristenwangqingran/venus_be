# -*- coding: utf-8 -*-
# @Time    : 2020-09-13
# @Author  : GongXun


import json
import requests
import traceback
from flask import current_app
from .myredis import MyRedis
from . import utils


class Process:

    def __init__(self, project_id):
        self.project_id = project_id

        # internal variables
        self.hd = MyRedis(
            current_app.config['REDIS']['URL_FOR_GIT'])

        self.status = ["ongoing", "success", "fail", "skip", 'done']
        self.true_status = ["ongoing", "success", "skip", 'done']
        self.done_status = ["success", "fail", "skip", 'done']
        self.template = {
            "start_time": "",
            "end_time": "",
            "status": "ongoing/success/fail/skip",
            "steps": [
                {
                    "start_time": "",
                    "end_time": "",
                    "name": "git clone",
                    "status": "skip",
                    "details": "xxxxx"
                },
            ],
            "finish": False
        }
        self.record_template = {
            "name": "git clone",
            # "status": "skip",
            # "details": "xxxxx"
        }

        # self._create()

    def is_exists(self, ):
        if self.hd.get(self.project_id):
            return True
        else:
            return False

    def is_ongoing(self, ):
        process = self.query()
        if not process:
            return False
        return process['status'] == 'ongoing'

    def query(self):
        if not self.is_exists():
            return None
        process_bytes = self.hd.get(self.project_id)
        if process_bytes:
            process = json.loads(process_bytes)
        else:
            process = None
        return process

    def reset(self, ):
        return self._create()

    def _create(self, ):
        process = {
            "start_time": utils.get_current_timestr(),
            "end_time": '',
            "status": "ongoing",
            "steps": [],
            "user": "",
            "finish": False
        }
        self.hd.set(self.project_id, json.dumps(process), ex=24 * 60 * 60)

    def _check_record(self, record):
        for k, v in self.record_template.items():
            if k not in record:
                return False
            elif k == 'status' and k not in self.status:
                return False
        return True

    def _record_merge(self, old, new):
        for k in old:
            if k in ("start_time", "end_time"):
                continue
            elif k == 'details':
                old[k] += f"\n{new[k]}"
            else:
                old[k] = new[k]

    def update(self, new_record):
        process = self.query()
        if not process:
            return False

        if self._check_record(new_record):
            for record in process['steps']:
                if record['name'] == new_record['name']:
                    self._record_merge(record, new_record)
                    record["end_time"] = utils.get_current_timestr()
                    break
            else:
                # insert
                new_record["start_time"] = utils.get_current_timestr()
                process["steps"].append(new_record)

            # current_app.logger.info(
            #     f"current process for project {self.project_id} is: {process}")
            self.hd.set(self.project_id, json.dumps(process), ex=6 * 60 * 60)
            return True
        else:
            return False

    def check_done(self, step_name):
        process = self.query()
        if not process:
            return False

        for step in process['steps']:
            if step['name'] == step_name:
                return True if step['status'] in self.done_status else False

    def check_finish(self,):
        process = self.query()
        if not process:
            return False

        return process.get('finish', False) is True

    def finish(self, finish=True):
        process = self.query()
        if not process:
            return False

        process['finish'] = finish
        self.hd.set(self.project_id, json.dumps(process), ex=6 * 60 * 60)
        self.close()

    def close(self):
        process = self.query()
        if not process:
            return False

        for record in process['steps']:
            if record['status'] not in self.true_status:
                process['status'] = record['status']
                break
        else:
            process['status'] = "success"
        process["end_time"] = utils.get_current_timestr()
        self.hd.set(self.project_id, json.dumps(process), ex=6 * 60 * 60)

        current_app.logger.info(
            f"project {self.project_id} update finish...")
        self.hd.disconnect()
        self.hd = None

    # for project sync
    def send_fail_to_people(self, people, project_name):
        try:
            send = False
            if not people:
                raise ValueError("No people")

            msg = f"Hello, {people.replace('@shopee.com', '')} \n" \
                  f"your project: {project_name} sync fail, please check \n"
            process = self.query()
            if not process:
                return

            for step in process.get("steps", []):
                if step["status"] == "fail":
                    send = True
                    msg += f"[{step['name']}] fail: \n" \
                           f"{step['details']} \n"

            if send:
                body = {
                    "channel": "st",
                    "content": msg,
                    "g_name": "",
                    "u_name": people
                }
                requests.post(url=current_app.config['QABOT_NOTI'], headers={
                    "accept": "application/json", "Content-Type": "application/json"}, json=body)

                current_app.logger.info(f"Send message to {people} success!")

        except Exception:
            current_app.logger.error(
                f"Send fail item to people fail: {traceback.format_exc()}")
