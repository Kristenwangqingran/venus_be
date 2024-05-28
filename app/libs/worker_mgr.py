# -*- coding: utf-8 -*-
# @Time    : 2022-03-09
# @Author  : GongXun

import time
import os
import re
import random
import traceback
import datetime
import json
from threading import Lock
from app.commons import MyLogger
from app.commons import MyRedis, init_mymq, get_config
from app.models import CaseType_to_ARGS, OFFICIAL_ExecutorType, OFFICIAL_ENVType
from .stf_mgr import STFMgr
from .exec_mgr import TaskFactory

current_env = get_config()
MG = MyLogger('workermgr', path=os.path.join(
    'instance', current_env.LOG_FOLDER, 'worker_mgr.log'))


class WokerMGR:

    def __init__(self):
        self.stfmgr = STFMgr()

        self.capacity_lock = Lock()
        self.empty_value = ('', None, "None", 'NONE')

        if os.environ.get("APS_CONFIG") == 'true':
            self._trigger_worker_upload_info()
        else:
            # get info from redis
            pass

    @staticmethod
    def _get_executor_name(worker_name):
        ret = worker_name
        cp = re.match(r'([^0-9]+)', worker_name)
        if cp:
            ret = cp.group(1)
        return ret

    def get_UEs(self):
        devices = self.stfmgr.all_infos()
        return devices

    def update_UEs(self):
        self.stfmgr.update()

    @classmethod
    def get_workers(cls):
        result_hd = MyRedis(current_env.REDIS['URL_FOR_WORKER'])
        workers_dict = {}
        workers = result_hd.keys()
        for worker in workers:
            info = result_hd.get(worker)
            info = json.loads(info)
            if info['status'] == 'offline':
                continue
            name = worker.decode('utf-8')
            workers_dict[name] = info
        result_hd.disconnect()
        return workers_dict

    def _trigger_worker_upload_info(self, executor=None, env=None, timeout=5):

        def _worker_syncflag_clear(executor, env):
            result_hd = MyRedis(current_env.REDIS['URL_FOR_WORKER'])
            workers = self.get_workers()
            for worker_name, info in workers.items():
                executor_name = self._get_executor_name(worker_name)
                if executor and executor != executor_name:
                    continue
                if env and info['env'] != env:
                    continue
                info['syncflag'] = False
                result_hd.set(worker_name, json.dumps(info))
            result_hd.disconnect()

        def _worker_sync_done(executor, env, timeout):
            all_done = False
            dest_time = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
            MG.info(
                f"now: {datetime.datetime.now()}, dest_time: {dest_time}, executor: {executor}, env: {env}, timeout: {timeout}")
            result_hd = MyRedis(current_env.REDIS['URL_FOR_WORKER'])
            while datetime.datetime.now() < dest_time:
                workers = self.get_workers()
                all_done = True
                for worker_name, info in workers.items():
                    executor_name = self._get_executor_name(worker_name)
                    if executor and executor != executor_name:
                        continue
                    if env and env != info['env']:
                        continue
                    if info['syncflag'] is False:
                        all_done = False
                        MG.warn(
                            f"worker: {worker_name} still not sync!")
                        break
                if all_done is True:
                    break
                time.sleep(1)

            workers = self.get_workers()
            for worker_name, info in workers.items():
                executor_name = self._get_executor_name(worker_name)
                if executor and executor != executor_name:
                    continue
                if env and env != info['env']:
                    continue
                if info['syncflag'] is False:
                    info['status'] = 'offline'
                    result_hd.set(worker_name, json.dumps(info))
                    MG.warn(
                        f"Set worker: {worker_name} offline!")
            result_hd.disconnect()
            return all_done

        try:
            result_hd = MyRedis(current_env.REDIS['URL_FOR_WORKER'])

            _worker_syncflag_clear(executor, env)
            mymq = init_mymq()
            task = TaskFactory.init_task_v2()
            task.update({
                "action": "infos",
                "channel_id": 'infos'
            })

            # assign task
            if executor:
                if not env:
                    env = "common"
                mymq.send('thoseworkers',
                          f"{executor}__{env}", json.dumps(task))
            else:
                mymq.send('allworkers', "", json.dumps(task))
                MG.warn(f"Let all worker to report info")

            # wait worker sync status
            time.sleep(5)
            # check task status
            sync_done = _worker_sync_done(executor, env, timeout=timeout)
            msg = "sync all workers done?: "
            MG.warning(f"{msg}{sync_done}")

            result_hd.disconnect()
        except Exception:
            MG.error(traceback.format_exc())

    def get_params(self):

        def _build_worker_params(worker_info):
            for param in worker_info['params']:
                if param['group'] in ('Android', 'iOS'):
                    params = self.stfmgr.get_device_types(
                        platform=param['group'].lower())
                    param['options'] = params

        errmsg = ''
        params = {}

        try:
            workers = self.get_workers()
            for _, info in workers.items():
                key = f"{info['executor']}_{info['env']}"
                if key not in params:
                    if info['env'] == 'mobile':
                        _build_worker_params(info)
                    params[key] = info["params"]

        except Exception as err:
            MG.error(traceback.format_exc())
            errmsg = str(err)

        finally:
            if errmsg:
                MG.error(f"Get params failed: {errmsg}")
        return params, errmsg

    def _update_worker_resource(self, executor, env):

        def __filter_workers_by_category(category, env):
            workers = []
            result_hd = MyRedis(current_env.REDIS['URL_FOR_WORKER'])
            workerkeys = result_hd.keys()
            for worker in workerkeys:
                worker_name = worker.decode('utf-8')
                executor_name = self._get_executor_name(worker_name)
                if executor_name != category:
                    continue
                data = result_hd.get(worker)
                info = json.loads(data)
                if info['env'] == env and info['syncflag'] is True and info['status'] == "normal":
                    # if info['env'] == env and info['status'] == "normal":
                    workers.append(info)

            result_hd.disconnect()
            return workers

        def __get_idel_workers(executor, env):
            all_workers = __filter_workers_by_category(executor, env)
            workers = []
            for worker in all_workers:
                if worker['max_task_count'] - worker['task_count'] > 0:
                    workers.append(worker)
            return workers

        result_hd = MyRedis(
            current_env.REDIS['URL_FOR_WORKER_CAPACITY'])
        self.capacity_lock.acquire()
        if executor in OFFICIAL_ExecutorType and env in OFFICIAL_ENVType:
            self.stfmgr.update()
        workers = __get_idel_workers(executor, env)
        if workers:
            result_hd.set(f"{executor}__{env}", json.dumps(workers))
        self.capacity_lock.release()
        result_hd.disconnect()

    def _get_worker_resource(self, executor, env, params):
        workers = []
        k = f"{executor}__{env}"
        result_hd = MyRedis(
            current_env.REDIS['URL_FOR_WORKER_CAPACITY'])
        self.capacity_lock.acquire()
        data = result_hd.get(k)
        if data:
            tmp_workers = json.loads(data)
            for worker in tmp_workers:
                MG.warn(
                    f"to check params for worker: {worker['name']}")
                if params:
                    if self._is_worker_match_params(worker, params):
                        workers.append(worker)
                    else:
                        MG.warn(
                            f"{worker['name']} check params not pass!")

                else:
                    workers.append(worker)
        self.capacity_lock.release()
        result_hd.disconnect()
        return workers

    def _is_worker_match_params(self, worker, params):
        worker_ok = True
        needed_types = []
        for dest_param in params:
            if dest_param['value'] in self.empty_value:
                continue
            else:
                needed_types.append(
                    (dest_param['group'].lower(), dest_param['value']))

        if not self.stfmgr.has_devices(worker['node'], needed_types):
            worker_ok = False
            MG.warn(
                f"{worker['name']} can't match params: {params}")

        return worker_ok

    def _acquire_worker_resource(self, executor, env, params):
        theworker = None
        locked_devices = []

        result_hd = MyRedis(
            current_env.REDIS['URL_FOR_WORKER_CAPACITY'])
        self.capacity_lock.acquire()
        k = f"{executor}__{env}"
        data = result_hd.get(k)
        if data:
            workers = json.loads(data)
            random.shuffle(workers)
            for worker in workers:
                try:
                    if worker['max_task_count'] - worker['task_count'] > 0:
                        if params:
                            if self._is_worker_match_params(worker, params):
                                device_types = []
                                [device_types.append((item['group'].lower(
                                ), item['value'])) for item in params if item['value'] not in self.empty_value]
                                locked_devices = self.stfmgr.acquire_devices(
                                    worker['node'], device_types)
                                if locked_devices:
                                    worker['task_count'] += 1
                                    result_hd.set(k, json.dumps(workers))
                                    theworker = worker
                                    break
                                else:
                                    continue
                            else:
                                MG.warn(
                                    f"{worker['name']} can't match params: {params}")
                                continue

                        else:
                            if env == 'mobile':
                                devices = self.get_UEs()
                                node_devices = devices.get(worker['node'], {})
                                for platform, device_types in node_devices.items():
                                    for device_type in device_types.keys():
                                        locked_devices = self.stfmgr.acquire_devices(
                                            worker['node'], [(platform, device_type)])
                                        if locked_devices:
                                            worker['task_count'] += 1
                                            result_hd.set(k, json.dumps(workers))
                                            theworker = worker
                                            break
                                    if locked_devices:
                                        break
                                if locked_devices:
                                    break
                                else:
                                    continue
                            else:
                                worker['task_count'] += 1
                                result_hd.set(k, json.dumps(workers))
                                theworker = worker
                                break

                    else:
                        MG.info(f"{worker['name']} is busy!")

                except Exception:
                    MG.error(traceback.format_exc())
                    for item in locked_devices:
                        self.stfmgr.release_device(item['udid'])
                    theworker = None
                    locked_devices = []
        else:
            MG.warn(f"currently has no resource for: {k}")
        self.capacity_lock.release()
        result_hd.disconnect()
        return theworker, locked_devices

    def _filter_params_by_casetype(self, case_type, params):
        if not params or not isinstance(params, list):
            return []
        final_params = []
        needed_params = CaseType_to_ARGS[case_type]
        for param in params:
            if param['name'] in needed_params:
                final_params.append(param)
        return final_params

    def release_device(self, udid):
        MG.info(
            f"to release device: {udid}")
        self.stfmgr.release_device(udid)

    def acquire_worker_resource(self, executor, env, case_type, params=None):
        ret = False
        if params:
            params = self._filter_params_by_casetype(case_type, params)
        theworker, locked_devices = self._acquire_worker_resource(
            executor, env, params)
        if not theworker:
            self._update_worker_resource(executor, env)
            theworker, locked_devices = self._acquire_worker_resource(
                executor, env, params)

        if locked_devices:
            for i, param in enumerate(params):
                param['value'] = locked_devices[i]['udid']
        return theworker, locked_devices

    def has_worker_resource(self, executor, env, case_type, params=None):
        return True
        ret = False
        if params:
            MG.warn(f"before fillter, params: {params}")
            params = self._filter_params_by_casetype(case_type, params)
            MG.warn(f"after fillter, params: {params}")
        workers = self._get_worker_resource(executor, env, params)
        if workers:
            ret = True
        else:
            self._update_worker_resource(executor, env)
        return ret

    def update_workers_info(self, timeout=60):
        self._trigger_worker_upload_info(timeout=timeout)
