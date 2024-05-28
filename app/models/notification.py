# -*- coding: utf-8 -*-
# Author: libo (libo@shopee.com)
# Filename: notification.py (c) 2023
# Created:  2023-07-20T06:23:23.710Z


import requests
import datetime
from urllib import parse


class PhoneNoti(object):

    def __init__(self, username, password, HOST_SPACE, HOST_SEE):
        self._username = username
        self._password = password
        self.HOST_SPACE = HOST_SPACE
        self.HOST_SEE = HOST_SEE

        self._token = None
        self._token = self._get_token()

    def request_with_get(self, url, params=None):
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            'accept': 'application/json',
        }
        response = requests.get(url, headers=headers, params=params)
        return response

    def request_with_post(self, url, params=None):
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            'accept': 'application/json',
        }
        response = requests.post(url, headers=headers, json=params)
        return response

    def _get_token(self):
        url = parse.urljoin(self.HOST_SPACE, "/v1/sessions")
        response = requests.post(url, auth=(self._username, self._password))
        return response.json()["token"]

    def send_phone_call(self, phone_number, team, msg):
        """send_phone_call send a phone call to someone

        :param phone_number: phone number to call
        :type phone_number: str
        :param team: team
        :type team: str
        :param msg: message to send
        :type msg: str
        :return: True or False
        :rtype: bool
        """
        url = parse.urljoin(self.HOST_SEE,
                            "/apis/see/v2/incident/call/create")
        params = {
            "message": msg,
            "phone_number": phone_number,
            "team": team
        }
        response = self.request_with_post(url, params)
        resp_data = response.json()
        print(resp_data)
        if response.status_code == 200 and resp_data["result"]["mgk_response"]["error_code"] == '0':
            return True
        else:
            return False

    def get_history(self, limit, msg_type="PhoneCall"):
        url = parse.urljoin(self.HOST_SEE, "/apis/see/v2/history")
        params = {
            "limit": limit,
            "type": msg_type,
            "page": 0
        }
        response = self.request_with_get(url, params)
        if response.status_code == 200 and response.json()["success"]:
            items = response.json()["result"]["items"]
            items = [item for item in items if item["user_email"]
                     == "szqa.bot@shopee.com"]
            return [{
                "type": item["log_type"],
                "email": item["user_email"],
                "phone_number": eval(item["resource"])["phone_number"],
                "team": eval(item["resource"])["team"],
                "message": eval(item["resource"])["message"],
                "created": datetime.datetime.fromtimestamp(item["created_at"])

            } for item in items]
        else:
            return []


if __name__ == "__main__":
    obj = PhoneNoti(HOST_SPACE="https://space.shopee.io",
                    HOST_SEE="https://see.shopee.io/apis/see",
                    username="kobe",
                    password="Kobe_491100")

    print(obj.send_phone_call("+8613395429197", "venus", "hi"))
    print(obj.get_history(10))
