import requests
import traceback
import re
from datetime import datetime
from flask import current_app


class TCMMgr:

    AUTH = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYW1lIjoiWHVuIEdvbmciLCJlbWFpbCI6Inh1bi5nb25nQHNob3BlZS5jb20iLCJ0b2tlbiI6ImV5SmhiR2NpT2lKU1V6STFOaUlzSW10cFpDSTZJbU0zWlRFeE5ERXdOVGxoTVRsaU1qRTRNakE1WW1NMVlXWTNZVGd4WVRjeU1HVXpPV0kxTURBaUxDSjBlWEFpT2lKS1YxUWlmUS5leUpwYzNNaU9pSmhZMk52ZFc1MGN5NW5iMjluYkdVdVkyOXRJaXdpWVhwd0lqb2lOVFEwTlRrek5qWTJNell0Y21Wdk1tbDBkV2hoTmprNU1XSTRabkJ4Y25FNE5UTnlNVGxvYm5WbFp6Z3VZWEJ3Y3k1bmIyOW5iR1YxYzJWeVkyOXVkR1Z1ZEM1amIyMGlMQ0poZFdRaU9pSTFORFExT1RNMk5qWXpOaTF5Wlc4eWFYUjFhR0UyT1RreFlqaG1jSEZ5Y1RnMU0zSXhPV2h1ZFdWbk9DNWhjSEJ6TG1kdmIyZHNaWFZ6WlhKamIyNTBaVzUwTG1OdmJTSXNJbk4xWWlJNklqRXhOall5TURFd05EQXdOelF6TkRBeE5UVTROaUlzSW1oa0lqb2ljMmh2Y0dWbExtTnZiU0lzSW1WdFlXbHNJam9pZUhWdUxtZHZibWRBYzJodmNHVmxMbU52YlNJc0ltVnRZV2xzWDNabGNtbG1hV1ZrSWpwMGNuVmxMQ0poZEY5b1lYTm9Jam9pVnpGdVUyaDNkMVZXVGxnMGJVVlVYMjlQWDBzd1FTSXNJbTVpWmlJNk1UWTVNek0zTnpjd015d2libUZ0WlNJNklsaDFiaUJIYjI1bklpd2ljR2xqZEhWeVpTSTZJbWgwZEhCek9pOHZiR2d6TG1kdmIyZHNaWFZ6WlhKamIyNTBaVzUwTG1OdmJTOWhMMEZCWTBoVWRHWjViR0p6VlVwNGEzVkNhMTlqZEY5VlZ6ZEZNVkkyUjJsdU4zbFdiSFYyTFhSQldXeDZUMUF4VjJSUlBYTTVOaTFqSWl3aVoybDJaVzVmYm1GdFpTSTZJbGgxYmlJc0ltWmhiV2xzZVY5dVlXMWxJam9pUjI5dVp5SXNJbXh2WTJGc1pTSTZJbVZ1SWl3aWFXRjBJam94Tmprek16YzRNREF6TENKbGVIQWlPakUyT1RNek9ERTJNRE1zSW1wMGFTSTZJakEzTW1ZNU5ERXhZbVV5TWpoaU5ETmlZV013TkRReE9XRmhZemt6WXpBM09UTmhaVGM1WkdNaWZRLm1RSGZXbU9EejVVRWlmVFZTTEhHZGo4ak9nUHd0QTZWVmdpa1lVeE41MjJqekpPSXBtZHkwczNILXlRck1fNWJrYXVzaUZHdnVxVlhMZEhldkxNS3lXZWl3UFJTWDVfQVlFTzZ3cEstb1E2WlhnUFF6VFB6b296QnpwWVE4WFF2VTIyVVFQd3B0OGVTak9EZEZBWjNiRG5JYmVoYTRoZVdYU0laTjkwWmF5OThRWXlJWUx0Mzk2QzJyZlFrVGh2a3UwMUlpaE10UGhUNEdtZFRSUGxzLTl3YmZIZ0pnR2gxeDJ6YTJHVEhoYUtQMXNWekdPaGdsWFozc2dsMFFoWTJ0RWdDRXZLTmU5RjN4UkNvd21yd0VtVUQ2ajd5bzB0RXNndlVTaXVZWTUybVNGc3E4S2tZUzVSTEZaWWk5YWdTZzE1RWhIZlBFTGhFR1NKN0FFSExXdyIsImlzcyI6InRjbSJ9.y6ZHoxfpSsv-AGKQMP0j95vYNQWS5-lEj-pwD7OLx-U"

    @classmethod
    def __get_rate(cls, data):
        Progress = "unknow"
        PassRate = "unknow"
        extra = {}
        try:
            Progress = round((data['failCount'] + data['ignoreCount'] +
                             data['successCount']) * 100 / data['totalCount'], 2)

            if data['successCount'] + data['failCount'] > 0:
                PassRate = round(data['successCount'] * 100 /
                                 (data['successCount'] + data['failCount']), 2)
            else:
                PassRate = 0

            extra = {
                "failCount": data['failCount'],
                "ignoreCount": data['ignoreCount'],
                "successCount": data['successCount'],
                "totalCount": data['totalCount'],
                "name": data['name'],
                "creator": data['creator'],
                "modifier": data['modifier'],
            }
        except Exception:
            current_app.logger.error(traceback.format_exc())

        return Progress, PassRate, extra

    @classmethod
    def get_rate_by_planID(cls, plan_id):
        tcm_url = f"http://vm2.epd.i.test.shopee.io/tcm/api/v1/testcase_plans/{plan_id}"
        current_app.logger.info(f"tcm_url: {tcm_url}")
        resp = requests.get(tcm_url, headers={
                            "Accept": "application/json", "Authorization": cls.AUTH}, timeout=5)
        try:
            info = resp.json()
            # current_app.logger.info(f"TCM info: {info}")
            data = info['data']

        except Exception:
            current_app.logger.error(traceback.format_exc())
            data = None

        return cls.__get_rate(data)

    @classmethod
    def timestamp_convert(cls, datetime_str):
        datetime_obj = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        seconds = datetime_obj.timestamp()
        return int(seconds)

    @classmethod
    def get_rate_by_planName(cls, plan_name, project_id, ctime_start, ctime_end):
        tcm_url = "http://vm2.epd.i.test.shopee.io/tcm/api/v1/testcase_plans/pagination"
        params = {
            "pageIndex": 1,
            "pageSize": 100,
            "projectId": project_id,
            "name": plan_name
        }
        current_app.logger.info(
            f"get_rate_by_planName tcm_url: {tcm_url}, params: {params}")
        resp = requests.get(tcm_url, headers={
                            "Accept": "application/json", "Authorization": cls.AUTH}, params=params, timeout=60)
        result = []
        try:
            info = resp.json()
            current_app.logger.info(
                f"get_rate_by_planName response: {info}")
            for record in info['data']:
                if cls.timestamp_convert(ctime_start) <= record["cTime"] and record["cTime"] <= cls.timestamp_convert(ctime_end):
                    result.append(cls.__get_rate(record))

        except Exception:
            current_app.logger.error(traceback.format_exc())

        return result

    @classmethod
    def get_plan_link(cls, plan_id):
        return f"https://tcm.epd.i.shopee.io"
