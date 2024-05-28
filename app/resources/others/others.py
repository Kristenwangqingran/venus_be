# -*- coding: utf-8 -*-
# @Time    : 2020/09/10
# @Author  : GongXun

import traceback
import requests
import time
from flask import request, current_app
from app.commons import myrq, ma, resp_return
from app.resources import BaseResource, OpenAPIRequestArgs
from app.models import REGIONs, PLATFORMs, APPTYPEs
from app.libs import SCPMgr, TCMMgr, parser, Pipeline, Deploy, common_pipeline_callback
from app.commons.config import get_config
# import szqa_resource

current_conf = get_config()


class ValidatesView(BaseResource):

    def get(self):

        methods = []
        return resp_return('QUERY_SUCCESS', methods, len(methods))


class PlatformsView(BaseResource):

    def get(self):
        try:
            return resp_return('QUERY_SUCCESS', PLATFORMs, len(PLATFORMs))
        except Exception as err:
            return resp_return('COMMON_ERROR', new_msg=str(err))


class RegionsView(BaseResource):

    def get(self):
        try:
            return resp_return('QUERY_SUCCESS', REGIONs, len(REGIONs))
        except Exception as err:
            return resp_return('COMMON_ERROR', new_msg=str(err))


class APPtypesView(BaseResource):

    def get(self):
        try:
            return resp_return('QUERY_SUCCESS', APPTYPEs, len(APPTYPEs))
        except Exception as err:
            return resp_return('COMMON_ERROR', new_msg=str(err))


class APPInfosView(BaseResource):

    def get(self):
        try:
            data = {
                "platform": PLATFORMs,
                "apptype": APPTYPEs,
                "region": REGIONs,
            }
            return resp_return('QUERY_SUCCESS', data)
        except Exception as err:
            return resp_return('COMMON_ERROR', new_msg=str(err))


class APPVersionRequestArgs(ma.Schema):
    platform = ma.String(required=True)
    apptype = ma.String(required=True)
    region = ma.String(required=True)


class APPVersionsView(BaseResource):

    def get(self):
        try:
            query_args = APPVersionRequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', f'{str(err.args)}')

        try:
            filters = {
                "platform": query_args.get('platform'),
                "app_name": query_args.get('apptype'),
                "region": query_args.get('region'),
            }
            versions = []
            try:
                pass
                # infos = szqa_resource.get_app_version_list(**filters)
                # if infos:
                #     for item in infos:
                #         versions.append(item['app_version'])

            except Exception as err:
                current_app.logger.warn(
                    f"get_app_version_list failed: {str(err)}")

            return resp_return('QUERY_SUCCESS', versions[:20])

        except Exception as err:
            return resp_return('COMMON_ERROR', new_msg=str(err))


