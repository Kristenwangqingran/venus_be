# -*- coding: utf-8 -*-
# @Time    : 2022/07/18
# @Author  : Chen Jiaxin


import os
import requests
import datetime
import traceback
from flask import current_app
from .yapi_client import YapiClient
from app.commons import myrq, Process, RunLogger
from app.commons.hc_gen_case import default_template
from app.models import HttpProject, HttpMenu, HttpApi, HttpEnv, HcTemplate


class HttpApiManagement:
    def __init__(self, token, process=None, yapi_url='', author='', message=True):
        self.yapi_url = yapi_url
        self.token = token
        self.client = YapiClient(token=token, yapi_url=yapi_url)
        self.yapi_project_id = self.client.get_project_id()
        self.process = process
        self.process.reset()
        self.prefix = f"[{process.project_id}] " if process else ""

        self.http_project = None
        self.old_menu = {}
        self.old_api = {}
        self.old_env = {}

        self.author = author
        self.message = message
        self.new_api = []

    def _update_process(self, name, status, detail):
        self.process.update({
            "name": name,
            "status": status,
            "details": detail
        })

    def _update_process_and_log(self, name, status, detail):
        self._update_process(name, status, detail)
        if status in ['fail']:
            current_app.logger.error(self.prefix + detail)
        else:
            current_app.logger.info(self.prefix + detail)

    def _get_old_env(self, http_project):
        for env in http_project.envs:
            self.old_env[env.id] = False

    def _save_env(self, envs):
        self._update_process(name="Update project env", status="ongoing", detail="start update project env ...")
        for env in envs:
            http_env = HttpEnv.query.filter_by(http_project_id=self.http_project.id, yapi_id=env.get("_id", "")).first()
            if http_env:
                http_env.put_save({
                    "name": env.get("name", "no-name"),
                    "domain": env.get("domain", ""),
                    "headers": env.get("header", [])
                })
                msg = f"Update env[name: {http_env.name}] success!"
            else:
                http_env = HttpEnv(**{
                    "name": env.get("name", "no-name"),
                    "domain": env.get("domain", ""),
                    "headers": env.get("header", []),
                    "yapi_id": env.get("_id", ""),
                    "http_project_id": self.http_project.id
                })
                http_env.save()
                msg = f"Create env[name: {http_env.name}] success!"
            self.old_env[http_env.id] = True
            self._update_process_and_log(name="Update project env", status="ongoing", detail=msg)
        self._update_process(name="Update project env", status="success", detail="Done")

    def _get_project_info(self, ):
        self._update_process(
            name="Update project info", status="ongoing", detail="start get project info from yapi ...")
        project_info = self.client.get_project_info()
        self.http_project = HttpProject.query.filter_by(yapi_url=self.yapi_url, yapi_id=self.yapi_project_id).first()
        if self.http_project:
            self.http_project.put_save({
                "name": project_info['name']
            })
            msg = f'Update http project[id:{self.yapi_project_id}] success!'
        else:
            self.http_project = HttpProject(**{
                "name": project_info['name'],
                "yapi_id": self.yapi_project_id,
                "token": self.token,
                "yapi_url": self.yapi_url
            })
            self.http_project.save()
            msg = f'Create http project[id:{self.yapi_project_id}] success!'
        self._update_process_and_log(name="Update project info", status="success", detail=msg)
        self._save_env(project_info["env"])

    def _get_env_list(self, ):
        project_info = self.client.get_project_info()
        return [{"id": env['_id'], "name": env["name"]} for env in project_info["env"]]

    def _get_old(self, ):
        for menu in self.http_project.menus:
            self.old_menu[menu.id] = False
        for api in self.http_project.apis:
            self.old_api[api.id] = False

    def _delete_old_not_valid(self, ):
        self._update_process(name="Delete old", status="ongoing", detail="start delete old ... ")

        need_to_del = \
            [('menu', self.old_menu, HttpMenu), ('api', self.old_api, HttpApi), ('env', self.old_env, HttpEnv)]

        for del_type, del_dict, del_class in need_to_del:
            for del_id in [k for k, v in del_dict.items() if not v]:
                del_obj = del_class.query.get(del_id)
                msg = f"Delete old {del_type} [name: {del_obj.name}]"
                del_obj.rdelete()
                self._update_process_and_log(name="Delete old", status="ongoing", detail=msg)

        self._update_process(name="Delete old", status="done", detail="Done")

    def _get_api_info(self, api_id, menu_id):
        self._update_process(name="Update api", status="ongoing", detail="update api ...")
        api_info = self.client.get_api_info(api_id)

        if api_info["method"].upper() not in ['GET', 'POST', 'PUT', 'DELETE']:
            msg = f'API[yapi id: {api_id}, name: {api_info["name"]}] is not a http api, pass'
            self._update_process_and_log(name="Update api", status="ongoing", detail=msg)
            return ""

        http_api = HttpApi.query.filter_by(http_project_id=self.http_project.id, yapi_id=api_id).first()
        body = HttpApi.get_r_for_health_check(api_info.get("body", {}).get("children", []))
        response = HttpApi.get_r_for_health_check(api_info.get("response", {}).get("children", []))
        errors = HttpApi.parse_error_code(api_info.get("response", {}))
        if http_api:
            http_api.put_save({
                "name": api_info["name"],
                "method": api_info["method"],
                "path": api_info["path"],
                "desc": api_info["desc"],
                "headers": api_info.get("headers", []),
                "params": api_info.get("params", []),
                "query": api_info.get("query", []),
                "body": body,
                "response": response,
                "errors": errors
            })
            self.old_api[http_api.id] = True
            msg = f'Update http api[name:{http_api.name}] success!'
        else:
            http_api = HttpApi(**{
                "yapi_id": api_id,
                "name": api_info["name"],
                "method": api_info["method"],
                "path": api_info["path"],
                "desc": api_info["desc"],
                "headers": api_info.get("headers", []),
                "params": api_info.get("params", []),
                "query": api_info.get("query", []),
                "body": body,
                "response": response,
                "errors": errors,
                "http_menu_id": menu_id,
                "http_project_id": self.http_project.id
            })
            http_api.save()
            msg = f'Create http api[name:{http_api.name}] success!'
            self.new_api.append({
                "yapi_id": api_id,
                "method": api_info["method"],
                "name": api_info["name"]
            })
        self._update_process_and_log(name="Update api", status="ongoing", detail=msg)
        template_msg = ""
        try:
            self._generate_template(body, response, errors, http_api)
        except Exception:
            template_msg = f"Some wrong happened while generating template for api[id: {api_info.get('id')}], \n" \
                           f"{traceback.format_exc()}"
        return template_msg

    def _get_menu_and_api(self, ):
        self._update_process(name="Update menu", status="ongoing", detail="update menu ...")
        menu_info = self.client.get_api_menu_list()
        menu_msg, api_msg, template_msg = "", "", ""
        for menu in menu_info:
            try:
                http_menu = HttpMenu.query.filter_by(http_project_id=self.http_project.id, yapi_id=menu["id"]).first()
                if http_menu:
                    http_menu.put_save({
                        "name": menu["name"],
                        "desc": menu["desc"]
                    })
                    self.old_menu[http_menu.id] = True
                    msg = f'Update http menu[name:{http_menu.name}] success!'
                else:
                    http_menu = HttpMenu(**{
                        "name": menu["name"],
                        "yapi_id": menu["id"],
                        "desc": menu["desc"],
                        "http_project_id": self.http_project.id
                    })
                    http_menu.save()
                    msg = f'Create http menu[name: {http_menu.name}] success!'
                self._update_process_and_log(name="Update menu", status="ongoing", detail=msg)

                for api_info in menu["api_list"]:
                    try:
                        template_msg += self._get_api_info(api_info["id"], http_menu.id)
                    except Exception:
                        api_msg += f"Some wrong happened while dealing with api[id: {api_info.get('id')}], \n" \
                                   f"{traceback.format_exc()}"

            except Exception:
                menu_msg += f"Some wrong happened while dealing with menu[id: {menu.get('id')}], \n" \
                            f"{traceback.format_exc()}"

        current_app.logger.info(f"Get menu and api done.")
        self._update_process_and_log(name="Update menu", status="success" if not menu_msg else "fail",
                                     detail=menu_msg if menu_msg else "Update menus success!")
        self._update_process_and_log(name="Update api", status="success" if not api_msg else "fail",
                                     detail=api_msg if api_msg else "Update apis success!")
        self._update_process_and_log(name="Update template", status="success" if not template_msg else "fail",
                                     detail=template_msg if template_msg else "Update templates success!")

    def _generate_template(self, body, response, errors, http_api):
        self._update_process(name="Update template", status="ongoing", detail="update basic template ...")
        fields = default_template(body, response, list(errors.values()))
        updated = False
        for template in http_api.templates:
            if template.type == 'basic':
                template.put_check({
                    "fields": fields
                })
                updated = True
            else:
                nd = HcTemplate.update_old_template(template.fields, fields)
                template.put_check({
                    "fields": nd
                })

            template.save()

        if not updated:
            template = HcTemplate(**{
                "name": "basic",
                "type": "basic",
                "is_default": True,
                "fields": fields,
                "api_type": "http",
                "http_api_id": http_api.id
            })
            template.save()

        msg = f"Update template for api[name: {http_api.name}] success."
        self._update_process_and_log(name="Update template", status="ongoing", detail=msg)

    def send_message(self, ):
        try:
            if not self.new_api:
                # No messages without new api
                return

            msg = f"{self.author} triggered sync, \n" \
                  f"project yapi_id: {self.yapi_project_id}, name: {self.http_project.name}\n" \
                  f"ends at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                  f"This sync adds the following api [format: <yapi_id> | <method> | <name>]\n"
            for info in self.new_api:
                msg += f'{info.get("yapi_id")} | {info.get("method")} | {info.get("name")}\n'
            for people in current_app.config['SPEX_API_UPDATE_NOTI']:
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
                f"{self.prefix}Send message error: {traceback.format_exc()}")

    def sync_from_yapi(self, ):
        success = True
        try:
            self._get_project_info()
            self._get_old()
            self._get_menu_and_api()
            self._delete_old_not_valid()

            if self.message:
                self.send_message()

        except Exception:
            err = f"Some wrong happened while sync api from yapi: {traceback.format_exc()}"
            self._update_process_and_log(name="sync", status="fail", detail=err)
            success = False

        return success

    def get_env_list(self, ):
        env_list = []
        try:
            env_list = self._get_env_list()

        except Exception:
            current_app.logger.error(f"Some wrong happened while get project env: {traceback.format_exc()}")

        return env_list


