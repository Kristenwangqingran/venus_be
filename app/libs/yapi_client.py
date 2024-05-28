# -*- coding: utf-8 -*-
# Author: libo (libo@shopee.com)
# Filename: yapi_client.py (c) 2022
# Created:  2022-05-27T02:32:05.803Z


import requests
import json
import logging
from urllib.parse import urljoin


class YapiConfig:
    URL = "https://adp.i.sz.shopee.io"


class TokenError:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class YapiClient:

    def __init__(self, token, yapi_url=""):
        self._url = yapi_url if yapi_url else YapiConfig.URL
        self._project_id = None
        self._token = None
        self._logger = logging.getLogger("YapiClient")
        self.set_project(token)

    def set_project(self, token):
        self._token = token
        self._project_id = self._get_project_id()

    def get_project_id(self, ):
        return self._project_id

    def _get_project_id(self, ):
        project_info = self.get_project_info()
        return project_info['id']

    def _request_get(self, url, params={}):
        headers = {
            "Content-Type": "application/json"
        }
        params.update({
            "token": self._token
        })
        req = requests.get(urljoin(self._url, url), params=params, headers=headers)
        if req.status_code == 200:
            response = req.json()
            if response["errcode"] != 0:
                if response["errcode"] == 40011:
                    raise TokenError(f"The token provided is wrong and cannot be requested.")
                raise Exception(f"request with url-[{url}] and param-[{params}] fail, error message is [{response['errmsg']}]")
            else:
                return response["data"]
        else:
            raise Exception(f"request with url-[{url}] and param-[{params}] fail, code {req.status_code}")

    @staticmethod
    def _get_query(data):
        query_data = [{
                "name": x["name"],
                "desc": x.get("desc", ""),
                "type": x.get("type", ""),
                "example": x.get("example", ""),
                "required": False if "required" not in x else bool(int(x["required"])),
        } for x in data.get("req_query", [])]
        return query_data

    def _get_body(self, data):
        query_data = {
            "name": "req_body",
            "type": "",
            "children": []
        }

        # req_query
        param_data = []
        if data.get("req_body_other"):
            param_data = self._get_other_data_info(json.loads(data["req_body_other"]))
            query_data.update({"type": "body_json"})
        elif data.get("req_body_form"):
            query_data.update({"type": "body_form"})
            param_data = [{
                "name": x["name"],
                "desc": x.get("desc", ""),
                "type": x["type"],
                "example": x.get("example", ""),
                "required": False if "required" not in x else bool(int(x["required"])),
            } for x in data["req_body_form"]]
        else:
            query_data.update({"type": "other"})
        query_data["children"] = param_data
        return query_data

    @staticmethod
    def _get_header(data):
        data = data.get("req_headers")
        return [{
            # "id": header["_id"],
            "name": header["name"],
            "value": header.get("value", ""),
            "required": bool(int(header["required"]))
        } for header in data]

    def _parse_array(self, data):
        array_type = data['items']['type']
        ret_data = {"type": array_type, "children": None}
        if array_type == 'object':
            ret_items = self._get_other_data_info(data['items'])
        elif array_type == 'array':
            ret_items = [self._parse_array(data['items'])]
        else:
            ret_items = []
        ret_data["children"] = ret_items
        return ret_data

    def _get_other_data_info(self, data):
        format_data = []
        required_list = [] if "required" not in data else data["required"]
        for key, value in data.get("properties", {}).items():
            required = True if key in required_list else False
            if not value.get('type'):
                continue
            current_value = {"name": key, "type": value["type"], "required": required, "desc": value.get("description", ""), "children": []}
            if value["type"] == "object":
                current_value["children"].extend(self._get_other_data_info(value))
            elif value["type"] == "array":
                current_value["children"].append(self._parse_array(value))
            format_data.append(current_value)
        return format_data

    def get_project_info(self):
        """get_project_info get the detail info of the project

        :return: info dict
        :rtype: dict
        """
        resp = self._request_get(url="/api/project/get")
        return {
            "id": resp["_id"],
            "name": resp["name"],
            "env": resp["env"]
        }

    def get_menu_list(self):
        resp = self._request_get(url="/api/interface/getCatMenu", params={"project_id": self._project_id})
        return [{
            "id": x["_id"],
            "name": x["name"],
            "desc": x["desc"]
        } for x in resp]

    def get_api_info(self, api_id):
        resp = self._request_get(url="/api/interface/get", params={"id": api_id})
        resp_body = {
            "name": "resp_body",
            "type": resp["res_body_type"],
            "children": [] if not resp.get("res_body")
            else self._get_other_data_info(json.loads(resp.get("res_body", "{}")))
        }
        return {
            "status": resp["status"],
            "path": resp["path"],
            "id": resp["_id"],
            "method": resp["method"],
            "name": resp["title"],
            "desc": resp.get("desc", ""),
            "headers": self._get_header(resp),
            "params": resp.get("req_params", []),
            "query": self._get_query(resp),
            "body": self._get_body(resp),
            "response": resp_body,
        }

    def get_cat_info(self, cat_id):
        resp = self._request_get(url="/api/interface/list_cat", params={"catid": cat_id, "page": 1, "limit": 1000})
        return resp

    def get_api_list(self):
        resp = self._request_get(url="/api/interface/list", params={"page": 1, "limit": 1000, "project_id": self._project_id})
        return resp

    def get_api_menu_list(self):
        resp = self._request_get(url="/api/interface/list_menu", params={"project_id": self._project_id})
        menu_list = []
        for menu in resp:
            if not menu.get("name"):
                continue
            menu_list.append({
                "id": menu["_id"],
                "name": menu["name"],
                "desc": menu["desc"],
                "api_list": [{
                    "status": x["status"],
                    "id": x["_id"],
                    "method": x["method"],
                    "name": x["title"],
                } for x in menu["list"]],
            })
        return menu_list

    def get_all_api(self):
        menu_list = self.get_api_menu_list()
        for menu in menu_list:
            for api in menu["api_list"]:
                api.update(self.get_api_info(api["id"]))
        return menu_list
