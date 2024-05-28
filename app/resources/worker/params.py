# -*- coding: utf-8 -*-
# @Time    : 2020/10/20
# @Author  : GongXun


import traceback
from flask import request, current_app
from app.commons import ma, resp_return
from app.resources import BaseResource
from app.libs import workermgr


class ParamsView(BaseResource):

    def get(self):
        try:
            params, err = workermgr.get_params()

            if err:
                current_app.logger.error(f"get params failed: {err}")

            if params:
                return resp_return('QUERY_SUCCESS', params, len(params))
            else:
                return resp_return('PARAMS_ERR', new_msg=str(err))

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('PARAMS_ERR', new_msg=str(err))
