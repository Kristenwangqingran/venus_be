# -*- coding: utf-8 -*-
# @Time    : 2022/4/12
# @Author  : Jiaxin Chen


import os
import json
import copy
import time
import requests
import datetime
import traceback
import queue
import szqa_utils
import threading
import subprocess
import base64
from threading import Event
from urllib import parse
from flask import current_app
from app.commons import RunLogger

from app.commons import myrq, MyRedis, db, init_mymq, utils
from collections import defaultdict
from app.tasks.basetask import BaseTask
from app.models import Case, Casesuite, SuiteResult, CaseResult, project_schema, Group, \
    SpexApi, Project, \
    CaseType_to_ARGS, OFFICIAL_ExecutorType, DEFAULT_CASE_TIMEOUT, ExecutorType, MobileCaseType, CASE_UNPASS_REASON, \
    TaskStatus_DONE, TaskStatus_UNSUCCESS, TaskStatus_UNDONE, caseresult_schema
from app.commons.config import get_config
from .case_import_mgr import git_core

current_env = get_config()


class ExecUtils:
    topos_map = {
        "TopoAndroid": "mobile",
        "TopoIos": "mobile",
        "TopoAndroidIos": "mobile",
        "TopoIosAndroid": "mobile",
        "TopoTwoAndroid": "mobile",
        "TopoTwoIos": "mobile",
        "TopoMobile": "mobile",
        "TopoTwoMobile": "mobile",
        "TopoWeb": "web",
        "TopoHttp": "api",
        "TopoSpex": "api",
    }

    @staticmethod
    def _analyze_dependency(dependency):
        """
            input:
                dependency: case dependency mapping
            outputs:
                final_sequence: sequence after parse
                sequence_dict:  case dependency mapping
                errors: errors
        """
        final_sequence = []
        errors = ''
        sequence_dict = defaultdict(list)
        case_status = defaultdict(str)

        def _get_dependency_case_id(case_id):
            error = ''
            ret = []

            if case_status[case_id] == 'ongoing':
                error += f"case: {case_id} circular dependency, please check it carefully!\n"
            else:
                current_app.logger.info(
                    f"to parse case {case_id}'s dependency...")
                case_status[case_id] = 'ongoing'
                if case_id in dependency:
                    for key, value in dependency[case_id].items():
                        if len(value) != 2:
                            continue

                        mum_case_id = value[0]
                        mum_case_id = str(mum_case_id)
                        if mum_case_id in sequence_dict[case_id]:
                            continue
                        sequence_dict[case_id].append(mum_case_id)
                        sub_ret, sub_error = _get_dependency_case_id(
                            mum_case_id)
                        error += sub_error
                        ret += sub_ret
                    ret = ret + [case_id]
                else:
                    ret = [case_id]
                    sequence_dict[case_id] = []
                case_status[case_id] = 'done'
            return ret, error

        for one_case_id in dependency:
            if not dependency[one_case_id]:
                continue
            ret_list, e = _get_dependency_case_id(one_case_id)
            errors += e
            for i in ret_list:
                i = int(i)
                if i in final_sequence:
                    continue
                else:
                    final_sequence.append(i)

        return final_sequence, sequence_dict, errors

    @staticmethod
    def _analyze_sequence(sequence):
        """
            input:
                sequence: case sequence mapping
            outputs:
                final_sequence: sequence after parse
                errors: errors
        """
        final_sequence, errors = [], ''
        case_status = defaultdict(str)

        def _get_sequence_case_id(case_id):
            error = ''
            ret = []

            if case_status[case_id] == 'ongoing':
                error += f"case: {case_id} circular sequence, please check it carefully!\n"
            else:
                current_app.logger.info(
                    f"to parse case {case_id}'s sequence...")
                case_status[case_id] = 'ongoing'
                if case_id in sequence:
                    for mum_case_id in sequence[case_id]:
                        mum_case_id = str(mum_case_id)
                        sub_ret, sub_error = _get_sequence_case_id(mum_case_id)
                        error += sub_error
                        ret += sub_ret
                    ret = ret + [case_id]
                else:
                    ret = [case_id]
                case_status[case_id] = 'done'

            return ret, error

        for case_id in sequence:
            if not sequence[case_id]:
                continue
            ret, error = _get_sequence_case_id(case_id)
            errors += error
            for i in ret:
                i = int(i)
                if i in final_sequence:
                    continue
                else:
                    final_sequence.append(i)

        return final_sequence, errors

    @staticmethod
    def _check_mismatch(dependency_case_sequence, case_sequence):
        err = ''
        cross_set = set(dependency_case_sequence) & set(case_sequence)
        if cross_set:
            dependency_order = dict([(dependency_case_sequence.index(item), item)
                                     for item in cross_set])
            dependency_sorted_key = sorted(dependency_order.keys())

            sequence_order = dict([(case_sequence.index(item), item)
                                   for item in cross_set])
            sequence_sorted_key = sorted(sequence_order.keys())

            for index, _ in enumerate(dependency_sorted_key):
                if dependency_order[dependency_sorted_key[index]] != sequence_order[sequence_sorted_key[index]]:
                    err += f"dependency_order{[dependency_order[k] for k in dependency_sorted_key]} != sequence_order{[sequence_order[k] for k in sequence_sorted_key]}\n"
                    break
        return err

    @classmethod
    def parse_plan(cls, plan, prefix=''):
        err = ''
        # to analyze the case dependency
        dependency_case_sequence, sequence_dict, errors = cls._analyze_dependency(
            plan.get('dependency', {}))
        if errors:
            current_app.logger.error(
                f"{prefix}parse case dependency get errors: {errors}")
            err += errors

        # to analyze the case sequence
        case_sequence, errors = cls._analyze_sequence(plan.get('sequence', {}))
        if errors:
            current_app.logger.error(
                f"{prefix}parse case sequence get errors: {errors}")
            err += errors

        errors = cls._check_mismatch(dependency_case_sequence, case_sequence)
        if errors:
            current_app.logger.error(
                f"{prefix}plan check mismath get errors: {errors}")
            err += errors

        current_app.logger.info(
            f"{prefix}dependency_case_sequence: {dependency_case_sequence}")
        current_app.logger.info(f"{prefix}case_sequence: {case_sequence}")
        if err:
            current_app.logger.error(f"{prefix}parse plan get err: {err}")
        return dependency_case_sequence, case_sequence, err

    @classmethod
    def _get_cases_by_group_id(cls, group_id):
        all_cases = Case.query.filter(
            Case.group_id == group_id, Case.deleted == False).order_by(
            Case.updated_time.asc()).all()
        sub_groups = Group.query.filter_by(
            mum_id=group_id, deleted=False).all()
        for sub_group in sub_groups:
            tmp_cases = cls._get_cases_by_group_id(sub_group.id)
            all_cases.extend(tmp_cases)
        return all_cases

    @classmethod
    def parse_cases(cls, suite_instance, case_id_sequence_list, data, prefix=''):
        # plan = {
        #     "sequence": {
        #         # case_id0: [case_idm, case_idn],
        #         # case_id1: [case_idx, case_idy],
        #     },
        #     "dependency": {
        #         # case_id0: {
        #         #     "a": case_idm, "x",
        #         #     "b": case_idn, "y",
        #         # }
        #     },
        #     "must_serial": [],
        # }
        priority = data.get('common', {}).get("priority", [])
        if not priority:
            priority = data.get('common', {}).get(
                "extra", {}).get("priority", [])
            if not priority:
                priority = ["P0", "P1", "P2", "P3"]
        priority = [item.upper() for item in priority]

        plan = suite_instance.plan
        if plan is None:
            plan = {}

        for case_id in suite_instance.case_id_list:
            case_instance = Case.query.filter_by(
                id=case_id, deleted=False).first()
            if case_instance:
                if case_instance.id not in case_id_sequence_list and case_instance.type in CaseType_to_ARGS and case_instance.priority.upper() in priority:
                    case_id_sequence_list.append(case_instance.id)

        current_app.logger.info(f"{prefix}suite name: {suite_instance.name}")
        current_app.logger.info(
            f"{prefix}suite_instance.schedule: {suite_instance.schedule}")

        if suite_instance.run_all_config.get('run_all', []):
            # All cases in a project need to be executed
            for config in suite_instance.run_all_config['run_all']:
                all_cases = []
                if config.get('type') == 'project':
                    all_cases = Case.query.filter(
                        Case.project_id == config.get('id'), Case.deleted == False).order_by(
                        Case.updated_time.asc()).all()
                elif config.get('type') == 'group':
                    all_cases = cls._get_cases_by_group_id(config.get('id'))

                for case in all_cases:
                    if case.id not in case_id_sequence_list and case.type in CaseType_to_ARGS and case.priority.upper() in priority:
                        case_id_sequence_list.append(case.id)

        # if plan.get('run_all_case', False) is False and suite_instance.schedule and \
        #         suite_instance.schedule.get('run_all', False) is False:
        #     # Update the case_id_list in the casesuite table
        #     suite_instance.case_id_list = case_id_sequence_list
        #     suite_instance.save()

        # Handling inter-case dependencies and execution order
        dependency_case_sequence, case_sequence, errors = cls.parse_plan(
            plan, prefix)

        other_serial_cases = []
        other_parallel_cases = []
        if data.get('common', {}).get('serial', False) or plan.get('serial', False) or \
                (suite_instance.schedule and suite_instance.schedule.get('serial', False)):
            for case_id in case_id_sequence_list:
                if case_id in dependency_case_sequence + case_sequence:
                    continue
                else:
                    other_serial_cases.append(case_id)
        else:
            for case_id in plan.get('must_serial', []):
                if case_id not in dependency_case_sequence + case_sequence:
                    other_serial_cases.append(case_id)

            other_parallel_cases = list(set(case_id_sequence_list) - set(
                dependency_case_sequence + case_sequence + other_serial_cases))

        # show schedule sequence
        current_app.logger.info(f"""{prefix}
                        dependency_case_sequence: {dependency_case_sequence}, 
                        case_sequence: {case_sequence}, 
                        other_serial_cases: {other_serial_cases}, 
                        other_parallel_cases: {other_parallel_cases}""")

        return dependency_case_sequence, case_sequence, other_serial_cases, other_parallel_cases, errors

    @classmethod
    def get_executor_env(cls, executor, casetype):
        ret = None
        if executor in OFFICIAL_ExecutorType:
            ret = cls.topos_map[casetype]
        else:
            ret = 'common'
        return ret

    @classmethod
    def get_timeout(cls, case_instance=None):
        '''
            min:         1 * 60s
            max:        20 * 60s
            default:     5 * 60s
            if history < min:
                use default
            elif history > max:
                use history * 120%
            else # min < history < max
                use max(history * 2, default)
        '''
        # min_timeout = 1 * 60
        # max_timeout = 60 * 60
        # default_timeout = DEFAULT_CASE_TIMEOUT
        #
        # if case_instance.timeout and case_instance.timeout != default_timeout:
        #     return case_instance.timeout
        #
        # ret = default_timeout
        # last_result = CaseResult.query.filter_by(
        #     case_id=case_instance.id, status='pass').order_by(CaseResult.updated_time.desc()).limit(1).first()
        # if last_result:
        #     duration = last_result.updated_time - last_result.created_time
        #     total_seconds = duration.total_seconds()
        #     if total_seconds:
        #         total_seconds = int(total_seconds)
        #         if total_seconds < min_timeout:
        #             ret = default_timeout
        #         elif max_timeout < total_seconds:
        #             ret = max_timeout
        #         else:
        #             ret = min(
        #                 max(default_timeout, total_seconds * 2), max_timeout)
        # hardcode it
        timeout = case_instance.timeout or DEFAULT_CASE_TIMEOUT if case_instance else DEFAULT_CASE_TIMEOUT
        return timeout

    @classmethod
    def get_group(cls, case_instance):
        if case_instance.base_group:
            return case_instance.base_group

        groups = case_instance.group.get_grandmas(case_instance.group_id)
        if len(groups) > 1:
            group_id = groups[-2]
            group_name = Group.query.get(group_id).name

        elif len(groups) == 1:
            group_id = case_instance.group_id
            group_name = Group.query.get(group_id).name

        else:
            group_name = case_instance.group.name
        return group_name

    @staticmethod
    def input_parse(case_instance, dependency, case_output_cache, prefix=''):
        err = ''
        case_id = str(case_instance.id)
        inputs_after_parse = case_instance.inputs
        if case_id in dependency:
            try:
                inputs_after_parse = copy.deepcopy(case_instance.inputs)
                is_list = False
                if isinstance(inputs_after_parse, list):
                    is_list = True
                for k, v in dependency[case_id].items():
                    if len(v) != 2:
                        if is_list:
                            for input_dict in inputs_after_parse:
                                if input_dict['name'] == k:
                                    input_dict['value'] = v[0]
                                    break
                        else:
                            inputs_after_parse[k] = v[0]
                        continue
                    (mum_case_id, mum_k) = v
                    if mum_case_id in case_output_cache:
                        outputs = case_output_cache[mum_case_id]
                        if outputs and mum_k in outputs:
                            if is_list:
                                for input_dict in inputs_after_parse:
                                    if input_dict['name'] == k:
                                        input_dict['value'] = outputs[mum_k]
                                        break
                            else:
                                inputs_after_parse[k] = outputs[mum_k]
                        else:
                            err += f"case {case_instance}'s dependency case: {mum_case_id} has no {mum_k}!"
                    else:
                        err += f"case {case_instance}'s dependency case: {mum_case_id} still has no result!"
                        break
            except Exception:
                current_app.logger.error(
                    f'{prefix} Some wrong happened in input_parse: {traceback.format_exc()}')

        return inputs_after_parse, err

    @classmethod
    def cancel_task(cls, channel_id):
        caseresult_instance = CaseResult.query.filter_by(id=channel_id).first()
        caseresult_instance.status = 'canceled'
        caseresult_instance.save()
        worker = caseresult_instance.worker

        if not worker:
            current_app.logger.info(
                "Unable to find the corresponding worker for execution!")
            return

        task = TaskFactory.get_cancel_task(channel_id)
        mymq = init_mymq()
        mymq.send(worker["exchange"], worker["routing_key"], json.dumps(task))
        current_app.logger.info(
            f"Send task to {worker['routing_key']} to stop {channel_id}")
        mymq.close()


