# -*- coding: utf-8 -*-
# @Time    : 2022/3/31
# @Author  : Chen Jiaxin

import os
import traceback
from app.resources import BaseResource
from app.commons import resp_return, MyRedis
from app.commons import aps
from flask import current_app


class AllApsView(BaseResource):
    def get(self, ):
        try:
            tasks = aps.MYASP.show_tasks()
            return resp_return('QUERY_SUCCESS', tasks)
        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))


class DeleteApsView(BaseResource):
    def delete(self, id):
        try:
            aps.MYASP.remove_task(task_id=str(id))
            return resp_return('EXECUTE_OK')
        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))


class ChangeApsView(BaseResource):
    def post(self):
        try:
            current_webserver = os.environ.get("CURRENT_WEBSERVER")
            hd = MyRedis(current_app.config['URL_FOR_RESULT'])
            hd.set('CURRENT_WEBSERVER', current_webserver)
            hd.disconnect()
            current_app.logger.info(f"{current_webserver} has been set to execute aps task.")
            return resp_return('EXECUTE_OK')
        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
