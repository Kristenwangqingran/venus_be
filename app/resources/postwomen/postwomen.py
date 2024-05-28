# -*- coding: utf-8 -*-
# @Time    : 2022/4/14
# @Author  : Jiaxin Chen

import json
import time
import curlify
import requests
import datetime
import traceback
from flask import current_app, request
from app.commons import resp_return, MyRedis, ma
from app.resources import BaseResource
from app.libs import postwomen


class SpexPostWomenView(BaseResource):
    def post(self, api_id):
        try:
            json_data = request.get_json()
            req = json.loads(json_data.get('request', '{}'))
            params = json_data.get('params', {})

            exec_id = int(datetime.datetime.now().timestamp())
            postwomen.queue(exec_id, api_id=api_id, request=req, params=params, timeout=1 *
                            60 * 60, result_ttl=24 * 60 * 60)

            result_hd = MyRedis(current_app.config['URL_FOR_RESULT'])
            timeout = 30
            result = {}
            ret_result = {
                'errorCode': -1,
                'trace_id': '',
                'response': {}
            }
            while timeout:
                result_byte = result_hd.get(exec_id)
                result = json.loads(result_byte) if result_byte else {}
                if result.get("status") == 'done':
                    ret_result['errorCode'] = result.get('errorCode', -1)
                    ret_result['response'] = result.get(
                        'response') if result.get('response') else {}
                    ret_result['trace_id'] = result.get('trace_id', '')
                    break
                else:
                    time.sleep(1)
                    timeout -= 1
            result_hd.disconnect()

            if result.get("status") != 'done':
                return resp_return('COMMON_ERROR', ret_result)

            return resp_return('EXECUTE_OK', ret_result)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class HttpRequestArgs(ma.Schema):
    method = ma.String(default='')
    url = ma.String(default='')
    headers = ma.String(default='{}')
    body = ma.String(default='{}')


class HttpPostWomenView(BaseResource):
    def post(self, ):
        try:
            json_data = request.get_json()
            method = json_data.get("method")
            url = json_data.get("url")
            headers = json.loads(json_data.get("headers"))
            body = json.loads(json_data.get("request"))
            if not method or not url:
                return resp_return('JSON_ERROR', new_msg='No method or url')

            exec_id = int(datetime.datetime.now().timestamp())
            postwomen.queue(exec_id, 'http', method=method, url=url, headers=headers, body=body,
                            timeout=1 * 60 * 60, result_ttl=24 * 60 * 60)

            result_hd = MyRedis(current_app.config['URL_FOR_RESULT'])
            timeout = 30
            result = {}
            ret_result = {
                'status_code': -1,
                'response_headers': {},
                'response': {}
            }
            while timeout:
                result_byte = result_hd.get(exec_id)
                result = json.loads(result_byte) if result_byte else {}
                if result.get("status") == 'done':
                    ret_result['status_code'] = result.get('statusCode', -1)
                    ret_result['response_headers'] = result.get('response_headers', {})
                    ret_result['response'] = result.get('response', {})
                    break
                else:
                    time.sleep(1)
                    timeout -= 1
            result_hd.disconnect()

            if result.get("status") != 'done':
                return resp_return('COMMON_ERROR', ret_result)

            return resp_return('EXECUTE_OK', ret_result)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def get(self, ):
        try:
            try:
                query_args = HttpRequestArgs().dump(request.args)
                method, url = query_args['method'], query_args['url']
                headers = json.loads(query_args['headers'])
                body = json.loads(query_args['body'])
            except Exception as err:
                current_app.logger.error(traceback.format_exc())
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            r = requests.Request(method=method, url=url, headers=headers, json=body).prepare()
            curl = curlify.to_curl(r)

            return resp_return('QUERY_SUCCESS', curl)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class PostWomenResultView(BaseResource):
    def get(self, exec_id):
        try:
            result_hd = MyRedis(current_app.config['URL_FOR_RESULT'])
            result = json.loads(result_hd.get(exec_id))
            result_hd.disconnect()
            return resp_return('EXECUTE_OK', result)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
