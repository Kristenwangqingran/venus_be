# -*- coding: utf-8 -*-
# @Time    : 2022/4/12
# @Author  : Jiaxin Chen


import time
import json
import requests
import traceback
from flask import current_app
from app.models import SuiteResult
from app.commons import myrq


class Goc:
    def __init__(self, suiteresult_id, cov_args, plan_name=''):
        self.suiteresult_id = suiteresult_id
        self.cov_args = cov_args
        self.plan_name = plan_name
        self.cov_type = cov_args.get("cov_type", "go")

    def _send_goc_request(self, api):
        url = current_app.config['GOC_HOST'] + current_app.config[api]
        body = dict(**self.cov_args.get("args", {}))
        body["suiteresult_id"] = str(self.suiteresult_id)
        body["plan_name"] = self.plan_name
        body["cov_type"] = self.cov_type
        if api == 'GOC_CLEAR':
            body["clear"] = self.cov_args.get("clear", True)

        current_app.logger.info(f"Send a request to {url}, body: {body}")
        r = requests.post(url, json=body, timeout=300)
        res = json.loads(r.content.decode())
        current_app.logger.info(f"Get response: {res}")

        if res.get("code", -1) == 0 or not res.get('error', ''):
            current_app.logger.info(f"Successfully execute the {api} command")
        else:
            current_app.logger.error(
                f"Some errors occurred while executing the {api} command: {res.get('error', '')}")

        return res

    def goc_clear(self, ):
        """
        Send a clear request to the goc service
        """
        ok, err_msg = True, ''
        res = self._send_goc_request('GOC_CLEAR')
        if res.get("code", -1) != 0:
            ok, err_msg = False, res.get('error', '')

        # Some services have been locked out
        while res.get("code", -1) == 415:
            suite_result = SuiteResult.query.filter_by(id=self.suiteresult_id).first()
            if suite_result.status == "canceled":
                current_app.logger.warn(
                    f"suite_result id: {self.suiteresult_id} is canceled!")
                break

            current_app.logger.warning(
                f"{res.get('message', '')}: {res.get('error', '')}, wait 300s to send request again.")
            time.sleep(5 * 60)
            # retry
            res = self._send_goc_request('GOC_CLEAR')
            current_app.logger.info(f"Get response: {res}")
            if res.get("code", -1) != 415:
                break

        if res.get("code", -1) == 0:
            ok, err_msg = True, ''
        else:
            ok, err_msg = False, res.get('error', '')

        return ok, err_msg

    def goc_profile(self, ):
        """
        Send a profile request to the goc service
        """
        res = self._send_goc_request('GOC_PROFILE')

        return res.get('error', '')

    def goc_check(self, ):
        res = self._send_goc_request('GOC_CHECK')
        data = res.get("data", {})
        items = data.get("items", [])

        return (True, items) if res.get("code", -1) == 0 else (False, items)

    def goc_unlock(self, ):
        """
        Send a request to unlock the corresponding service
        """
        res = self._send_goc_request('GOC_UNLOCK')

        return res.get('error', '')

    def goc_update(self, ):
        """
        Send a update request to the goc service
        """
        res = self._send_goc_request('GOC_UPDATE')

        return res.get('error', '')


@myrq.job('goc')
def goc_update(suiteresult_id):
    """
    Send a update request to the goc service
    """
    suite_result = SuiteResult.query.get(suiteresult_id)
    goc = Goc(suiteresult_id, suite_result.extra.get('exec_data', {}).get('code_coverage', {}))
    suite_result = SuiteResult.query.get(suiteresult_id)
    errors = goc.goc_update()
    if not suite_result.casesuite.is_manual:
        if not errors:
            suite_result.status = 'done'
    else:
        if not errors:
            suite_result.status = 'pass'
        else:
            suite_result.status = 'fail'
    suite_result.save()

    return errors


@myrq.job('goc')
def goc_profile(suite_result_id):
    """
    Send a profile request to the goc service
    """
    suite_result = None
    try:
        suite_result = SuiteResult.query.get(suite_result_id)
        cov_args = suite_result.extra.get("exec_data", {}).get("code_coverage", {})
        if cov_args and cov_args.get("status", False):
            goc = Goc(suite_result.id, cov_args, suite_result.casesuite.name)
            goc.goc_profile()
            goc.goc_unlock()
            current_app.logger.info("Goc profile done.")
        else:
            current_app.logger.info(f"No need to profile.")
        suite_result.status = 'pass'

    except Exception:
        if suite_result:
            suite_result.status = 'error'
        current_app.logger.error(f"Some wrong happened while getting profile data: {traceback.format_exc()}")

    finally:
        suite_result.save()
