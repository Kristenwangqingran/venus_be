# -*- coding: utf-8 -*-
# @Time    : 2022/2/28
# @Author  : Jiaxin Chen


import os
import json
import time
import shutil
import traceback
from flask import current_app
from app.commons import myrq, init_mymq, MyRedis
from app.commons.hc_gen_case import generate_cases as gc
from app.commons.hc_gen_case import serialize_bytes_base64
from app.models import HcPlan, HcCase, HcCaseResult, HcPlanResult, SpexApi, HttpPlan, HttpApi, http_env_detail_schema
from sqlalchemy.orm.attributes import flag_modified
from app.commons.config import get_config

current_env = get_config()
NOT_DONE_STATUS = ['pending', 'running']


class PlanResultNotFoundError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class HealthCheck:
    def __init__(self, plan_id, data, token, api_type, routing_key):
        self.plan_id = plan_id
        self.data = data
        self.token = token
        self.api_type = api_type
        self.routing_key = routing_key

        if api_type == "spex":
            self.plan = HcPlan.query.get(plan_id)
            self.env = {"name": data['env']}
        else:
            self.plan = HttpPlan.query.get(plan_id)
            self.env = http_env_detail_schema.dump(data['env'])
        self.plan_result = None
        self.case_results = {}

        self.total_case_num = 0
        self.path = ""
        self.prefix = ""
        self.result_hd = MyRedis(current_app.config['REDIS']['URL_FOR_RESULT'])

    def _init_path(self, ):
        self.path = os.path.join(current_app.instance_path, 'logs',
                                 current_app.config['HC_PATH'], str(self.plan_result.id))
        if not os.path.exists(self.path):
            os.makedirs(self.path, exist_ok=True)

    def _init_logger(self, ):
        from app.commons import RunLogger
        logger = RunLogger(f"HC{str(self.plan_result.id)}",
                           current_env.SUITE_LOG_FOLDER)
        log_path = logger.log_dir
        self.prefix = f"[HC{str(self.plan_result.id)}]"
        current_app.logger.info(f"The log of the execution(plan_result_id: {str(self.plan_result.id)})"
                                f"will be logged in the {log_path}")

    def generate_result(self, ):
        self.plan_result = HcPlanResult(**{
            "runner": self.data["runner"],
            "status": "pending",
            "html": "",
            "extra": {
                "casePath": "",
                "err_msg": "",
                "env": self.data['env'],
                "region": self.data['region'],
                "routing_cid": self.data['routing_cid'],
                "pfb": self.data['pfb'],
            },
            "api_type": self.api_type
        })
        if self.api_type == "spex":
            self.plan_result.plan_id = self.plan_id
        else:
            self.plan_result.http_plan_id = self.plan_id
        self.plan_result.save()
        self._init_path()
        self._init_logger()
        current_app.logger.info(
            f'Create suite result success! suite_result id: {self.plan_result.id}')

    def generate_task(self, exec_json_path, total):
        task = {
            "action": "health_check",
            "env": self.data['env'],
            "region": self.data['region'],
            "routing_cid": self.data['routing_cid'],
            "pfb": self.data['pfb'],
            "suiteresult_id": str(self.plan_result.id),
            "caseresult_id": str(self.plan_result.id),
            "plan_file_path": exec_json_path,
            "total_case_num": total,
            "report_path": self.path,
            "timeout": self.data.get("timeout", 60 * total),
            "token": self.token,
            "type": self.api_type
        }
        self.plan_result.total = self.total_case_num
        self.plan_result.save()
        current_app.logger.info(f"{self.prefix} {self.plan.name} task: {task}")
        return task

    def send_task(self, task):
        result = {"status": "pending"}
        self.result_hd.set(f'plan_{task["caseresult_id"]}',
                           json.dumps(result), ex=24 * 60 * 60)

        mymq = init_mymq()
        ok = mymq.send('oneworker', self.routing_key, json.dumps(task))
        if ok:
            current_app.logger.info(
                f"{self.prefix} {self.plan.name} send task to {self.routing_key} success!")
        else:
            current_app.logger.info(
                f"{self.prefix} {self.plan.name} send task to {self.routing_key} failed!")
            self.plan_result.status = 'error'
            self.plan_result.save()

    def wait_plan_result(self, timeout=12 * 60 * 60):
        last_status = None
        while timeout:
            try:
                result = json.loads(
                    self.result_hd.get(f'plan_{str(self.plan_result.id)}'))
                current_status = result.get('status', '')
                if current_status != last_status:
                    self.plan_result.put_check(result)
                    last_status = result.get('status', '')

                if current_status not in NOT_DONE_STATUS:
                    break

            except Exception:
                current_app.logger.error(f"{self.prefix} Some wrong happened while waiting result:"
                                         f" {traceback.format_exc()}")

            finally:
                time.sleep(1)
                timeout -= 1

    def wait_case_results(self, timeout=12 * 60 * 60):
        current_app.logger.info(f"{self.prefix} Start to wait case exec ... ")
        while timeout:
            try:
                case_result_not_done = [case_result_id for case_result_id, info in self.case_results.items()
                                        if info['status'] in NOT_DONE_STATUS]
                if not case_result_not_done:
                    break

                for case_result_id in case_result_not_done:
                    result_byte = self.result_hd.get(case_result_id)
                    result = json.loads(result_byte) if result_byte else {}
                    if result['status'] not in NOT_DONE_STATUS:
                        case_result = HcCaseResult.query.get(case_result_id)
                        case_result.put_save(result)
                        self.case_results[case_result_id] = result

            except Exception:
                current_app.logger.error(f"{self.prefix} Some wrong happened while waiting case results:"
                                         f" {traceback.format_exc()}")

            finally:
                time.sleep(1)
                timeout -= 1

    def generate_exec_json(self, ):
        # Subclasses inherit and rewrite as needed
        return ""

    def generate_case_and_result(self, case_dict):
        case = HcCase(**case_dict)
        case.save()
        case_result = HcCaseResult(**{
            "status": "pending",
            "runner": self.data["runner"],
            "case_type": case.case_type,
            "response": {},
            "error_code": {},
            "plan_result_id": self.plan_result.id,
            "case_id": case.id
        })
        case_result.save()
        record = {
            "status": "pending"
        }
        self.result_hd.set(case_result.id, json.dumps(record), ex=24 * 60 * 60)
        self.case_results[case_result.id] = record
        return case.id, case_result.id

    def prepare_exec(self, exec_json):
        path = os.path.join(self.path, 'plan.json')
        with open(path, 'w') as f:
            json.dump(exec_json, f, default=serialize_bytes_base64)

        current_app.logger.info(
            f"{self.prefix} {self.plan.name} exec json has been generated in {path}")
        self.plan_result.extra["casePath"] = path
        flag_modified(self.plan_result, "extra")
        self.plan_result.save()
        return path

    @staticmethod
    def parse_case(case, api):
        pass

    def prepare_for_rerun(self, last_plan_result_id):
        last_plan_result = HcPlanResult.query.get(last_plan_result_id)
        if not last_plan_result or not last_plan_result.extra["casePath"]:
            raise PlanResultNotFoundError(last_plan_result_id)

        shutil.copy(last_plan_result.extra["casePath"], self.path)
        current_app.logger.info(
            f"{self.prefix} {self.plan.name} exec json has been copy to {self.path}")
        exec_json = os.path.join(self.path, 'plan.json')
        self.plan_result.extra["casePath"] = exec_json
        flag_modified(self.plan_result, "extra")
        self.plan_result.save()
        self.total_case_num = last_plan_result.total
        return exec_json

    def run(self, ):
        current_app.logger.info(
            f'Start to run {self.api_type} health_check, plan id: {self.plan_id}, data: {self.data}')
        self.generate_result()
        exec_json_path = self.generate_exec_json()
        task = self.generate_task(exec_json_path, self.total_case_num)
        self.send_task(task)
        self.plan_result.put_check({'status': 'running'})
        self.wait_case_results()
        self.wait_plan_result()

    def rerun(self, plan_result_id):
        current_app.logger.info(
            f'Start to rerun old {plan_result_id}.New plan id: {self.plan_id}, data: {self.data}')
        self.generate_result()
        exec_json = self.prepare_for_rerun(plan_result_id)
        task = self.generate_task(exec_json, self.total_case_num)
        self.send_task(task)
        self.wait_case_results()
        self.wait_plan_result()


