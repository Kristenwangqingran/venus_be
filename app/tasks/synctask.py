# -*- coding: utf-8 -*-
# @Time    : 2020-09-08
# @Author  : GongXun


import os
import requests
from flask import current_app
from app.commons import myrq


@myrq.job('notification')
def modify_notification(name, user, owner):
    g_name = ""
    if os.environ.get("ENV_CONFIG", "") == "test":
        owner = "zongqing.ji@shopee.com"
        g_name = "Automation Platform QABOT_NOTI"
    body = {
        "channel": "st",
        "content": f"Your automation platform project/test plan: '{name}' has been modified by {user}",
        "g_name": g_name,
        "u_name": f"{owner}"
    }
    requests.post(url=current_app.config['QABOT_NOTI'], headers={
        "accept": "application/json", "Content-Type": "application/json"}, json=body)