class SCPView(BaseResource):

    @classmethod
    def post_check(self, value):
        normal = {
            # "project": "",
            # "full_project": "",
            # "project_id": 0,
            "branch": ""
        }
        errors = []

        if value.get("project") or value.get("full_project") or value.get("project_id"):
            pass
        else:
            errors.append(
                f"project or project_id can't be all empty!")

        for k in normal.keys():
            if k in value:
                pass
            else:
                errors.append(f"{k} missing")
        return errors

    def post(self):
        try:
            request_body = request.get_json()
            request_args = OpenAPIRequestArgs().dump(request.args)
            callback = request.headers.get("Ci-Flow-Callback", "")
            current_app.logger.info(
                f"get scp data query from webhook, callback is: {callback}")
            if request_args.get("skip", False) is True:
                common_pipeline_callback.queue(
                    callback, 1, message="action skipped")
                return resp_return('SKIP')

            SCP_pipeline_callback.queue(
                request_body, callback, timeout=180, result_ttl=24 * 60 * 60)
            return resp_return('COMMON_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class TCMView(BaseResource):

    @classmethod
    def post_check(self, value):
        normal = {
            # "plan_id": 0,
            # "plan_name": "",
            # "project_id": 0,
            "progress": 0,
            "pass_rate": 0,
            # "ctime_start": 0,
            # "ctime_end": 1700448686
        }
        errors = []

        if value.get("plan_id") or (value.get("plan_name") and value.get("project_id")):
            pass
        else:
            errors.append(
                f"plan_id or plan_name and project_id can't be all empty!")

        for k in normal.keys():
            if k in value:
                pass
            else:
                errors.append(f"{k} missing")
        return errors

    def post(self):
        try:
            request_body = request.get_json()
            request_args = OpenAPIRequestArgs().dump(request.args)
            callback = request.headers.get("Ci-Flow-Callback", "")
            current_app.logger.info(
                f"get tcm data query from webhook, callback is: {callback}")
            if request_args.get("skip", False) is True:
                common_pipeline_callback.queue(
                    callback, 1, message="action skipped")
                return resp_return('SKIP')

            TCM_pipeline_callback.queue(
                request_body, callback, timeout=180, result_ttl=24 * 60 * 60)
            return resp_return('COMMON_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class JiraView(BaseResource):

    @classmethod
    def post_check(self, value):
        normal = {
            "method": "",
            "tasks": "id1,id2",
            # "target_status": ""
        }
        errors = []

        for k in normal.keys():
            if k in value:
                pass
            else:
                errors.append(f"{k} missing")
        return errors

    def post(self):
        try:
            request_body = request.get_json()
            request_args = OpenAPIRequestArgs().dump(request.args)
            callback = request.headers.get("Ci-Flow-Callback", "")
            current_app.logger.info(
                f"get jira action from webhook, callback is: {callback}")
            if request_args.get("skip", False) is True:
                common_pipeline_callback.queue(
                    callback, 1, message="action skipped")
                return resp_return('SKIP')

            Jira_pipeline_callback.queue(
                request_body, callback, timeout=60, result_ttl=24 * 60 * 60)
            return resp_return('COMMON_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class DeployView(BaseResource):

    @classmethod
    def post_check(self, value):
        normal = {
            "name": "",
            "branch": "",
            "env": "",
            "cids": "",
            "pfb": "",
            # "timeout": 600
        }
        errors = []

        if value.get("name") and value.get("env"):
            if value["env"].lower() in ("live", ):
                errors.append(
                    "no no no, live is forbidden!")
        else:
            errors.append(
                "name and env can't be empty!")

        for k in normal.keys():
            if k in value:
                pass
            else:
                errors.append(f"{k} missing")
        return errors

    def post(self):
        try:
            request_body = request.get_json()
            request_args = OpenAPIRequestArgs().dump(request.args)
            callback = request.headers.get("Ci-Flow-Callback", "")
            current_app.logger.info(
                f"get deploy from webhook, callback is: {callback}")
            if request_args.get("skip", False) is True:
                common_pipeline_callback.queue(
                    callback, 1, message="action skipped")
                return resp_return('SKIP')

            deploy_callback.queue(
                request_body, callback, request_args['lazy'], timeout=12 * 60 * 60, result_ttl=24 * 60 * 60)
            return resp_return('COMMON_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


@myrq.job('callback')
def SCP_pipeline_callback(request_body, callback):
    current_app.logger.info("wait 30s to do the scp checking...")
    time.sleep(30)
    runtime_args = Pipeline.pipeline_query(callback)
    if not runtime_args:
        return Pipeline.pipeline_callback(callback, 2, errors="pipeline query field")

    # args replace
    request_body = parser(request_body, runtime_args)

    errors = SCPView.post_check(request_body)
    if errors:
        return Pipeline.pipeline_callback(callback, 2, errors=errors)

    if request_body.get("project_id"):
        Total, ST_Total, UT_Total, CInc, ST_CInc, UT_CInc = SCPMgr.get_coverage_by_projectID(
            int(request_body["project_id"]), request_body["branch"])
    elif request_body.get("full_project"):
        Total, ST_Total, UT_Total, CInc, ST_CInc, UT_CInc = SCPMgr.get_coverage_by_fullProjectName(
            request_body["full_project"], request_body["branch"])
    else:
        Total, ST_Total, UT_Total, CInc, ST_CInc, UT_CInc = SCPMgr.get_coverage_by_projectName(
            request_body["project"], request_body["branch"])

    real_value_map = {
        "Total": Total,
        "ST_Total": ST_Total,
        "UT_Total": UT_Total,
        "CInc": CInc,
        "ST_CInc": ST_CInc,
        "UT_CInc": UT_CInc
    }
    success = True
    errors = []
    for k, v in request_body.items():
        if k in real_value_map:
            if 'unknow' != real_value_map[k] and float(real_value_map[k].replace("%", "")) >= float(v):
                pass
            else:
                errors.append(f"{k}: {real_value_map[k]} less than {v}")
                success = False

    extra = {
        "SCP-link": SCPMgr.get_mergeddata_link(request_body.get("project"), request_body.get("full_project"), request_body["branch"]),
    }
    if errors:
        extra["errors"] = errors
    extra.update(real_value_map)
    return Pipeline.pipeline_callback(callback, 1 if success else 2, **extra)


@myrq.job('callback')
def TCM_pipeline_callback(request_body, callback):
    runtime_args = Pipeline.pipeline_query(callback)
    if not runtime_args:
        return Pipeline.pipeline_callback(callback, 2, errors="pipeline query field")

    # args replace
    request_body = parser(request_body, runtime_args)

    errors = TCMView.post_check(request_body)
    if errors:
        return Pipeline.pipeline_callback(callback, 2, errors=errors)

    TCM_infos = []
    if request_body.get("plan_id"):
        Progress, PassRate, _extra = TCMMgr.get_rate_by_planID(
            int(request_body["plan_id"]))
        TCM_infos.append((Progress, PassRate, _extra))
    else:
        TCM_infos = TCMMgr.get_rate_by_planName(request_body["plan_name"], int(
            request_body["project_id"]), request_body.get("ctime_start", "2019-11-11 11:11:11"), request_body.get("ctime_end", "2222-11-11 11:11:11"))

    success = True
    errors = []
    extra = {
        "TCM-link": TCMMgr.get_plan_link(0),
    }
    current_app.logger.info(f"TCM_infos: {TCM_infos}")
    for Progress, PassRate, _extra in TCM_infos:
        if isinstance(Progress, (int, float)) and Progress < float(request_body["progress"]):
            success = False
            errors.append(
                f"plan: {_extra['name']}, progress: {Progress} less than {request_body['progress']}")

        if isinstance(PassRate, (int, float)) and PassRate < float(request_body["pass_rate"]):
            success = False
            errors.append(
                f"plan: {_extra['name']}, pass_rate: {PassRate} less than {request_body['pass_rate']}")

        if isinstance(PassRate, (int, float)) and isinstance(Progress, (int, float)):
            _extra.update({
                "progress": f"{round(Progress, 2)}%({_extra['failCount']+_extra['ignoreCount']+_extra['successCount']}/{_extra['totalCount']})",
                "pass_rate": f"{round(PassRate, 2)}%({_extra['successCount']}/{_extra['successCount']+_extra['failCount']})"
            })
            extra[f"{_extra['name']}"] = _extra
        else:
            success = False
            errors.append("no plan found")

    if errors:
        extra["errors"] = errors
    return Pipeline.pipeline_callback(callback, 1 if success else 2, **extra)


@myrq.job('callback')
def deploy_callback(request_body, callback, lazy):
    runtime_args = Pipeline.pipeline_query(callback)
    if not runtime_args:
        return Pipeline.pipeline_callback(callback, 2, errors="pipeline query field")

    # args replace
    request_body = parser(request_body, runtime_args)

    errors = DeployView.post_check(request_body)
    if errors:
        return Pipeline.pipeline_callback(callback, 2, errors=errors)

    _extra = {}
    if lazy is True:
        commit_id, pfb = Deploy.history(
            request_body["name"], request_body["env"])

        if commit_id:
            current_app.logger.info(
                f"last build info for {request_body['name']}-{request_body['env']} is: {commit_id}, {pfb}")
            if commit_id == runtime_args[request_body["branch"]] and pfb == request_body["pfb"]:
                _extra['message'] = "last deploy is same with this, so skip deployment"
                _extra['commit_id'] = commit_id
                _extra['pfb'] = pfb
                return Pipeline.pipeline_callback(callback, 1, **_extra)

    try:
        callback_id, service_names = Deploy.build(request_body["name"], request_body["branch"],
                                                  request_body["env"], request_body["cids"], request_body["pfb"])
        success, _extra = Deploy.query(callback_id, int(
            request_body.get("timeout", 600)))
    except Exception as err:
        return Pipeline.pipeline_callback(callback, 2, errors=str(err))

    extra = {
        "callback_id": callback_id,
        "space_deployment_link": f"https://space.shopee.io/console/cmdb/deployment/detail/{service_names[0]}"
    }
    return Pipeline.pipeline_callback(callback, 1 if success else 2, **extra, **_extra)


@myrq.job('callback')
def Jira_pipeline_callback(request_body, callback):
    runtime_args = Pipeline.pipeline_query(callback)
    if not runtime_args:
        return Pipeline.pipeline_callback(callback, 2, errors="pipeline query field")

    # args replace
    request_body = parser(request_body, runtime_args)

    errors = JiraView.post_check(request_body)
    if errors:
        return Pipeline.pipeline_callback(callback, 2, errors=errors)

    # call pbot
    url = "http://bot.qa.sz.shopee.io:10001/openapi/jira"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    if request_body['method'] in ("add_label",):
        if not request_body.get('label_name'):
            return Pipeline.pipeline_callback(callback, 2, errors=f"jira query code error: label_name missing")

        body = {
            "method": "add_label",
            "tasks": [{"id": task_id.strip(), "body": {"lable": request_body['label_name']}} for task_id in request_body['tasks'].split(',') if task_id.strip()]
        }
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        return Pipeline.pipeline_callback(callback, 1)

    else:
        body = {
            "method": "query",
            "tasks": [{"id": task_id.strip()} for task_id in request_body['tasks'].split(',') if task_id.strip()]
        }
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        if resp.status_code == 200:
            resp_body = resp.json()
            if resp_body["code"] != 0:
                return Pipeline.pipeline_callback(callback, 2, errors=f"jira query code error: {resp_body['message']}")
            else:
                errors = []
                extra = {
                }

                if request_body['method'] in ("query",):
                    for record in resp_body["data"]:
                        extra[record["id"]] = {
                            "summary": record["summary"],
                            "assignee": record["assignee"],
                            "creator": record["creator"],
                            "priority": record["priority"],
                            "reporter": record["reporter"],
                            "status": record["status"],
                            "issue_links": record.get("issue_links"),
                        }
                        if record.get("issue_links"):
                            for issue in record["issue_links"]:
                                if issue['issue_type'] == "Bug" and issue['issue_status'].upper() not in ("DONE", "CLOSED", "ICEBOX"):
                                    errors.append(
                                        f"task {record['id']} has unfinished bug: {issue['id']}({issue['issue_status']})")

                elif request_body['method'] in ("status_check",):
                    for record in resp_body["data"]:
                        extra[record["id"]] = {
                            "summary": record["summary"],
                            "assignee": record["assignee"],
                            "creator": record["creator"],
                            "priority": record["priority"],
                            "reporter": record["reporter"],
                            "status": record["status"],
                            "issue_links": record.get("issue_links"),
                        }
                        if request_body.get('target_status', 'xxxxxx').lower() != record["status"].lower():
                            errors.append(
                                f"task {record['id']} status: {record['status'].lower()} != {request_body.get('target_status', 'Done').lower()}")

                else:
                    errors.append("unknow method")

                if errors:
                    extra["errors"] = errors
                return Pipeline.pipeline_callback(callback, 1 if len(errors) == 0 else 2, **extra)

        else:
            return Pipeline.pipeline_callback(callback, 2, errors=f"jira query status code wrong: {resp.status_code}")