class TaskFactory(BaseTask):

    @classmethod
    def get_import_task(cls, category, project_instance, py_modules_path, log_file,
                        author, token, import_type, cases_info_file):
        task = cls.init_task_v2()
        task.update({
            "action": "import",
            "case_category": category,
            "project_id": project_instance.id,
            "project_path": cls._get_attr_from_extra(project_instance, "project_path", category),
            "host": current_app.config['WEB_HOST'],
            "py_modules": py_modules_path,
            "logfile": log_file,
            "executor_path": cls._get_executor_path(project_instance, category),
            "author": author,
            "use_file_as_inputs": cls._get_attr_from_extra(project_instance, "use_file_as_inputs",
                                                           category) or False,
            "productline": project_schema.dump(project_instance)["productline"],
            "token": token,
            "cases_info_file": cases_info_file,
            'import_type': import_type,
            "timeout": 60 * 60
        })
        return task

    @classmethod
    def set_origin_result(cls, result_hd, channel_id):
        result = cls.init_result()
        result.update({
            "status": "pending",
        })
        result_hd.set(channel_id,
                      json.dumps(result), ex=30 * 60 * 60)

    @classmethod
    def get_exec_task(cls, case_result, case_instance, inputs, data, project, env_name, worker_env):
        task = cls.init_task_v2()
        task.update({
            "action": "exec",
            "channel_id": case_result.id,
            "case_id": case_instance.id,
            "case_name": case_instance.name,
            "case_category": ExecutorType[case_instance.category.lower()],
            "case_type": case_instance.type,
            "steps": [],
            "inputs": inputs if inputs else case_instance.inputs,
            "outputs": case_instance.outputs,
            "case_extra": case_instance.extra,
            "caseresult_id": case_result.id,
            "suiteresult_id": data.get('suiteresult_id', None),
            "project_id": project.id,
            "project_name": project.name,
            "project_path": cls._get_attr_from_extra(project, "project_path", case_instance.category.lower()),
            "py_modules": os.path.join(project.get_product_path(), "pips"),
            "logfile": case_result.get_absolute_logdir(),
            "executor_path": cls._get_executor_path(project, case_instance.category.lower()),
            "env": env_name,
            "region": data.get('api', {}).get('region', "").lower(),
            "author": case_instance.author,
            "runner": data['author'],
            "timeout": ExecUtils.get_timeout(case_instance),  # seconds
            "use_file_as_inputs": cls._get_attr_from_extra(project, "use_file_as_inputs",
                                                           case_instance.category) or False,
            "runtime_args": {
                "exec_args": {
                    # "debug_mode": data.get("common", {}).get("debug_mode", False),
                    # "enable_proxy": data.get("common", {}).get("enable_proxy", False),
                    "common": data.get("common", {}),
                    # "official_web": data.get("official_web", {}),
                    # "offcial_mobile": data.get("official_mobile", []),
                    "api": data.get("api", {})
                },
                "code_coverage": data.get("code_coverage", {})
            },
            "executor_type": case_instance.category.lower(),
            "executor_env": worker_env
        })
        return task

    @staticmethod
    def get_cancel_task(channel_id):
        return {
            "action": "canceled",
            "channel_id": channel_id
        }

    @staticmethod
    def get_postwomen_task(exec_id, ):
        return {
            "action": "postwomen",
            "caseresult_id": exec_id,
            "logfile": os.path.join(current_app.instance_path, current_env.POSTWOMEN_LOG)
        }


