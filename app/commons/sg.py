# -*- coding: utf-8 -*-
# @Time    : 2021-12-15
# @Author  : GongXun

import requests
from flask import current_app
from blinker import Namespace
from .myrq import myrq
signals = Namespace()
request_record = signals.signal('request_record')


@request_record.connect
def request_record_handler(sender, **kwargs):
    current_app.logger.info(f'Got a signal sent by {sender}, {kwargs}')
    to_record_server.queue(kwargs, timeout=5 * 60, result_ttl=10 * 60)


@myrq.job('record')
def to_record_server(kwargs):
    return  # TODO, just stop record
    headers = {
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(
            url=current_app.config['RECORD_HOST'],
            headers=headers,
            json=kwargs,
            timeout=2
        )
        if r.status_code not in (200, ):
            current_app.logger.error(
                f"insert new record failed: {r.status_code}")
        else:
            current_app.logger.info(f"insert new record success: {r.json()}")

    except Exception as err:
        current_app.logger.error(f"insert new record failed: {str(err)}")
