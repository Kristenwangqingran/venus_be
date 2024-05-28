# -*- coding: utf-8 -*-
# @Time    : 2023-09-19
# @Author  : GongXun


import requests
import traceback
import base64
import re
import time
import json
from flask import current_app

from app.commons.config import get_config
from app.commons import utils, myrq


current_env = get_config()

# PP


class Pipeline:

    @classmethod
    def __get_pipeline_token(cls):
        host = "https://space.shopee.io/apis/uic/v2/auth/basic_login"
        token = base64.b64encode(
            f"{current_env.SPCLI_USER}:{current_env.SPCLI_PSD}".encode('utf-8'))
        headers = {"Authorization": f"Basic {token.decode('utf-8')}"}
        resp = requests.post(host, headers=headers, timeout=5)
        return resp.json()['token']

    @classmethod
    def pipeline_callback(cls, url, resultCode, **kwargs):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {cls.__get_pipeline_token()}"
        }
        body = {
            "result": {
                "resultCode": resultCode,
                "resultMsg": "finish"
            },
            # "extra": every_to_string(**kwargs)
        }
        if kwargs:
            body["extra"] = utils.every_to_string(**kwargs)

        current_app.logger.info(f"pipeline_callback: [{url}], body: {body}")
        resp = requests.post(url, headers=headers, json=body, timeout=5)
        current_app.logger.info(f"result: {resp.json()}")

    @classmethod
    def pipeline_query(cls, callback):
        ro = re.match(
            r".*?/trigger/(?P<name>.*?)/build/(?P<buildID>\d+)/job/(?P<jobID>\d+)/plugin/(?P<pluginID>\d+)", callback)
        return cls.__pipeline_query(ro.group("name"), int(ro.group("buildID")))

    @classmethod
    def __pipeline_query(cls, pipeline_name, run_id, retry=5):
        '''{
        'pipeline_name': 'shopee-marketplace_core-promotion-qa-internal_platforms-QA_common_v1_3_deploy__79424',
        'run_id': 67803
}, response: {
        'errno': 0,
        'errmsg': 'success',
        'logid': '3226741541',
        'data': {
                'detail': [{
                        'stage_id': 229132,
                        'stage_name': '1',
                        'stage_status': 'SUCCESS',
                        'jobs': [{
                                'job_id': 232634,
                                'job_name': '1_1',
                                'description': 'Check Out Code',
                                'job_status': 'SUCCESS',
                                'job_duration': 4241,
                                'plugin_id': 1,
                                'plugin_name': 'Check Out From GitLab',
                                'binary_download_url': '',
                                'input_type': 2
                        }]
                }, {
                        'stage_id': 229133,
                        'stage_name': '2',
                        'stage_status': 'START',
                        'jobs': [{
                                'job_id': 232635,
                                'job_name': '2_1',
                                'description': 'deploy',
                                'job_status': 'RUNNING',
                                'job_duration': 40,
                                'plugin_id': 8,
                                'plugin_name': 'Third-party Tool',
                                'binary_download_url': ''
                        }]
                }],
                'pluginGlobals': [{
                        'jobName': '1_1',
                        'description': '',
                        'pluginId': 1,
                        'pluginGlobalEnvParams': [{
                                'paramKey': 'CODE_PATH',
                                'paramType': 'string',
                                'paramValue': 'gitlab@git.garena.com:shopee/szqa/automation/venus_be.git',
                                'description': ''
                        }, {
                                'paramKey': 'MAIN_REPO',
                                'paramType': 'bool',
                                'paramValue': 'true',
                                'description': ''
                        }, {
                                'paramKey': 'CODE_BRANCH',
                                'paramType': 'string',
                                'paramValue': 'master',
                                'description': ''
                        }, {
                                'paramKey': 'CODE_TYPE',
                                'paramType': 'int',
                                'paramValue': '0',
                                'description': ''
                        }, {
                                'paramKey': 'CODE_TAG',
                                'paramType': 'string',
                                'paramValue': 'v15.3.3',
                                'description': ''
                        }, {
                                'paramKey': 'CODE_COMMITID',
                                'paramType': 'string',
                                'paramValue': '',
                                'description': ''
                        }, {
                                'paramKey': 'BRANCH_FILTER',
                                'paramType': 'string',
                                'paramValue': '',
                                'description': ''
                        }, {
                                'paramKey': 'TAG_FILTER',
                                'paramType': 'string',
                                'paramValue': '',
                                'description': ''
                        }, {
                                'paramKey': 'EXACT_COMMITID',
                                'paramType': 'string',
                                'paramValue': 'e0b53b5affc1f9e3f179371fd18db647fe061191',
                                'description': ''
                        }, {
                                'paramKey': 'WORKING_PATH',
                                'paramType': 'string',
                                'paramValue': '',
                                'description': ''
                        }, {
                                'paramKey': 'INPUT_APPROVE_TYPE',
                                'paramType': 'string',
                                'paramValue': 'APPROVE_BY_ROLE',
                                'description': ''
                        }, {
                                'paramKey': 'INPUT',
                                'paramType': 'string',
                                'paramValue': '',
                                'description': ''
                        }, {
                                'paramKey': 'INPUT_TYPE_KEY',
                                'paramType': 'string',
                                'paramValue': '1',
                                'description': ''
                        }, {
                                'paramKey': 'AUTO_SKIP_FAIL',
                                'paramType': 'boolean',
                                'paramValue': 'false',
                                'description': ''
                        }]
                }],
                'globalEnvParams': [{
                        'paramKey': 'SPACE_PIPELINE_NAME',
                        'paramType': 'string',
                        'paramValue': 'shopee-venus-webserver',
                        'description': 'the pipeline name from space '
                }, {
                        'paramKey': 'DEPLOY_TIMEOUT',
                        'paramType': 'string',
                        'paramValue': '600',
                        'description': 'deploy timeout(s),  if deploy not finish in TIMEOUT(s), will fail'
                }, {
                        'paramKey': 'local_env',
                        'paramType': 'string',
                        'paramValue': 'test',
                        'description': 'env'
                }, {
                        'paramKey': 'local_cids',
                        'paramType': 'string',
                        'paramValue': '""',
                        'description': 'cids: CN,SG'
                }, {
                        'paramKey': 'local_pfb',
                        'paramType': 'string',
                        'paramValue': '""',
                        'description': 'pfb name'
                }, {
                        'paramKey': 'PIPELINE_GITTRIGGER_TITLE',
                        'paramType': 'string',
                        'paramValue': 'V15.0',
                        'description': ''
                }, {
                        'paramKey': 'PIPELINE_GITTRIGGER_DESCRIPTION',
                        'paramType': 'string',
                        'paramValue': '',
                        'description': ''
                }, {
                        'paramKey': 'PIPELINE_GITTRIGGER_ASSIGNEES',
                        'paramType': 'string',
                        'paramValue': '',
                        'description': ''
                }],
                'platformParams': {
                        'gitMasterInfo': {
                                'gitSshUrl': 'gitlab@git.garena.com:shopee/szqa/automation/venus_be.git',
                                'gitlabDomain': 'git.garena.com',
                                'gitlabEnv': 'live',
                                'projectId': 21600,
                                'commitId': 'e0b53b5affc1f9e3f179371fd18db647fe061191',
                                'codeBranch': 'v15.0',
                                'codeType': '0',
                                'pushTime': '2023-12-14T15:51:05+08:00',
                                'commitEmail': '',
                                'commitMessage': 'update\n',
                                'workspace': '',
                                'jobName': '1_1'
                        },
                        'userInfo': {
                                'userEmail': '',
                                'userToken': ''
                        },
                        'gitEventKind': 'merge_request',
                        'mergeEvent': {
                                'mergeIid': 806,
                                'targetBranch': 'kobe',
                                'fromBranch': 'v15.0'
                        },
                        'git_even': {
                                'open': True,
                                'git_title': 'V15.0',
                                'git_desc': '',
                                'git_assignees': ''
                        },
                        'pipelineType': 0
                }
        }
}'''

        def __parse_args(raw_args):
            results = {}
            ms = re.findall(r"(\w+)(?::|=)\s*([-\w/,]+)", raw_args)
            for k, v in ms:
                results[k] = v
            return results

        def __parse_platformParams(platformParams):
            args = {}
            if platformParams and isinstance(platformParams, dict):
                args["targetBranch"] = platformParams.get(
                    'gitMasterInfo', {}).get("codeBranch")
                args[args["targetBranch"]] = platformParams.get(
                    'gitMasterInfo', {}).get("commitId")

                args["fromBranch"] = platformParams.get(
                    'gitMasterInfo', {}).get("codeBranch")
                args[args["fromBranch"]] = platformParams.get(
                    'gitMasterInfo', {}).get("commitId")

                if "gitEventKind" in platformParams:
                    args["gitEventKind"] = platformParams["gitEventKind"]
                    args["targetBranch"] = platformParams.get(
                        'mergeEvent', {}).get("targetBranch")
                    args[args["targetBranch"]] = "unknow"

                    args["fromBranch"] = platformParams.get(
                        'mergeEvent', {}).get("fromBranch")
                    args[args["fromBranch"]] = "unknow"

                    git_desc = platformParams.get('git_even', platformParams.get(
                        'git_event', {})).get("git_desc", "")
                    if git_desc:
                        args.update(__parse_args(git_desc))
            return args

        def __parse_globalEnvParams(globalEnvParams):
            args = {}
            if globalEnvParams and isinstance(globalEnvParams, list):
                for param in globalEnvParams:
                    v = param['paramValue']
                    if isinstance(v, str) and v == '""':
                        v = ""
                    args[param['paramKey']] = v
                    if param['paramKey'].startswith('local_'):
                        args[param['paramKey'].replace(
                            'local_', '')] = v
            return args

        def __parse_pluginGlobals(pluginGlobals):

            def __convert_data(pluginGlobalEnvParams):
                data_dict = {}
                for item in pluginGlobalEnvParams:
                    data_dict[item['paramKey']] = item
                return data_dict

            args = {}
            if pluginGlobals and isinstance(pluginGlobals, list):
                for job_info in pluginGlobals:
                    if re.match(r'^\w+$', job_info['description']):
                        data_dict = __convert_data(
                            job_info['pluginGlobalEnvParams'])

                        if 'CODE_TYPE' in data_dict:
                            if int(data_dict['CODE_TYPE']['paramValue']) == 0:  # branch
                                args[f"{job_info['description']}__fromBranch"] = data_dict['CODE_BRANCH']['paramValue']
                                args[f"{job_info['description']}__targetBranch"] = data_dict['CODE_BRANCH']['paramValue']

                            elif int(data_dict['CODE_TYPE']['paramValue']) == 1:  # tag
                                args[f"{job_info['description']}__fromBranch"] = data_dict['CODE_TAG']['paramValue']
                                args[f"{job_info['description']}__targetBranch"] = data_dict['CODE_TAG']['paramValue']

                            else:
                                continue

                            args[f"{job_info['description']}__commit_ID"] = data_dict['EXACT_COMMITID']['paramValue']

                    else:
                        current_app.logger.info(
                            f"skip pluginGlobal: {job_info['description']}")

            return args

        result = {}
        url = "https://space.shopee.io/apis/pipeline_ci/openapi/pipeline/build/detail"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {cls.__get_pipeline_token()}"
        }
        body = {
            "pipeline_name": pipeline_name,
            "run_id": run_id
        }

        while retry:
            current_app.logger.info(
                f"pipeline_query request: [{url}], body: {body}")
            try:
                resp = requests.post(url, headers=headers,
                                     json=body, timeout=5)
                resp_data = resp.json()
                current_app.logger.info(
                    f"pipeline_query request: [{url}], body: {body}, response: {resp_data}")

                if resp_data['errno'] == 0:
                    resp_body = resp_data['data']
                    result = __parse_globalEnvParams(
                        resp_body.get("globalEnvParams", {}))
                    result.update(__parse_platformParams(
                        resp_body.get("platformParams", {})))
                    result.update(__parse_pluginGlobals(
                        resp_body.get("pluginGlobals", {})))
                    current_app.logger.info(f"pipeline_query result: {result}")
                    break
                # elif resp_data['errno'] == 50005:
                else:
                    retry -= 1
                    time.sleep((10-retry) * 10)
                    continue

            except Exception:
                current_app.logger.error(traceback.format_exc())

        return result