@myrq.job('update_spex_api')
def get_http_api(yapi_project_token, process_id=0, yapi_url='', author='', message=True):
    success = True
    logger = None
    process = None
    try:
        logger = RunLogger(process_id, os.path.join(current_app.instance_path, "logs", current_app.config['HC_PATH']))
        process = Process(process_id)
        ham = HttpApiManagement(yapi_project_token, process, yapi_url, author, message)
        success = ham.sync_from_yapi()

    except Exception:
        success = False
        err = f"[{process.project_id}] [RQ]Update http api failed: {traceback.format_exc()}"
        current_app.logger.error(f"[{process_id}] {err}")
        process.update({
            "name": "rq",
            "status": "fail",
            "details": err
        })

    finally:
        if success and process:
            process.finish()
        if logger:
            logger.release()


@myrq.job('update_spex_api')
def update_http_api(project_id_list, process_id=0):
    success = True
    logger = None
    process = None
    try:
        logger = RunLogger(process_id, os.path.join(current_app.instance_path, "logs", current_app.config['HC_PATH']))
        process = Process(process_id)
        for project_id in project_id_list:
            project = HttpProject.query.get(project_id)
            if not project:
                current_app.logger.error(f'[{process_id}] Project id: {project_id} not found!')
            else:
                current_app.logger.info(f"[{process_id}] Start to update project id: {project_id}")
                ham = HttpApiManagement(project.token, process, project.yapi_url)
                success = ham.sync_from_yapi()

    except Exception:
        success = False
        err = f"[{process.project_id}] [RQ]Update http api failed: {traceback.format_exc()}"
        current_app.logger.error(f"[{process_id}] {err}")
        process.update({
            "name": "rq",
            "status": "fail",
            "details": err
        })

    finally:
        if success and process:
            process.finish()
        if logger:
            logger.release()