class DataManagement:
    def __init__(self, data):
        self.data = self._deal_data(data)
        self.datas = {}
        self.count = 1
        self.env_name = data.get('api', {}).get(
            'env', {}).get('name', 'test-env')
        self.region = data.get('api', {}).get('region', "sg").lower()
        self.pfb = data.get("api", {}).get("routing", {}).get("pfb", "")
        self.author = data.get('author', 'no-one')
        self.suite_result_id = data.get('suiteresult_id', None)

        self._init_datas()

    @staticmethod
    def _deal_data(data):
        new_data = copy.deepcopy(data)
        routing = data.get("api", {}).get("routing", {})
        if routing and new_data.get("code_coverage", {}).get("status", False):
            new_data['code_coverage']['args']['routing'] = routing
        return new_data

    @staticmethod
    def _insert_install_app(devices, install_app):
        if install_app:
            for device in devices:
                device["installApp"] = install_app
        return devices

    @classmethod
    def _spilt_mobile(cls, main_devices, sub_devices):
        main_devices = cls._insert_install_app(main_devices.get("devices", []),
                                               main_devices.get("installApp", {}))
        sub_devices = cls._insert_install_app(sub_devices.get("devices", []),
                                              sub_devices.get("installApp", {}))
        main_devices_num = len(main_devices)
        sub_devices_num = len(sub_devices)

        if not main_devices and not sub_devices:
            return [[]]

        if not main_devices or not sub_devices:
            # Only the main test device is selected or only the helper test device is selected or none of them are selected
            # return: [[{}], [{}] ...]
            return_devices = main_devices if main_devices else sub_devices
            return [[device] for device in return_devices]

        if main_devices_num == 1 and sub_devices_num == 1:
            # only one param
            # return: [[{}, {}]]
            return [main_devices + sub_devices]

        # mutiple param
        # return: [[{}, {}], [{}, {}] ...]
        if main_devices_num >= sub_devices_num:
            min_devices = sub_devices
            max_devices = main_devices
            min_devices_num = sub_devices_num
            max_devices_num = main_devices_num
        else:
            min_devices = main_devices
            max_devices = sub_devices
            min_devices_num = main_devices_num
            max_devices_num = sub_devices_num
        min_devices *= (max_devices_num // min_devices_num + 1)
        min_devices = min_devices[:max_devices_num]
        return list(zip(max_devices, min_devices))

    @classmethod
    def _split_mutiple_param(cls, data):
        """{
                "author": gong.xun@shopee.com,
                "common": {
                    "enable_proxy": true,
                    "debug_mode": true,
                    "update": true,
                    "serial": true
                },
                "api": {
                    "env": {
                        "name": "test-env",
                        "id": 1344
                    },
                    "pfb": "dsfa"
                },
                "code_coverage": {
                    "status": true,
                    "clear": false,
                    "cov_type": "go", # go/java
                    "args": {
                        "config": [{
                            "delta": {
                                "base": ""
                            },
                            "instances": {
                                "account-bff-code-coverage-test-fr": {
                                    "filter": {
                                        "include": [],
                                        "exclude": ["\\.gen\\.go", "\\.pb\\.go", "_test\\.go"]
                                    },
                                    "module_path": ""
                                }
                            }
                        }]
                    }
                },
                "official_web": {
                    "browser": "chrome",
                    "version": "99.0.4844.94"
                },
                "official_mobile": {
                    "android_main_device_id": {
                        "devices": [{
                            "value": "W-K130-TMV <-> W-K130-TMV <-> 8.1.0",
                            "description": "W-K130-TMV <-> W-K130-TMV <-> 8.1.0",
                            "key": "W-K130-TMV <-> W-K130-TMV <-> 8.1.0",
                            "group": "Android",
                            "notes": "Android主测设备",
                            "type": "selectbox",
                            "name": "android_main_device_id"
                        }]
                    },
                    "android_sub_device_id": {
                        "devices": [{
                            "value": "SM-J250F <-> SM-J250F <-> 7.1.1",
                            "description": "SM-J250F <-> SM-J250F <-> 7.1.1",
                            "key": "SM-J250F <-> SM-J250F <-> 7.1.1",
                            "group": "Android",
                            "notes": "Android辅测设备",
                            "type": "selectbox",
                            "name": "android_sub_device_id"
                        }]
                    }
                }
            }"""

        datas = {}
        try:
            if isinstance(data.get("official_mobile", []), list):
                datas = {0: data}
                return datas

            official_mobile = data.get("official_mobile", {})
            mobile_datas = cls._spilt_mobile(official_mobile.get("android_main_device_id", {}),
                                             official_mobile.get("android_sub_device_id", {})) + \
                cls._spilt_mobile(official_mobile.get("ios_main_device_id", {}),
                                  official_mobile.get("ios_sub_device_id", {}))

            if mobile_datas == [[], []]:
                # Handling cases without official mobile parameters
                mobile_datas = [[]]

            if len(mobile_datas) > 1:
                mobile_datas = [datas for datas in mobile_datas if datas]

            for index, mobile in enumerate(mobile_datas):
                template = copy.deepcopy(data)
                template["official_mobile"] = list(mobile)
                datas[index] = template

        except Exception as err:
            current_app.logger.error(
                f"Some wrong happened while splitting multiple parameters: {traceback.format_exc()}")

        return datas

    def _init_datas(self, ):
        if not self.data.get("official_mobile"):
            self.data["official_mobile"] = {}

        self.datas = self._split_mutiple_param(self.data)
        self.count = len(self.datas)

        self._remove_datas_key('suiteresult_id')

    def update_datas(self, args):
        for index in range(self.count):
            for k, v in args.items():
                self.datas[index][k] = v
                self.data[k] = v

    def _remove_datas_key(self, k):
        for index in range(self.count):
            if k in self.datas[index]:
                del self.datas[index][k]


class BaseExec:
    def __init__(self, dataMgr=None, cancel_signal=None, cases_list=None, prefix='', retry=0, record_id=None):
        self.app = current_app._get_current_object()
        self.cases_list = cases_list if cases_list else []
        self.prefix = prefix
        self.cancel_signal = cancel_signal
        self.retry = retry
        self.dataMgr = dataMgr

        self.result_hd = MyRedis(current_app.config['URL_FOR_RESULT'])
        self.mymq = init_mymq()

        self.record_key = int(str(os.getpid()) + str(int(time.time())))
        self.cases_status = defaultdict(dict)
        self.record_lock = threading.Lock()

        if self.cases_list:
            self._init_record()

        # use to return result id
        self.record_id = record_id

    def set_cases_list(self, cases_list):
        self.cases_list = cases_list
        self._init_record()

    @staticmethod
    def _load_json(s):
        def _load(dic):
            tmp = {}
            for k, v in dic.items():
                if isinstance(k, str):
                    try:
                        k = int(k)
                    except Exception:
                        pass
                if isinstance(v, dict):
                    v = _load(v)
                # elif isinstance(v, list):
                #     new_v = []
                #     for v_item in v:
                #         if isinstance(v_item, dict):
                #             v_item = _load(v_item)
                #         new_v.append(v_item)
                #     v = new_v
                tmp[k] = v
            return tmp

        data = json.loads(s)
        return _load(data)

    def _init_record(self, ):
        # {
        #     "case_id": {
        #         "status": "pass/fail/canceled",
        #         "exec_record": {
        #             data_index: [
        #                 {
        #                     "result_id": 123,
        #                     "status": "pass",
        #                     "other_results": {
        #                         result_id: status
        #                     }
        #                 }
        #             ]
        #         }
        #     }
        # }
        record = {
            case_id: {
                "status": "pending",
                "exec_record": {
                    index: [] for index in range(self.dataMgr.count)
                }
            } for case_id in self.cases_list
        }
        self.result_hd.set(
            self.record_key, json.dumps(record), ex=24 * 60 * 60)

    def _update_record(self, case_id, data_index=0, results=None, status=''):
        """
        results:
            {
                "result_id": 123,
                "status": "pass",
                "other_results": {
                    result_id: status
                }
            }
        """
        try:
            record = self._load_json(self.result_hd.get(self.record_key))
            if results:
                updated = False
                for result in record[case_id]["exec_record"][data_index]:
                    if result["result_id"] == results["result_id"]:
                        result["status"] = results["status"]
                        result["other_results"] = results["other_results"]
                        updated = True

                if not updated:
                    record[case_id]["exec_record"][data_index].append(results)
                record[case_id]["status"] = results["status"]
            if status:
                record[case_id]["status"] = status
            self.result_hd.set(
                self.record_key, json.dumps(record), ex=24 * 60 * 60)

        except Exception:
            current_app.logger.error(f"{self.prefix} Update record failed! case_id: {case_id}, data_index: {data_index}"
                                     f"result: {results}, error: {traceback.format_exc()}")

    @staticmethod
    def _wait_available_worker(case_instance, worker_env, param_list, prefix):
        from app.libs import workermgr
        while True:
            theworker, locked_devices = workermgr.acquire_worker_resource(
                case_instance.category.lower(), worker_env, case_instance.type,
                param_list)
            if theworker:
                current_app.logger.info(
                    f"{prefix} case: {case_instance.name}, get worker: {theworker['name']}")
                break
            else:
                current_app.logger.warn(
                    f"{prefix} no worker resource for {case_instance.name}, wait 5s...")
                time.sleep(5)
        return theworker, locked_devices

    def _create_case_result(self, case_instance, data_index):
        case_result = CaseResult(**{
            "status": "pending",
            "case_id": case_instance.id,
            "case_name": case_instance.name,
            "group_name": ExecUtils.get_group(case_instance),
            "env_name": self.dataMgr.env_name,
            "details": [
                {
                    "log": "",
                    "html_file": "",
                    "exec_data": self.dataMgr.datas[data_index]
                }
            ],
            "runner": self.dataMgr.author,
            "author": case_instance.author,
            "suiteresult_id": self.dataMgr.suite_result_id,
            "duration": 0,
            "debug_mode": case_instance.is_draft
        })
        case_result.save()

        if self.record_id:
            # return case result id, only once
            self.result_hd.set(self.record_id, json.dumps(
                {"case_result_id": case_result.id}), ex=10 * 60)
            self.record_id = None

        return case_result

    def _send_task_to_worker(self, theworker, case_instance, locked_devices, worker_env, task, prefix):
        if theworker:
            if case_instance.type in MobileCaseType:
                ok = self.mymq.send('thatworker',
                                    f"{theworker['name']}__{theworker['env']}", json.dumps(task))
                worker_info = {
                    "exchange": "thatworker",
                    "routing_key": f"{theworker['name']}__{theworker['env']}",
                    "locked_devices": locked_devices,
                    "locked_devices_released": False
                }
            else:
                ok = self.mymq.send('oneworker',
                                    f"{case_instance.category.lower()}__{worker_env}", json.dumps(task))
                worker_info = {
                    "exchange": "oneworker",
                    "routing_key": f"{case_instance.category.lower()}__{worker_env}"
                }
        else:
            ok = self.mymq.send('oneworker',
                                f"{case_instance.category.lower()}__{worker_env}", json.dumps(task))
            worker_info = {
                "exchange": "oneworker",
                "routing_key": f"{case_instance.category.lower()}__{worker_env}"
            }

        current_app.logger.info(
            f"{prefix} send to exchange: {worker_info['exchange']}, "
            f"routing_key: {worker_info['routing_key']},"
            f"locked_devices: {worker_info.get('locked_devices')},"
            f"status: {ok}")

        return ok, worker_info

    def _send_cancel_task_to_worker(self, exchange, routing_key, task):
        self.mymq.send(exchange, routing_key, json.dumps(task))
        current_app.logger.info(
            f"Send task to {routing_key} to stop {task['channel_id']}")

    def _run_one_case(self, case_instance, data_index, inputs=None, prefix=''):
        """
            data = {
                "env_id": json_data["env_id"],
                "author": request.headers.get('email', 'no-user'),
                "code_coverage": json_data.get("runtime_args", False),
                "runtime_args": json_data.get("runtime_args")
            }

            runtime_args:
                mobile: [{k, v, }, ]
                ui: [{}]
        """
        err = ''
        case_result = None
        try:
            case_id = case_instance.id
            project = case_instance.project
            worker_env = ExecUtils.get_executor_env(
                case_instance.category.lower(), case_instance.type)
            worker_type = f"{case_instance.category.lower()}_{worker_env}"
            env_name = self.dataMgr.env_name

            case_result = self._create_case_result(
                case_instance, data_index)
            logger = RunLogger(
                case_result.id, case_result.get_absolute_logdir())
            case_prefix = f"[{case_result.id}]"

            current_data = copy.deepcopy(self.dataMgr.datas[data_index])
            theworker, locked_devices = self._wait_available_worker(
                case_instance, worker_env, current_data.get(worker_type, []), case_prefix)
            # 用户没有选择设备，平台随机选取一个设备
            if locked_devices and worker_env == 'mobile' and not current_data.get(worker_type, []):
                current_data[worker_type] = [{
                    "name": f'{case_instance.type.strip("Topo").lower()}_main_device_id',
                    "value": locked_devices[0]['udid']
                }]

            task = TaskFactory.get_exec_task(case_result, case_instance, inputs, current_data,
                                             project, env_name, worker_env)
            TaskFactory.set_origin_result(self.result_hd, task['channel_id'])
            current_app.logger.info(
                f"{case_prefix} To run project={project.name}, case={case_instance.id, case_instance.name},"
                f"caseresult={case_result.id}, timout={task['timeout']}")
            ok, worker_info = self._send_task_to_worker(theworker, case_instance, locked_devices, worker_env, task,
                                                        case_prefix)
            case_result.worker = worker_info
            case_result.save()

            if not ok:
                raise BaseException

            return task['channel_id'], "pending", None

        except Exception as err:
            current_app.logger.error(f"{case_prefix}{traceback.format_exc()}")
            if case_result:
                case_result.status = 'error'
                case_result.reason = CASE_UNPASS_REASON['ERROR']['system_error']
                case_result.save()

            return None, "error", str(err)

    def cancel_cases(self, channel_id_list):
        for channel_id in channel_id_list:
            case_result_instance = CaseResult.query.get(channel_id)
            case_result_instance.status = 'canceled'
            case_result_instance.save()
            worker = case_result_instance.worker
            self.cases_status[channel_id] = {
                "case_id": case_result_instance.case_id,
                "case_status": 'canceled',
                "duration": 0,
                "standard_report": ''
            }

            if not worker:
                current_app.logger.info(
                    "Unable to find the corresponding worker for execution!")
                continue

            cancel_task = TaskFactory.get_cancel_task(channel_id)
            self._send_cancel_task_to_worker(
                worker["exchange"], worker["routing_key"], cancel_task)

    def get_case_result_not_done(self):
        record = self.result_hd.get(self.record_key)
        if record:
            record = self._load_json(record)
        else:
            return False, [], []

        is_done = True
        not_done = []
        need_retry = []
        for case_id, case_info in record.items():
            if case_info['status'] in ['pass', ]:
                # The case has been executed pass
                continue

            for data_id, case_results in case_info['exec_record'].items():
                exec_count_every_data = len(case_results)
                if exec_count_every_data < 1:
                    # First execute not done
                    is_done = False

                elif any([result['status'] in TaskStatus_UNDONE for result in case_results]):
                    # pending or running
                    is_done = False

                elif self.retry and case_results[-1]['status'] in TaskStatus_UNSUCCESS and \
                        exec_count_every_data < (1 + self.retry):
                    is_done = False
                    if case_info['status'] != 'retry':
                        need_retry.append(case_id)
                        with self.record_lock:
                            self._update_record(case_id, status='retry')

                not_done += [[case_id, data_id, result['result_id']] for result in case_results
                             if result['status'] not in TaskStatus_DONE]

        return is_done, not_done, need_retry

    def run_handler(self, run_queue):
        with self.app.app_context():
            while True:
                try:
                    case_id = run_queue.get()
                    if self.cancel_signal and self.cancel_signal.isSet():
                        break

                    case_instance = Case.query.get(case_id)
                    case_name = case_instance.name

                    current_app.logger.info(
                        f"{self.prefix} To run case, case_id: {case_id}, case_name: {case_name}...")

                    for index in range(self.dataMgr.count):
                        if self.cancel_signal and self.cancel_signal.isSet():
                            break

                        channel_id, status, error = self._run_one_case(
                            case_instance, index, prefix=self.prefix)

                        if error:
                            current_app.logger.error(f"{self.prefix} Run case error, case_id: {case_id}, "
                                                     f"case_name: {case_name}, error: {error}")

                        with self.record_lock:
                            self._update_record(
                                case_id, index, {"result_id": channel_id, "status": status})

                except Exception:
                    current_app.logger.error(f"{self.prefix} Some wrong happened in run handler: "
                                             f"{traceback.format_exc()}")

    def check_case_result(self, channel_id, caseresult_instance, case_instance):
        ret = self.result_hd.get(channel_id)
        case_status = ""
        outputs = {}
        duration = 0
        standard_report = []
        save_info = {}
        other_results = []
        if ret:
            ret = self._load_json(ret)
            now = datetime.datetime.now()
            timeout = case_instance.timeout or DEFAULT_CASE_TIMEOUT

            if ret["status"].lower() in TaskStatus_DONE:
                case_status = ret["status"].lower()
                outputs = ret.get("outputs", {})
                duration = float(ret.get("duration", 0))
                standard_report = ret.get("standard_report", [])
                save_info = ret.get("save_info", {})
                other_results = ret.get("other_results", [])
            else:
                if ret["status"].lower() == 'running':
                    # to update worker info
                    save_info = ret.get("save_info", {})

                # Case runs beyond the set timeout
                if caseresult_instance.created_time + datetime.timedelta(seconds=timeout) < now:
                    # The current time has exceeded the timeout time specified in the case
                    case_status = 'timeout'
                    save_info = {
                        "status": "timeout"
                    }
                    duration = timeout
                    current_app.logger.error(f"{self.prefix}case: {case_instance.name}, channel: {channel_id}, "
                                             f"case timeout!")

                else:
                    case_status = ret["status"].lower()
        else:
            case_status = 'missing'
            current_app.logger.error(
                f"{self.prefix}case: {case_instance.name}, channel: {channel_id} result missing!")

        return case_status, outputs, duration, standard_report, save_info, other_results

    def _common_put_for_case_result(self, obj, json_data):
        if json_data.get('details', []):
            json_data['details'][0]['exec_data'] = obj.details[0].get(
                'exec_data', {})

        obj.put_check(json_data)
        for k, v in json_data.items():
            if k in ('id', 'created_time', 'updated_time'):
                continue
            elif isinstance(v, (dict, list)):
                if k in ['worker', 'device_info'] and getattr(obj, k):
                    tmp_v = copy.deepcopy(getattr(obj, k))
                    tmp_v.update(v)
                else:
                    tmp_v = copy.deepcopy(v)
                setattr(obj, k, tmp_v)
            else:
                setattr(obj, k, v)

        obj.deleted = False
        obj.save()

    def _common_post_for_case_result(self, results, case_id, worker):
        ret = {}
        for caseresult_info in results:
            case = Case.query.get(case_id)
            caseresult_info.update({
                "author": case.author,
                "env_name": self.dataMgr.env_name,
                "case_id": case.id,
                "case_name": case.name,
                "runner": self.dataMgr.data['author'],
                "suiteresult_id": self.dataMgr.suite_result_id,
                "worker": worker
            })
            CaseResult.post_check(caseresult_info)
            caseresult = caseresult_schema.load(
                utils.del_id_none(caseresult_info))
            caseresult.save()
            ret[caseresult.id] = caseresult.status
        return ret

    def save_case_result(self, case_result, ):
        results, outputs, duration, standard_report, save_info = {}, {}, 0, '', {}
        if not case_result:
            current_app.logger.error(f"{self.prefix} case result not found!")
            return results, outputs, duration, standard_report, save_info

        db.session.refresh(case_result, ['status'])
        current_status = case_result.status
        case_status, outputs, duration, standard_report, save_info, other_results = \
            self.check_case_result(
                case_result.id, case_result, case_result.case)
        save_info["duration"] = duration
        if case_status in TaskStatus_DONE and current_status not in TaskStatus_DONE:
            if case_status == 'pass' and case_result.case.is_draft == True:
                case_result.case.is_draft = False
                case_result.case.save()
            case_result.status = case_status
            self.cases_status[case_result.id] = {
                "case_id": case_result.case_id,
                "case_status": case_status,
                "duration": duration,
                "standard_report": standard_report
            }
        elif case_status == 'running' and current_status == 'pending':
            case_result.status = 'running'
            case_result.worker.update(save_info.get("worker", {}))
        elif case_status == 'canceled':
            case_result.status = 'canceled'
        elif current_status == case_status:
            return results, outputs, duration, standard_report, save_info
        else:
            current_app.logger.error(f"{self.prefix} case result status error: "
                                     f"current is {current_status} while new status is {case_status}")
            return results, outputs, duration, standard_report, save_info
        current_app.logger.debug(f"case result: {case_result.id} "
                                 f"from {current_status} to {case_status}")

        self._common_put_for_case_result(case_result, save_info)
        ret = self._common_post_for_case_result(
            other_results, case_result.case_id, case_result.worker)
        results = {
            "result_id": case_result.id,
            "status": case_status,
            "other_results": ret
        }

        return results, outputs, duration, standard_report, save_info

    def update_to_case_management(self, automation_result, status, author, case_id):
        pass

    def result_handler(self, exec_queue, timeout):
        with self.app.app_context():
            suite_result = None
            log_count = 0
            current_app.logger.info(
                f"{self.prefix} Exec record key is {self.record_key}")
            while timeout > 0:
                try:
                    if self.cancel_signal and self.cancel_signal.is_set():
                        break

                    is_done, case_result_not_done, need_retry = self.get_case_result_not_done()

                    if log_count % 60 == 0:
                        current_app.logger.info(f"{self.prefix} Result handler still alive, is_done: {is_done};"
                                                f"case_not_done: {case_result_not_done};"
                                                f"need_retry: {need_retry}")

                    if is_done:
                        # Execution complete
                        break

                    for case_id in need_retry:
                        # to retry
                        exec_queue.put(case_id)

                    for case_id, data_index, case_result_id in case_result_not_done:
                        try:
                            case_result = CaseResult.query.get(case_result_id)
                            if suite_result is None:
                                suite_result = case_result.suiteresult
                            results, _, _, _, save_info = self.save_case_result(
                                case_result, )
                            with self.record_lock:
                                self._update_record(
                                    case_id, data_index, results)
                            self.update_to_case_management(save_info.get('details', [{}])[0].get('html_file', ''),
                                                           case_result.status, self.dataMgr.data.get(
                                                               'author', ''),
                                                           case_id)

                        except Exception:
                            current_app.logger.error(f"Some wrong happened in loop: \n"
                                                     f"{traceback.format_exc()}")

                    if case_result_not_done and suite_result:
                        suite_result.update_statistics()

                except Exception:
                    current_app.logger.error(f"Some wrong happened in result handler: \n"
                                             f"{traceback.format_exc()}")

                finally:
                    time.sleep(1)
                    timeout -= 1
                    log_count += 1

    def parallel_run(self, ):
        try:
            exec_queue = queue.Queue()
            timeout = len(self.cases_list) * ExecUtils.get_timeout()

            exec_thread = szqa_utils.thread.ExtThread(
                target=self.run_handler,
                args=(exec_queue,)
            )
            exec_thread.start()

            result_thread = szqa_utils.thread.ExtThread(
                target=self.result_handler,
                args=(exec_queue, timeout,)
            )
            result_thread.start()

            for case_id in self.cases_list:
                exec_queue.put(case_id)

            result_thread.join()

            is_done, case_result_not_done, _ = self.get_case_result_not_done()
            if self.cancel_signal and self.cancel_signal.is_set():
                current_app.logger.info(f"{self.prefix} Run canceled!")
                self.cancel_cases([result[2]
                                   for result in case_result_not_done])
            else:
                if not is_done:
                    current_app.logger.error(f"{self.prefix} Execute timeout! Still have these case not done:\n"
                                             f"{case_result_not_done}")
                    for case_id, _, case_result_id in case_result_not_done:
                        case_result = CaseResult.query.get(case_result_id)
                        current_status = case_result.status
                        if current_status in TaskStatus_DONE:
                            current_app.logger.error(
                                f"{self.prefix} case result: {case_result_id} 's status is {current_status},"
                                f"while status in redis is not done")
                        else:
                            case_result.status = 'timeout'
                            case_result.save()

                        self.cases_status[case_result_id] = {
                            "case_id": case_id,
                            "case_status": case_result.status,
                            "duration": DEFAULT_CASE_TIMEOUT,
                            "standard_report": ''
                        }

                else:
                    current_app.logger.info(f"{self.prefix} Run done!")

            exec_thread.stop()

        except Exception:
            current_app.logger.error(
                f"{self.prefix} Run error: {traceback.format_exc()}")


class SuiteExec(BaseExec):

    def __init__(self, data, suite_id=None, suite_result_id=None, record_id=None):
        super().__init__()
        self.dataMgr = DataManagement(data)
        self.suite_id = suite_id
        self.suite_result = None
        if suite_result_id:
            self.suite_result = SuiteResult.query.get(suite_result_id)
            self.suite_id = self.suite_result.casesuite_id
        self.cancel_signal = Event()
        self.cases_status = defaultdict(dict)

        # use to return result id
        self.record_id = record_id

    def _wait_project_update_done(self, suite_instance):
        if self.dataMgr.data.get("common", {}).get("update", False):
            from app.commons import Process
            process = Process(suite_instance.project_id)
            while process.is_exists() and not process.query()['finish']:
                current_app.logger.info(
                    f"{self.prefix} Case update not yet complete.")
                time.sleep(5)

    def goc_clear(self, ):
        from app.libs import Goc
        cov_args = self.dataMgr.data.get("code_coverage", {})
        goc = None
        if cov_args and cov_args.get("status", False):
            # Coverage data needs to be collected
            goc = Goc(self.suite_result.id, cov_args,
                      self.suite_result.casesuite.name)
            ok, err_msg = goc.goc_clear()
            if not ok:
                current_app.logger.info(
                    f"{self.prefix} Some errors occurred while executing the goc clear command: {err_msg}")
                self.suite_result.status = 'error'
                self.suite_result.save()
                raise Exception(f'Goc clear fail: {err_msg}')
        return goc, cov_args

    def _check_if_canceled(self):
        db.session.refresh(self.suite_result, ['status'])
        if self.suite_result.status == "canceled":
            current_app.logger.warn(
                f"{self.prefix}suite_result id: {self.suite_result.id} is canceled!")
            return True
        return False

    @classmethod
    def _walkdir(cls, dst_dir, subdir, dst_url):
        real_dst_dir = os.path.join(dst_dir, subdir)
        real_dst_url = os.path.join(dst_url, subdir)
        file_list = []
        if not os.path.exists(real_dst_dir):
            return file_list

        all_things = os.listdir(real_dst_dir)
        for item in all_things:
            if os.path.isfile(os.path.join(
                    real_dst_dir,
                    os.path.basename(item))) and not item.startswith('.'):
                file_list.append(os.path.join(real_dst_url, item))
            elif os.path.isdir(os.path.join(real_dst_dir, item)) and not item.startswith('.'):
                sub_file_list = cls._walkdir(dst_dir, os.path.join(
                    subdir, os.path.basename(item)), dst_url)
                file_list += sub_file_list
            else:
                continue
        return file_list

    def serial_run(self, cases, suite_instance):
        current_app.logger.info(
            f"{self.prefix} Start execution of cases that need to be serialised ... ")
        project_name = suite_instance.project.name
        suite_name = suite_instance.name
        suite_plan = suite_instance.plan
        run = True
        retry = self.dataMgr.data.get("common", {}).get("retry", 0)
        self.retry = retry
        need_retry = []
        cases_to_run = cases
        while run or retry:
            # if self._check_if_canceled():
            #     break

            if not run:
                # Failure to retry
                current_app.logger.info(
                    f"{self.prefix} Serial retry cases: {need_retry}")
                cases_to_run, need_retry = need_retry, []

            # serial run, need parse inputs/outputs
            case_output_cache = defaultdict(dict)
            for case_id in cases_to_run:
                # if self._check_if_canceled():
                #     break

                case_instance = Case.query.get(case_id)
                current_app.logger.info(
                    f"{self.prefix}To serial run project={project_name} suite={suite_name} "
                    f"case={case_instance.name}...")

                plan = suite_plan if suite_plan else {}
                inputs, new_err = ExecUtils.input_parse(
                    case_instance, plan.get('dependency', {}), case_output_cache, self.prefix)
                if new_err:
                    current_app.logger.error(
                        f"{self.prefix} Input parse error: {new_err}")

                for index, data in self.dataMgr.datas.items():
                    if self._check_if_canceled():
                        break

                    channel_id, status, error = self._run_one_case(
                        case_instance, index, inputs)
                    if error:
                        current_app.logger.error(f"{self.prefix} Run case error, case_id: {case_id}, "
                                                 f"case_name: {case_instance.name}, error: {error}")
                    else:
                        outputs = {}
                        duration = 0
                        standard_report = ''
                        log_count = 0
                        timeout = ExecUtils.get_timeout(case_instance)
                        caseresult_instance = CaseResult.query.get(channel_id)
                        while timeout:
                            if self._check_if_canceled():
                                break

                            results, outputs, duration, standard_report, _ = self.save_case_result(
                                caseresult_instance)
                            if results and results['status'] in TaskStatus_DONE:
                                break
                            else:
                                if log_count % 60 == 0:
                                    current_app.logger.info(
                                        f"{self.prefix} case: {case_instance.name}, channel: {channel_id} is ongoing!")
                                time.sleep(1)

                            log_count += 1
                            timeout -= 1

                        case_output_cache[case_instance.id] = outputs
                        db.session.refresh(caseresult_instance, ['status'])
                        if caseresult_instance.status not in TaskStatus_DONE:
                            caseresult_instance.status = 'timeout'
                            caseresult_instance.save()

                        self.cases_status[caseresult_instance.id] = {
                            "case_id": case_instance.id,
                            "case_status": caseresult_instance.status,
                            "duration": duration,
                            "standard_report": standard_report
                        }

                        if caseresult_instance.status.lower() in TaskStatus_UNSUCCESS:
                            need_retry.append(case_instance.id)

                self.suite_result.update_statistics()
            retry = retry - 1 if not run and retry > 0 else retry
            run = False

    def cancel_monitor(self, ):
        with self.app.app_context():
            current_app.logger.info(f"{self.prefix} Cancel monitor start!")
            suite_result = SuiteResult.query.get(self.suite_result.id)
            while True:
                try:
                    db.session.refresh(suite_result, ['status'])
                    if suite_result.status == "canceled":
                        current_app.logger.warn(
                            f"{self.prefix}suite_result id: {suite_result.id} is canceled!")
                        self.cancel_signal.set()
                        break

                except Exception:
                    current_app.logger.error(
                        f"{self.prefix} Cancel monitor error: {traceback.format_exc()}")

                time.sleep(1)

    def _auto_deploy(self, config, timeout=5400):
        log_path = current_app.config['SETUP_LOG_PATH']
        log_file = os.path.join(log_path, f'{self.suite_result.id}.log')
        if not os.path.exists(log_path):
            os.makedirs(log_path, exist_ok=True)

        ret_file = os.path.join(log_path, f'{self.suite_result.id}_ret.log')
        cmd = f"python run_increment_coverage.py " \
              f"-fb {config.get('feature_branch', '')} " \
              f"-gu {config.get('git_url', '')} " \
              f"-gtn {config.get('git_token_name', '')} " \
              f"-gt {config.get('git_token', '')} " \
              f"-dt {config.get('deploy_trigger', '')} " \
              f"-ib '{config.get('independent_env_branch', '')}' " \
              f"-ret {ret_file}"

        ret = -1
        try:
            with open(log_file, 'a+') as f:
                env = copy.deepcopy(os.environ)
                env['PYTHONPATH'] = env.get(
                    'PYTHONPATH', '') + ':/home/admin/instance'
                kwargs = {
                    "shell": True,
                    "stdout": f,
                    "stderr": f,
                    "cwd": current_app.config['SETUP_SCRIPT_PATH'],
                    "env": env
                }
                current_app.logger.info(f"{self.prefix} Setup auto deploy, call cmd: {cmd}, wait {timeout}s, \n"
                                        f"setup log will record in {log_file}")
                p = subprocess.Popen(cmd, **kwargs)
                ret = p.wait(timeout)
                current_app.logger.info(
                    f"{self.prefix} Execute done, return code is {ret}")

            if ret == 0:
                with open(ret_file, 'r') as f:
                    cov_config = json.load(f)
                    self.dataMgr.data['code_coverage']['args'].update(
                        cov_config)
                    self.suite_result.extra['exec_data'] = self.dataMgr.data
                    self.suite_result.save()

        except subprocess.TimeoutExpired:
            current_app.logger.error(f"Exec timeout: {traceback.format_exc()}")

        except Exception:
            current_app.logger.error(
                f"Some wrong happened while executing cmd: {traceback.format_exc()}")

        return True if ret == 0 else False, \
            log_file.replace(
                current_app.config['LOGS_PATH'], current_app.config['TOMCAT_HOST'])

    def setup(self, ):
        ok, log_file = True, ''
        try:
            setup = self.dataMgr.data.get("setup", {})
            auto_deploy_config = setup.get('auto_deploy', {})
            if auto_deploy_config:
                ok, log_file = self._auto_deploy(auto_deploy_config)

        except Exception:
            ok = False
            current_app.logger.error(
                f"{self.prefix} Setup error: {traceback.format_exc()}")

        return ok, log_file

    def send_msg(self, msg):
        try:
            body = {
                "channel": "all",
                "content": msg,
                "g_name": "",
                "u_name": self.dataMgr.author
            }
            requests.post(url=current_app.config['QABOT_NOTI'], headers={
                "accept": "application/json", "Content-Type": "application/json"}, json=body)

            current_app.logger.info(
                f"{self.prefix} Send message to {self.dataMgr.author} success!")

        except Exception:
            current_app.logger.error(
                f"{self.prefix} Send message error: {traceback.format_exc()}")

    def run(self, ):
        current_app.logger.info(
            f'SuiteExec to run suite: {self.suite_id}, args={self.dataMgr.datas}')
        goc = None
        try:
            suite_instance = Casesuite.query.get(self.suite_id)

            # Waiting for case update to complete
            self._wait_project_update_done(suite_instance)

            start_time = datetime.datetime.now()

            multi_param = True if self.dataMgr.count > 1 else False
            self.suite_result = SuiteResult(**{
                "created_time": self.dataMgr.data.get("start_time", datetime.datetime.now()),
                "runner": self.dataMgr.data['author'],
                "author": suite_instance.author,
                "casesuite_name": suite_instance.name,
                "project_name": suite_instance.project.name,
                "env_name": self.dataMgr.env_name,
                "total": len(suite_instance.case_id_list),
                "casesuite_id": self.suite_id,
                "status": "running",
                "extra": {"cases": {}, "exec_data": self.dataMgr.data,
                          "muti_param": multi_param, "param_count": self.dataMgr.count},
                "debug_mode": True,
                "pfb": self.dataMgr.pfb,
            })
            self.suite_result.save()

            if self.record_id:
                # return suite result id, only once
                self.result_hd.set(self.record_id, json.dumps(
                    {"suite_result_id": self.suite_result.id}), ex=25 * 60 * 60)
                self.record_id = None

            self.dataMgr.suite_result_id = self.suite_result.id
            self.dataMgr.update_datas({'suiteresult_id': self.suite_result.id})

            logger = RunLogger(self.suite_result.id,
                               current_env.SUITE_LOG_FOLDER)
            self.prefix = f"[{self.suite_result.id}]"
            current_app.logger.info(
                f"{self.prefix} run suite: {suite_instance.name}, result id: {self.suite_result.id}")

            cancel_monitor = szqa_utils.thread.ExtThread(
                target=self.cancel_monitor,
                args=()
            )
            cancel_monitor.start()

            # do something before executing
            ok, log_file = self.setup()
            if not ok:
                msg = f'hello, {self.dataMgr.author} \n' \
                      f'your plan {self.suite_result.casesuite.name} setup error, please see log: \n' \
                      f'{log_file} for detail, thank you.'
                self.send_msg(msg)
                raise Exception(f"Setup error, log in {log_file}")

            # Parsing the case to be executed
            case_id_sequence_list = []
            dependency_case_sequence, case_sequence, other_serial_cases, other_parallel_cases, _ = \
                ExecUtils.parse_cases(
                    suite_instance, case_id_sequence_list, self.dataMgr.data, self.prefix)

            self.suite_result.total = len(
                case_id_sequence_list) * self.dataMgr.count
            self.suite_result.save()

            # If goc is configured, clear the historical coverage data of the service under test
            goc, cov_args = self.goc_clear()

            temp_list = dependency_case_sequence + case_sequence + other_serial_cases
            self.serial_run(
                sorted(set(temp_list), key=temp_list.index), suite_instance)

            self.set_cases_list(other_parallel_cases)
            self.parallel_run()

            if goc and cov_args and cov_args.get("status", False):
                goc.goc_profile()
                goc.goc_unlock()

            db.session.refresh(self.suite_result, ['status', "extra"])
            if self.suite_result.status == "canceled":
                pass
            else:
                self.suite_result.status = 'done'
                self.suite_result.update_statistics('done')
            self.suite_result.extra["case_status"] = self.cases_status
            self.suite_result.save()
            # self.generate_standardised_report(
            #     self.suite_result, start_time, self.cases_status)

        except Exception:
            current_app.logger.error(f"{self.prefix} {traceback.format_exc()}")
            if self.suite_result:
                self.suite_result.status = 'error'
                self.suite_result.save()
            if goc:
                goc.goc_unlock()

        finally:
            if self.result_hd:
                self.result_hd.disconnect()
            if self.suite_result:
                logger = RunLogger(self.suite_result.id,
                                   current_env.SUITE_LOG_FOLDER)
                logger.release()

    def retry_suite(self, retry_cases):
        goc = None
        try:
            logger = RunLogger(self.suite_result.id,
                               current_env.SUITE_LOG_FOLDER)
            self.prefix = f"[{self.suite_result.id}]"
            current_app.logger.info(
                f'{self.prefix} {self.dataMgr.author} trigger SuiteExec to retry suite result:'
                f' {self.suite_result.id}, args={self.dataMgr.datas}')

            self.suite_result.status = 'running'
            for case_id in retry_cases:
                if not case_id:
                    continue

                caseresult_id_list = self.suite_result.extra.get(
                    'cases', {}).get(str(case_id), [])
                if len(caseresult_id_list) > 0:
                    case_result = CaseResult.query.get(caseresult_id_list[-1])
                    item = f"{case_result.status}_num"
                    current_num = getattr(self.suite_result, item) - 1
                    if current_num < 0:
                        current_num = 0
                    setattr(self.suite_result, item, current_num)
            self.suite_result.save()

            self.dataMgr.update_datas({'suiteresult_id': self.suite_result.id})
            self.dataMgr.suite_result_id = self.suite_result.id
            self.cases_status = self.suite_result.extra["case_status"]

            self.set_cases_list(retry_cases)
            self.parallel_run()

            db.session.refresh(self.suite_result, ['status', 'extra'])
            if self.suite_result.status == "canceled":
                pass
            else:
                self.suite_result.status = 'done'
            self.suite_result.extra["case_status"] = {
                **self.suite_result.extra["case_status"], **self.cases_status}
            self.suite_result.save()

            cov_args = self.dataMgr.data.get("code_coverage", {})
            if cov_args and cov_args.get("status", False):
                from app.libs import Goc
                goc = Goc(self.suite_result.id, cov_args,
                          self.suite_result.casesuite.name)
                goc.goc_profile()
                goc.goc_unlock()

        except Exception:
            current_app.logger.error(f"{self.prefix} {traceback.format_exc()}")
            if self.suite_result:
                self.suite_result.status = 'error'
                self.suite_result.save()
            if goc:
                goc.goc_unlock()

        finally:
            if self.result_hd:
                self.result_hd.disconnect()
            if self.suite_result:
                logger = RunLogger(self.suite_result.id,
                                   current_env.SUITE_LOG_FOLDER)
                logger.release()


class ManualExec(BaseExec):
    def __init__(self, data, case_execute_map):
        super().__init__()
        self.dataMgr = DataManagement(data)
        self.case_execute_map = case_execute_map

    def update_to_case_management(self, automation_result, status, author, case_id):
        data = {
            "automation_result": automation_result,
            "status": status,
            "type": "execute",
            "executor": author
        }
        case_instance = Case.query.get(case_id)
        execute_id = self.case_execute_map[case_instance.manual_case_id]
        url = parse.urljoin(current_app.config['CASEMANAGE_URL'],
                            current_app.config['CASE_MANAGEMENT_CALL_BACK'] + str(execute_id))

        resp = requests.put(url, headers={
            'token': current_app.config['AUTOMATION_TOKEN']}, json=data, timeout=5)
        if resp.status_code != 200:
            errmsg = f"Link auto error: {resp.status_code}"
            current_app.logger.warn(errmsg)

    def run(self, cases_list):
        current_app.logger.info(
            f'ManualExec to run cases: {cases_list}, args={self.dataMgr.datas}')
        try:
            self.set_cases_list(cases_list)
            self.parallel_run()

        except Exception:
            current_app.logger.error(
                f"ManualExec wrong: {traceback.format_exc()}")

        finally:
            if self.result_hd:
                self.result_hd.disconnect()


class ExecMgr:

    @classmethod
    def run_case_v2(cls, case_instance, data, record_id=None):
        error = ''
        worker_env = ExecUtils.get_executor_env(
            case_instance.category.lower(), case_instance.type)
        worker_type = f"{case_instance.category.lower()}_{worker_env}"

        if case_instance.category.lower() in OFFICIAL_ExecutorType and data.get(worker_type):
            from app.libs import workermgr
            ok = workermgr.has_worker_resource(
                case_instance.category.lower(), worker_env, case_instance.type, data.get(worker_type, []))

            if ok:
                current_app.logger.info(
                    f"These are workers can handle case: {case_instance.name}")
                _ = _run_case_v2.queue(case_instance.id, data, record_id,
                                       timeout=35 * 60, result_ttl=24 * 60 * 60)
            else:
                error = 'NO_MATCH_WORKER'
        else:
            _ = _run_case_v2.queue(case_instance.id, data, record_id,
                                   timeout=35 * 60, result_ttl=24 * 60 * 60)

        return error

    @classmethod
    def run_suite_v2(cls, suite_id, data, suiteresult_id=None, retry=False, retry_cases=None, record_id=None, **kwargs):
        error = ''
        suite_instance = Casesuite.query.get(suite_id)
        project_id = suite_instance.project_id
        project_instance = Project.query.get(project_id)
        executor_type = project_instance.get_executor_type()
        if not executor_type:
            executor_type = "exec"

        if retry:
            current_app.logger.info(
                f'run_suite_v2 to retry case: {suite_id}, retry_cases={retry_cases}, args={data}')
            retry_suite.queue(
                suiteresult_id, data, retry_cases, timeout=5 * 60 * 60, result_ttl=24 * 60 * 60, queue=executor_type
            )

        else:
            current_app.logger.info(
                f'run_suite_v2 to run suite: {suite_id}, args={data}')
            if data.get("common", {}).get("update", False):
                update_job = git_core.queue(
                    project_id, data['author'], timeout=60 * 60, result_ttl=24 * 60 * 60)
                _run_suite_v2.queue(
                    suite_id, data, record_id, depends_on=update_job, timeout=24.5 * 60 * 60, result_ttl=24 * 60 * 60, queue=executor_type)
            else:
                _run_suite_v2.queue(
                    suite_id, data, record_id, timeout=24.5 * 60 * 60, result_ttl=24 * 60 * 60, queue=executor_type)

        if error:
            current_app.logger.error(f"run suite error: {error}")

        return error

    @classmethod
    def run_manual_cases(cls, cases_list, data, case_execute_map):
        error = ''
        if not error:
            _run_manual_cases.queue(
                cases_list, data, case_execute_map, timeout=24 * 60 * 60, result_ttl=24 * 60 * 60)
        else:
            current_app.logger.error(f"run manual cases error: {error}")
        return error

    @classmethod
    def run_manual_plan(cls, suite_result_id, data):
        _run_manual_plan.queue(
            suite_result_id, data, timeout=24 * 60 * 60, result_ttl=24 * 60 * 60)


class PostWomen:
    def __init__(self, exec_id):
        self.exec_id = exec_id
        self.logger = RunLogger(exec_id, os.path.join(
            current_app.instance_path, current_env.POSTWOMEN_LOG))
        self.prefix = f"[{exec_id}]"

    def gen_spex_task(self, api_id, request, params):
        api = SpexApi.query.get(api_id)
        if not api:
            current_app.logger.error(f"{self.prefix}Not found api!")
            return

        task = {
            "protocol": "spex",
            "service_name": api.service.path + '.' + api.service.name,
            "cmd": api.name,
            "topic": api.topic,
            "params": params,
            "req": request,
            "timeout": 60
        }
        return task

    @staticmethod
    def gen_http_task(method, url, headers, body):
        task = {
            "protocol": "http",
            "method": method,
            "url": url,
            "headers": headers,
            "body": body,
            "timeout": 60
        }
        return task

    def run(self, task):
        try:
            task_hd = MyRedis(
                current_app.config['REDIS']['URL_FOR_POSTWOMEN_TASK'])
            task_hd.set(self.exec_id, json.dumps(task), ex=24 * 60 * 60)
            task_hd.disconnect()
            current_app.logger.info(
                f'{self.prefix}Successfully set task to redis!')

            result = {"status": "pending"}
            result_hd = MyRedis(
                current_app.config['URL_FOR_RESULT'])
            result_hd.set(self.exec_id, json.dumps(result), ex=24 * 60 * 60)
            current_app.logger.info(f'{self.prefix} pending!')

            mq_task = TaskFactory.get_postwomen_task(self.exec_id)
            mymq = init_mymq()
            ok = mymq.send('oneworker', "spex__common", json.dumps(mq_task))
            if ok:
                current_app.logger.info(
                    f"{self.prefix}send task to spex__common success!")
            else:
                current_app.logger.info(
                    f"{self.prefix}send task to spex__common failed!")
                result = {"status": "error"}
                result_hd.set(self.exec_id, json.dumps(
                    result), ex=24 * 60 * 60)
                result_hd.disconnect()

        except Exception:
            current_app.logger.error(
                f"{self.prefix} Some wrong happened: {traceback.format_exc()}")

        finally:
            if self.logger:
                self.logger.release()


@myrq.job('exec')
def _run_case_v2(case_id, data, record_id=None):
    try:
        dataMgr = DataManagement(data)
        baseExec = BaseExec(dataMgr=dataMgr, cases_list=[
            case_id], record_id=record_id)
        baseExec.parallel_run()
    except Exception:
        current_app.logger.error(
            f"Some wrong happened in rq job to run case[id:{case_id}]: {traceback.format_exc()}")


@myrq.job('exec')
def _run_suite_v2(suite_id, data, record_id=None):
    try:
        suiteExec = SuiteExec(data, suite_id, record_id=record_id)
        suiteExec.run()
    except Exception:
        current_app.logger.error(
            f"Some wrong happened in rq job to run suite[id:{suite_id}]: {traceback.format_exc()}")


@myrq.job('exec')
def retry_suite(suite_result_id, data, retry_cases):
    try:
        suiteExec = SuiteExec(data, suite_result_id=suite_result_id)
        suiteExec.retry_suite(retry_cases)
    except Exception:
        current_app.logger.error(f"Some wrong happened in rq job to "
                                 f"retry suite_result[id:{suite_result_id}]: {traceback.format_exc()}")


@myrq.job('exec')
def _run_manual_cases(cases_list, data, case_execute_map):
    try:
        manualExec = ManualExec(data, case_execute_map)
        manualExec.run(cases_list)
    except Exception:
        current_app.logger.error(f"Some wrong happened in rq job to "
                                 f"run manual cases: {traceback.format_exc()}")


@myrq.job('postwomen')
def postwomen(exec_id, p_type='spex', **kwargs):
    try:
        pw = PostWomen(exec_id)
        task = getattr(pw, f'gen_{p_type}_task')(**kwargs)
        pw.run(task)

    except Exception:
        current_app.logger.info(f"Some wrong happened in rq job to "
                                f"run postwomen: {traceback.format_exc()}")


@myrq.job('exec')
def _run_manual_plan(suite_result_id, data):
    suite_result = None
    try:
        suite_result = SuiteResult.query.get(suite_result_id)
        if suite_result:
            suiteExec = SuiteExec(
                data, suite_result.casesuite_id, record_id=None)
            suiteExec.suite_result = suite_result

            # do something before executing
            ok, log_file = suiteExec.setup()
            if not ok:
                msg = f'hello, {suiteExec.dataMgr.author} \n' \
                      f'your plan {suite_result.casesuite.name} setup error, please see log: \n' \
                      f'{log_file} for detail, thank you. 88~'
                suiteExec.send_msg(msg)
                raise Exception(f"Setup error, log in {log_file}")

            suiteExec.goc_clear()
            suite_result.status = 'running'
            suite_result.save()

        else:
            raise Exception(f"Not found suite result[id:{suite_result_id}]")

    except Exception:
        if suite_result:
            suite_result.status = 'error'
            suite_result.save()
        current_app.logger.error(
            f"Some wrong happened in rq job to run manual suite[result id:{suite_result_id}]: {traceback.format_exc()}")