class SpexHealthCheck(HealthCheck):
    def __init__(self, plan_id, data, token):
        super().__init__(plan_id, data, token, 'spex', 'spex__common')

    @staticmethod
    def parse_case(case, api):
        fields = {}
        for field_name, field_cases in case["cases"].items():
            fields[field_name] = {
                "detail": field_cases
            }
            keys = field_name.split('.')
            if len(keys) == 1:
                if "[" in field_name:
                    list_name = field_name.split('[')[0]
                    fields[field_name]["type"] = api.request.get(
                        list_name, ["unknow"])[0]
                else:
                    field_type = api.request.get(
                        field_name, "")
                    if isinstance(field_type, str):
                        fields[field_name]["type"] = field_type
                    elif isinstance(field_type, dict):
                        fields[field_name]["type"] = "object"
                    elif isinstance(field_type, list):
                        fields[field_name]["type"] = "list"
            else:
                tmp = api.request
                for key in keys:
                    tmp = tmp.get(key, {})
                fields[field_name]["type"] = tmp if isinstance(
                    tmp, str) else "object"
        return fields

    def generate_cases(self, ):
        cases = {}
        for api in self.plan.service.apis:
            cmd = self.plan.service.path + '.' + self.plan.service.name + '.' + api.name
            if not api.deleted and api.topic == self.plan.topic and cmd in self.plan.command:
                current_app.logger.info(
                    f"{self.prefix} {api.name} need to test")
                flag = False
                for template in api.templates:
                    if not template.deleted and template.is_default:
                        params = self.plan.params if self.plan.params else {}
                        params.update(
                            template.params if template.params else {})
                        current_app.logger.info(f"{self.prefix} {api.name} default template id: {template.id},"
                                                f" name: {template.name}\n"
                                                f"api.request: {api.request} \n"
                                                f"api.response: {api.response} \n"
                                                f"template.fields: {template.fields} \n"
                                                f"template.params: {template.params} \n"
                                                f"plan.params: {self.plan.params} \n"
                                                f"exec use params: {params}")
                        case = gc(api.request, api.response, template.fields)
                        fields = self.parse_case(case, api)
                        for field_name, category_info in fields.items():
                            for i, single_case in enumerate(category_info.get("detail", [])):
                                case_id, case_result_id = self.generate_case_and_result({
                                    "field_name": str(field_name),
                                    "name": str(single_case.get("name", "")),
                                    "request": json.dumps(
                                        single_case.get("request", {}), default=serialize_bytes_base64),
                                    "expect_response": json.dumps(
                                        single_case.get("response", {}), default=serialize_bytes_base64),
                                    "api_id": api.id,
                                    "expect_errcode": single_case.get("error_code", {}),
                                    "case_type": single_case.get("type", ""),
                                    "field_type": str(category_info.get("type", "")),
                                    "api_type": str(self.api_type),
                                    "template_id": template.id
                                })
                                fields[field_name]["detail"][i]["case_result_id"] = case_result_id

                        cases[api.name] = {
                            "req_name": api.req_name,
                            "resp_name": api.resp_name,
                            "fields": fields,
                            "params": params
                        }
                        self.total_case_num += case["cases_num"]
                        current_app.logger.info(
                            f"{self.prefix} {api.name} generate {case['cases_num']} cases.")
                        flag = True
                        break
                if not flag:
                    current_app.logger.error(
                        f"{self.prefix} {api.name} not found default template!")
        current_app.logger.info(
            f"{self.prefix} {self.plan.name} has a total of {self.total_case_num} test cases")
        return cases

    def generate_exec_json(self, ):
        cases = self.generate_cases()
        exec_json = {
            "plan_name": self.plan.name,
            "remote_url": current_app.config['WEB_HOST'],
            "tomcat_host": current_app.config["TOMCAT_HOST"],
            "runner": self.data["runner"],
            "service_path": self.plan.service.path,
            "service_name": self.plan.service.name,
            "server_name": self.plan.server_name,
            "config_key": self.plan.config_key,
            "topic": self.plan.topic,
            "report_path": self.path,
            "cases": cases
        }
        exec_json_path = self.prepare_exec(exec_json)
        return exec_json_path


