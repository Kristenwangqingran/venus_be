# -*- coding: utf-8 -*-
# @Time    : 2022/08/01
# @Author  : Chen Jiaxin


import time
import json
import copy
import traceback
from flask import current_app
from app.commons import init_mymq, MyRedis, myrq


class SzqaDependencyMgr:
    """
    actions:
    1. query_szqa_dependency
    2. update_szqa_dependency
    3. change_python_path
    """
    def __init__(self, timestamp=None):
        self.routing_key = "official__api"
        self.hd = MyRedis(current_app.config["REDIS"]["URL_FOR_DEPENDENCY"])
        self.timestamp = timestamp if timestamp else int(time.time())
        self.task = {
            "action": "",
            "timestamp": self.timestamp
        }

    def send_task(self, task):
        result = {"status": "pending"}
        self.hd.set(self.timestamp, json.dumps(result), ex=24 * 60 * 60)
        mymq = init_mymq()
        ok = mymq.send('oneworker', self.routing_key, json.dumps(task))
        if ok:
            current_app.logger.info(f"Send task to {self.routing_key} success!")
        else:
            current_app.logger.info(f"Send task to {self.routing_key} failed!")

    def broadcast_task(self, task):
        from app.libs import workermgr
        workermgr.update_workers_info()
        workers_dict = workermgr.get_workers()
        result = {
            "status": "pending",
            "workers": {k: "pending" for k in workers_dict},
            "dependency": {k: {} for k in workers_dict}
        }
        self.hd.set(self.timestamp, json.dumps(result), ex=24 * 60 * 60)
        mymq = init_mymq()
        ok = mymq.send('allworkers', "", json.dumps(task))
        if ok:
            current_app.logger.info(f"Broadcast success!")
        else:
            current_app.logger.info(f"Broadcast failed!")

    def wait_result(self, timeout=12 * 60 * 60):
        while timeout:
            try:
                result_str = self.hd.get(str(self.timestamp))
                result = json.loads(result_str) if result_str else {}
                current_status = result.get('status', '')
                if current_status not in ['running', 'pending']:
                    current_app.logger.info(f"Result update!")
                    return result

            except Exception:
                current_app.logger.error(f"Some wrong happened while waiting result: {traceback.format_exc()}")

            finally:
                time.sleep(1)
                timeout -= 1
        return {}

    def _recover_status(self, workers):
        for worker in workers:
            result_str = self.hd.get(worker)
            info = json.loads(result_str) if result_str else {}
            info["status"] = "finish"
            self.hd.set(worker, json.dumps(info))

    def wait_broadcast_result(self, timeout=12 * 60 * 60):
        result = {}
        while timeout:
            try:
                result_str = self.hd.get(str(self.timestamp))
                result = json.loads(result_str) if result_str else {}
                all_done = True
                new_result = copy.deepcopy(result)
                for worker in result.get('workers', {}):
                    info_str = self.hd.get(worker)
                    info = json.loads(info_str) if info_str else {}
                    if info.get("status", "no") == "done":
                        new_result["workers"][worker] = "done"
                        new_result["dependency"][worker] = info.get("dependency", {})
                    else:
                        all_done = False
                new_result["status"] = "running" if not all_done else "done"
                self.hd.set(self.timestamp, json.dumps(new_result), ex=24 * 60 * 60)
                if all_done:
                    result = new_result
                    self._recover_status(result['workers'])
                    break

            except Exception:
                current_app.logger.error(f"Some wrong happened while waiting result: {traceback.format_exc()}")

            finally:
                time.sleep(1)
                timeout -= 1

        return result

    def run(self, action, broadcast=False, broadparams=None, timeout=12 * 60 * 60):
        self.task["action"] = action
        if broadcast:
            if isinstance(broadparams, dict):
                self.task = {**self.task, **broadparams}
            self.broadcast_task(self.task)
            result = self.wait_broadcast_result(timeout)
        else:
            self.send_task(self.task)
            result = self.wait_result()
        return result

    def get_result(self, ):
        result_str = self.hd.get(self.timestamp)
        return json.loads(result_str) if result_str else {}


@myrq.job('exec')
def update_szqa_dependency(timestamp):
    try:
        mgr = SzqaDependencyMgr(timestamp)
        mgr.run("update_szqa_dependency")
    except Exception:
        current_app.logger.error(f"Some wrong happened while updating szqa dependency: {traceback.format_exc()}")


@myrq.job("exec")
def change_python_path(timestamp, use_latest=False, new_path=''):
    try:
        mgr = SzqaDependencyMgr(timestamp)
        mgr.run("change_python_path", broadcast=True, broadparams={
            "use_latest": use_latest,
            "szqa_dependency_path": new_path
        })
    except Exception:
        current_app.logger.error(f"Some wrong happened while updating szqa dependency: {traceback.format_exc()}")
