# -*- coding: utf-8 -*-
# @Time    : 2021/11/23
# @Author  : Chen Jiaxin

import os
import json
import requests
import traceback
from app.resources import BaseResource
from app.commons import resp_return, ma
from app.libs import goc_update, Goc
from app.models import SuiteResult, Casesuite
from flask import current_app, request
from flask.helpers import send_file


class RequestArgs(ma.Schema):
    filepath = ma.String(default='')


class InstanceView(BaseResource):
    def get(self):
        try:
            url = current_app.config['GOC_HOST'] + \
                current_app.config['GOC_INSTANCE']
            current_app.logger.info(f"Send a request to {url}")
            r = requests.get(url, timeout=5)
            res = json.loads(r.content.decode())
            current_app.logger.info(f"Get response: {res}")

            data = res.get("data", {})
            ret = []
            for _, instance_list in data.items():
                ret += instance_list

            return resp_return('COMMON_OK', sorted(list(set(ret))))

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))


class ConfigView(BaseResource):
    def get(self, suite_id):
        try:
            config = {}
            suite_cls = Casesuite.query.get(suite_id)
            if not suite_cls:
                return resp_return('NOFOUND_ERROR', new_msg="No corresponding suite found!")

            suite_results = sorted(
                suite_cls.results, key=lambda x: x.updated_time, reverse=True)
            for suite_result in suite_results:
                config = suite_result.extra.get(
                    "exec_data", {}).get("code_coverage", {})
                if config:
                    return resp_return('COMMON_OK', config)

            return resp_return('COMMON_OK', config)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))


class CovLogView(BaseResource):
    def walkdir(self, dst_dir, subdir, dst_url, report=False):
        real_dst_dir = os.path.join(dst_dir, subdir)
        real_dst_url = os.path.join(dst_url, subdir)
        file_list = []
        if not os.path.exists(real_dst_dir):
            return file_list

        all_things = os.listdir(real_dst_dir)
        count = 1
        for item in all_things:
            if os.path.isfile(os.path.join(
                    real_dst_dir,
                    os.path.basename(item))) and not item.startswith('.'):
                file_list.append(
                    {
                        "key": count,
                        "title": item,
                        "url": os.path.join(real_dst_url, item),
                        "children": False
                    }
                )
                count += 1

            elif os.path.isdir(os.path.join(real_dst_dir, item)) and not item.startswith('.'):
                if report:
                    continue

                file_list.append(
                    {
                        "key": count,
                        # "title": os.path.join(subdir, item),
                        "title": item,
                        "url": os.path.join(real_dst_url, item),
                        "children":  True
                    }
                )
                count += 1

            else:
                continue
        return file_list

    def get(self, suiteresult_id):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        try:
            suite_result = SuiteResult.query.get(suiteresult_id)
            if not suite_result:
                return resp_return('NOFOUND_ERROR', new_msg='No corresponding results found!')

            if not suite_result.extra.get("exec_data", {}).get("code_coverage", {}).get("status", False):
                return resp_return('COMMON_ERROR', new_msg='No goc performed this time.')

            goc = Goc(suiteresult_id, suite_result.extra.get('exec_data', {}).get('code_coverage', {}))
            ok, items = goc.goc_check()

            base_log_path = items[0]
            base_url_path = os.path.join(
                current_app.config['TOMCAT_HOST'], base_log_path.replace('/home/admin/instance/logs/', ''))

            filepath = query_args.get('filepath', None)
            if filepath:
                base_log_path = os.path.join(base_log_path, filepath)
                base_url_path = os.path.join(base_url_path, filepath)

            report = True if filepath and filepath == 'report' else False

            current_app.logger.info(
                f"Suite {suiteresult_id} cov log path: {base_log_path}")

            if os.path.isfile(base_log_path):
                return send_file(base_log_path, as_attachment=True)

            elif os.path.isdir(base_log_path):
                result = self.walkdir(
                    base_log_path, '', base_url_path, report)
                return resp_return('QUERY_SUCCESS', result, len(result))

            else:
                current_app.logger.warning(f"{base_log_path} missing")
                return resp_return('FILE_MISSING')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))


class CovUpdateView(BaseResource):
    def get(self, suiteresult_id):
        try:
            goc_update.queue(suiteresult_id, timeout=30 *
                             60, result_ttl=24 * 60 * 60)
            return resp_return('COMMON_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
