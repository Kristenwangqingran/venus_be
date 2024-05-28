# -*- coding: utf-8 -*-
# @Time    : 2023-09-19
# @Author  : GongXun

import requests
import traceback
from flask import current_app


def parser(raw_data, variables_mapping):
    url = "http://bot.qa.sz.shopee.io:10001/openapi/parser"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "raw_data": raw_data,
        "variables_mapping": variables_mapping
    }
    result = raw_data
    current_app.logger.info(f"args parser, body: {body}")
    resp = requests.post(url, headers=headers, json=body, timeout=5)
    try:
        resp_body = resp.json()
        current_app.logger.info(f"result: {resp_body}")
        if resp_body['code'] == 0:
            result = resp_body['data']

    except Exception:
        current_app.logger.error(traceback.format_exc())
        result = raw_data
    return result