class HttpHealthCheck(HealthCheck):
    def __init__(self, plan_id, data, token):
        super().__init__(plan_id, data, token, 'http', 'spex__common')

    @staticmethod
    def parse_case(case, api):
        fields = {}
        for field_name, field_cases in case["cases"].items():
            fields[field_name] = {
                "detail": field_cases
            }
            keys = field_name.split('.')
            if len(keys) == 1:
                if "[" in field_name:
                    list_name = field_name.split('[')[0]
                    fields[field_name]["type"] = api.body.get(
                        list_name, ["unknow"])[0]
                else:
                    field_type = api.body.get(
                        field_name, "")
                    if isinstance(field_type, str):
                        fields[field_name]["type"] = field_type
                    elif isinstance(field_type, dict):
                        fields[field_name]["type"] = "object"
                    elif isinstance(field_type, list):
                        fields[field_name]["type"] = "list"
            else:
                tmp = api.body
                for key in keys:
                    tmp = tmp.get(key, {})
                fields[field_name]["type"] = tmp if isinstance(
                    tmp, str) else "object"
        return fields

    def generate_cases(self, ):
        cases = {}
        for api_id in self.plan.apis:
            api = HttpApi.query.get(api_id)
            flag = False
            for template in api.templates:
                if not template.deleted and template.is_default:
                    case = gc(api.body, api.response, template.fields)
                    fields = self.parse_case(case, api)

                    for field_name, category_info in fields.items():
                        for i, single_case in enumerate(category_info.get("detail", [])):
                            case_id, case_result_id = self.generate_case_and_result({
                                "field_name": str(field_name),
                                "name": str(single_case.get("name", "")),
                                "request": json.dumps(single_case.get("request", {}), default=serialize_bytes_base64),
                                "expect_response": json.dumps(
                                    single_case.get("response", {}), default=serialize_bytes_base64),
                                "api_id": api.id,
                                "expect_errcode": single_case.get("error_code", {}),
                                "case_type": single_case.get("type", ""),
                                "field_type": str(category_info.get("type", "")),
                                "api_type": str(self.api_type),
                                "template_id": template.id
                            })
                            fields[field_name]["detail"][i]["case_result_id"] = case_result_id

                    url, headers = self.plan.generate_url_and_header(
                        api.path, api.params, api.headers)
                    cases[api.name] = {
                        "url": url,
                        "headers": headers,
                        "fields": fields,
                        "method": api.method,
                        "queries": api.queries
                    }
                    self.total_case_num += case["cases_num"]
                    current_app.logger.info(
                        f"{self.prefix} {api.name} generate {case['cases_num']} cases.")
                    flag = True
                    break
            if not flag:
                current_app.logger.error(
                    f"{self.prefix} {api.name} not found default template!")
        current_app.logger.info(
            f"{self.prefix} {self.plan.name} has a total of {self.total_case_num} test cases")
        return cases

    def generate_exec_json(self, ):
        cases = self.generate_cases()
        exec_json = {
            "plan_name": self.plan.name,
            "remote_url": current_app.config['WEB_HOST'],
            "tomcat_host": current_app.config["TOMCAT_HOST"],
            "runner": self.data["runner"],
            "report_path": self.path,
            "cases": cases
        }
        exec_json_path = self.prepare_exec(exec_json)
        return exec_json_path


