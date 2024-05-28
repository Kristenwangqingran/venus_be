# -*- coding: utf-8 -*-
# @Time    : 2020/09/16
# @Author  : gongxun


import os
import datetime
from flask import current_app, request

from app import limiter
from app.commons import resp_return, Process, config
from app.resources import BaseResource
from app.models import Project
from app.libs import git_core
from app.resources.base_resource import limiter_by_path


class GitLogView(BaseResource):

    def get(self, id):
        try:
            project_instance = Project.query.get(id)
            log_file = os.path.join(project_instance.get_log_path(
            ), datetime.datetime.now().strftime("%Y-%m-%d") + '.log')
            current_app.logger.info(log_file)
            if os.path.isfile(log_file):
                content = ''
                with open(log_file) as f:
                    content = f.read()

                if content:
                    return resp_return('QUERY_SUCCESS', content)
                else:
                    return resp_return('FILE_EMPTY')

            else:
                return resp_return('FILE_MISSING')

        except Exception as err:

            return resp_return('COMMON_ERROR', new_msg=str(err))


class GitView(BaseResource):
    decorators = [limiter.limit(
        config.GIT_LIMIT_PATTERN, key_func=limiter_by_path)]

    def get(self, id):
        try:
            if not request.headers.get('email', None):
                return resp_return('NO_LOGIN')

            git_core.queue(id, request.headers.get(
                'email', 'no-user',), request.headers.get('token'), timeout=60 * 60, result_ttl=24 * 60 * 60)
            return resp_return('QUERY_SUCCESS')
        except Exception as err:
            return resp_return('GITPULL_ERR', new_msg=str(err))

    def post(self, id):
        try:
            if not request.headers.get('email', None):
                return resp_return('NO_LOGIN')

            git_core.queue(id, request.headers.get(
                'email', 'no-user'), timeout=60 * 60, result_ttl=24 * 60 * 60)
            return resp_return('QUERY_SUCCESS')
        except Exception as err:
            return resp_return('GITPULL_ERR', new_msg=str(err))


class ProcessView(BaseResource):

    def get(self, id):
        try:
            process = Process(project_id=id)
            info = process.query()
            if not info:
                return resp_return('NOFOUND_ERROR')
            else:
                return resp_return('QUERY_SUCCESS', info)

        except Exception as err:
            return resp_return('COMMON_ERROR', new_msg=str(err))
