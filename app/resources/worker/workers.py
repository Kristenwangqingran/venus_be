# -*- coding: utf-8 -*-
# @Time    : 2020/10/20
# @Author  : GongXun


import traceback
from flask import current_app

from app import limiter
from app.commons import ma, resp_return, utils, config
from app.resources import BaseResource
from app.libs import workermgr
from app.resources.base_resource import limiter_by_path


class WorkersView(BaseResource):

    def get(self):

        try:
            workers = workermgr.get_workers()
            return resp_return('QUERY_SUCCESS', workers, len(workers))

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('PARAMS_ERR', new_msg=str(err))


class UEsView(BaseResource):
    decorators = [limiter.limit(config.UES_LIMIT_PATTERN, key_func=limiter_by_path)]

    def get(self):
        try:
            devices = workermgr.get_UEs()
            return resp_return('QUERY_SUCCESS', devices, len(devices))

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('PARAMS_ERR', new_msg=str(err))

    def post(self):
        try:
            workermgr.update_UEs()
            devices = workermgr.get_UEs()
            return resp_return('CREATE_SUCCESS', devices, len(devices))

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('PARAMS_ERR', new_msg=str(err))