@myrq.job('health_check')
def health_check(plan_id, data, token, api_type="spex"):
    hc = None
    try:
        if api_type == "spex":
            hc = SpexHealthCheck(plan_id, data, token)
        else:
            hc = HttpHealthCheck(plan_id, data, token)

        hc.run()

    except Exception as err:
        prefix = hc.prefix if hc else ''
        if hc and hc.plan_result:
            hc.plan_result.status = 'error'
            hc.plan_result.extra["err_msg"] = err
            hc.plan_result.save()
        current_app.logger.error(
            f"{prefix} Something wrong happened while doing health check: {traceback.format_exc()}")


@myrq.job('health_check')
def health_check_rerun(plan_id, data, plan_result_id, token, api_type="spex"):
    hc = None
    try:
        last_plan_result = HcPlanResult.query.get(plan_result_id)
        data["env"] = last_plan_result.extra['env']
        data["region"] = last_plan_result.extra['region']
        data["routing_cid"] = last_plan_result.extra['routing_cid']
        data["pfb"] = last_plan_result.extra['pfb']

        if api_type == "spex":
            hc = SpexHealthCheck(plan_id, data, token)
        else:
            hc = HttpHealthCheck(plan_id, data, token)

        hc.rerun(plan_result_id)

    except Exception as err:
        prefix = hc.prefix if hc else ''
        if hc and hc.plan_result:
            hc.plan_result.status = 'error'
            hc.plan_result.extra["err_msg"] = err
            hc.plan_result.save()
        current_app.logger.error(
            f"{prefix} Something wrong happened while rerun: {traceback.format_exc()}")