# SDP
class Deploy:

    @classmethod
    def __get_pipeline_token(cls):
        host = "https://space.shopee.io/v1/sessions"
        auth = (current_env.SPCLI_USER, current_env.SPCLI_PSD)
        resp = requests.post(host, json={}, auth=auth)
        return resp.json()['token']

    @classmethod
    def build(cls, name, branch, env, cids, pfb):
        url = "https://space.shopee.io/apis/pipeline/openapi/pipeline/build"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {cls.__get_pipeline_token()}"
        }
        body = {
            "pipeline_name": f"{name}-{env}",
            "parameters": {
                "FROM_BRANCH": branch,
                "ENV": env,
                "DEPLOY_CIDS": cids,
                "PFB": pfb
            }
        }
        current_app.logger.info(f"pipeline build: [{url}], body: {body}")
        r = requests.post(url, headers=headers, json=body, timeout=5)
        resp = r.json()
        current_app.logger.info(f"result: {resp}")
        if 'callback_id' not in resp.get('data', {}):
            raise Exception(
                f"call deploy api error: please check your params, branch: {branch}, env: {env}, cids: {cids}, pfb: {pfb}")
        return resp['data']['callback_id'], resp['data']['service_names']

    @classmethod
    def query(cls, callback_id, timeout=600, step_time=30):
        url = "https://space.shopee.io/apis/pipeline/openapi/pipeline/build/detail"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {cls.__get_pipeline_token()}"
        }
        body = {
            "callback_id": callback_id
        }
        current_app.logger.info(
            f"pipeline build status query: [{url}], body: {body}")

        success, _extra = False, {}
        while timeout:
            r = requests.post(url, headers=headers, json=body, timeout=5)
            resp = r.json()
            current_app.logger.info(
                f"pipeline build status query result: {resp}")
            data = resp.get('data', {})
            _extra["data"] = data
            status = data.get('status', "FAILED")
            _extra["status"] = status
            if status == "SUCCESS":
                success = True
                break

            elif status in ("FAILED", "NOT_EXECUTED", "ABORTED"):
                success = False
                break

            else:
                current_app.logger.info(
                    f"callback_id: {callback_id}, time left: {timeout}")
                time.sleep(step_time)

            timeout -= step_time

        return success, _extra

    @classmethod
    def history(cls, name, env, build_status="SUCCESS"):
        url = "https://space.shopee.io/apis/pipeline/openapi/pipeline/history/list"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {cls.__get_pipeline_token()}"
        }
        body = {
            "pipeline_name": f"{name}-{env}",
            "build_status": build_status,
            "page": 1,
            "page_size": 1
        }
        current_app.logger.info(
            f"pipeline history: [{url}], body: {body}")

        r = requests.post(url, headers=headers, json=body, timeout=5)
        resp = r.json()
        current_app.logger.info(
            f"pipeline history result: {resp}")
        data = resp.get('data', {}).get('list', [])
        commit_id = None
        pfb = ""
        if data:
            extra = json.loads(data[0]['extra'])
            commit_id = extra['gitCommitID']

            parameter = json.loads(data[0]['parameter'])
            pfb = parameter['PFB']

        return commit_id, pfb


@myrq.job('callback')
def common_pipeline_callback(callback, code, **kwargs):
    time.sleep(1)
    Pipeline.pipeline_callback(
        callback, code, **kwargs)
