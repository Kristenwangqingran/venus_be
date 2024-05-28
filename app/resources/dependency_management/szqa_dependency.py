# -*- coding: utf-8 -*-
# @Time    : 2022/08/01
# @Author  : Chen Jiaxin


import time
import traceback
from app.resources import BaseResource
from flask import request, current_app
from app.libs import SzqaDependencyMgr, update_szqa_dependency, change_python_path
from app.commons import resp_return


class SzqaDependencyView(BaseResource):
    def get(self, ):
        try:
            mgr = SzqaDependencyMgr()
            result = mgr.run(action="query_szqa_dependency", broadcast=True, timeout=1 * 60)

            return resp_return('QUERY_SUCCESS', result)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, ):
        try:
            json_data = request.get_json()
            timestamp = int(time.time())
            change_python_path.queue(timestamp, json_data.get("use_latest", False), json_data.get("new_path", ""),
                                     timeout=60 * 60, result_ttl=24 * 60 * 60)
            return resp_return('UPDATE_SUCCESS', timestamp)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def post(self, ):
        try:
            timestamp = int(time.time())
            update_szqa_dependency.queue(timestamp, timeout=60 * 60, result_ttl=24 * 60 * 60)
            return resp_return('EXECUTE_OK', timestamp)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class DependencyResultView(BaseResource):
    def get(self, key):
        try:
            mgr = SzqaDependencyMgr(key)
            result = mgr.get_result()

            return resp_return('QUERY_SUCCESS', result)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