@myrq.job('health_check')
def spex_auto_check(api_id, data, token):
    hc = None
    try:
        exec_data = {
            "runner": data.get("author", "no-one"),
            "env": data.get('env', 'test'),
            "region": data.pop('region', ""),
            "routing_cid": data.pop('routing_cid', ""),
            "pfb": data.pop('pfb', "")
        }
        current_plan = None
        api = SpexApi.query.get(api_id)
        for plan in api.service.plans:
            if plan.deleted is False and plan.name == data.get('name', None):
                current_app.logger.info(f"Auto check plan exists")
                current_plan = plan
                break
        if not current_plan:
            current_app.logger.info(
                f"Auto check plan not exists, need to create")
            current_plan = HcPlan(**data)
            current_plan.save()

        hc = SpexHealthCheck(current_plan.id, exec_data, token)
        hc.run()

    except Exception as err:
        prefix = hc.prefix if hc else ''
        if hc and hc.plan_result:
            hc.plan_result.status = 'error'
            hc.plan_result.extra["err_msg"] = err
            hc.plan_result.save()
        current_app.logger.error(
            f"{prefix} Something wrong happened while doing auto check: {traceback.format_exc()}")


@myrq.job('health_check')
def http_auto_check(api_id, data, token):
    hc = None
    try:
        exec_data = {
            "runner": data.get("author", "no-one")
        }
        current_plan = None
        api = HttpApi.query.get(api_id)
        for plan in api.http_project.plans:
            if plan.deleted is False and plan.name == data.get('name', None):
                current_app.logger.info(f"Auto check plan exists")
                current_plan = plan
                break
        if not current_plan:
            current_app.logger.info(
                f"Auto check plan not exists, need to create")
            current_plan = HttpPlan(**data)
            current_plan.save()

        hc = HttpHealthCheck(current_plan.id, exec_data, token)
        hc.run()

    except Exception as err:
        prefix = hc.prefix if hc else ''
        if hc and hc.plan_result:
            hc.plan_result.status = 'error'
            hc.plan_result.extra["err_msg"] = err
            hc.plan_result.save()
        current_app.logger.error(
            f"{prefix} Something wrong happened while doing auto check: {traceback.format_exc()}")


@myrq.job('health_check')
def spex_batch_auto_check(api_id_list, data, token):
    hc = None
    try:
        exec_data = {
            "runner": data.get("author", "no-one"),
            "env": data.get('env', 'test'),
            "region": data.pop('region', ""),
            "routing_cid": data.pop('routing_cid', ""),
            "pfb": data.pop('pfb', ""),
        }

        if len(api_id_list) == 0:
            # Empty run all
            apis = SpexApi.query.filter(
                SpexApi.service_id == data['service_id'],
                SpexApi.topic == data["topic"],
                SpexApi.deleted == False
            ).all()
            api_id_list = [api.id for api in apis]

        for api_id in api_id_list:
            api = SpexApi.query.get(api_id)
            if not api:
                current_app.logger.error(
                    f"Batch auto-check not found api: {api_id}")
                continue

            if not api.templates:
                current_app.logger.error(
                    f"Batch auto-check api: {api_id} not found useful template!")
                continue

            data['command'].append(
                f"{api.service.path}.{api.service.name}.{api.name}")

        new_plan = HcPlan(**data)
        new_plan.save()

        hc = SpexHealthCheck(new_plan.id, exec_data, token)
        hc.run()

    except Exception as err:
        prefix = hc.prefix if hc else ''
        if hc and hc.plan_result:
            hc.plan_result.status = 'error'
            hc.plan_result.extra["err_msg"] = err
            hc.plan_result.save()
        current_app.logger.error(
            f"{prefix} Something wrong happened while doing batch auto check: {traceback.format_exc()}")


@myrq.job('health_check')
def http_batch_auto_check(data, token):
    hc = None
    try:
        exec_data = {
            "runner": data.get("author", "no-one")
        }

        new_plan = HttpPlan(**data)
        new_plan.save()

        hc = HttpHealthCheck(new_plan.id, exec_data, token)
        hc.run()

    except Exception as err:
        prefix = hc.prefix if hc else ''
        if hc and hc.plan_result:
            hc.plan_result.status = 'error'
            hc.plan_result.extra["err_msg"] = err
            hc.plan_result.save()
        current_app.logger.error(
            f"{prefix} Something wrong happened while doing batch auto check: {traceback.format_exc()}")
