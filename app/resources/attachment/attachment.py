# -*- coding: utf-8 -*-
# @Time    : 2020/09/23
# @Author  : GongXun


import os
from urllib import parse

from flask import request, current_app, send_file, url_for
from flask.helpers import send_file
from werkzeug.utils import secure_filename
from app.commons import db, ma, resp_return
from app.models import CaseResult
from app.resources import BaseResource
import re
import random
import traceback


class RequestArgs(ma.Schema):
    filepath = ma.String(default='')


class AttachmentsView(BaseResource):

    def walkdir(self, dst_dir, subdir, dst_url, recurse=False):
        real_dst_dir = os.path.join(dst_dir, subdir)
        real_dst_url = os.path.join(dst_url, subdir)
        file_list = []
        if not os.path.exists(real_dst_dir):
            return file_list

        all_things = os.listdir(real_dst_dir)
        for item in all_things:
            if os.path.isfile(os.path.join(
                    real_dst_dir,
                    os.path.basename(item))) and not item.startswith('.'):
                file_list.append(
                    {
                        "dir": False,
                        "name": os.path.join(subdir, item),
                        "url": os.path.join(real_dst_url, item)

                    }
                )
            elif os.path.isdir(os.path.join(real_dst_dir, item)) and not item.startswith('.'):
                file_list.append(
                    {
                        "dir": True,
                        "name": os.path.join(subdir, item),
                    }
                )
                if recurse:
                    file_list += self.walkdir(dst_dir,
                                              os.path.join(subdir, os.path.basename(item)), dst_url, recurse)

            else:
                continue
        return file_list

    def walkdir2(self, dst_dir, subdir, dst_url):
        real_dst_dir = os.path.join(dst_dir, subdir)
        real_dst_url = os.path.join(dst_url, subdir)
        file_list = []
        if not os.path.exists(real_dst_dir):
            return file_list

        all_things = os.listdir(real_dst_dir)
        for item in all_things:
            if os.path.isfile(os.path.join(
                    real_dst_dir,
                    os.path.basename(item))) and not item.startswith('.'):
                file_list.append(
                    {
                        "key": random.randint(10000000, 99999999),
                        "title": item,
                        "url": os.path.join(real_dst_url, parse.quote(item)),
                        "children": False
                    }
                )
            elif os.path.isdir(os.path.join(real_dst_dir, item)) and not item.startswith('.'):
                file_list.append(
                    {
                        "key": random.randint(10000000, 99999999),
                        # "title": os.path.join(subdir, item),
                        "title": item,
                        "url": os.path.join(real_dst_url, parse.quote(item)),
                        "children":  True
                    }
                )

            else:
                continue
        return file_list

    def get(self, id):

        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        try:
            case_result = CaseResult.query.get(id)
            base_log_path = case_result.get_absolute_logdir()
            base_url_path = os.path.join(
                current_app.config['TOMCAT_HOST'], case_result.get_relative_logdir())

            if query_args.get('filepath', None):
                base_log_path = os.path.join(
                    base_log_path, query_args.get('filepath'))
                base_url_path = os.path.join(
                    base_url_path, query_args.get('filepath'))

            current_app.logger.info(
                f"caseresult({id}) log path: {base_log_path}")

            if os.path.isfile(base_log_path):
                return send_file(base_log_path, as_attachment=True)

            elif os.path.isdir(base_log_path):
                # result = self.walkdir(
                #     base_log_path, '', base_url_path, recurse=True)
                result = self.walkdir2(
                    base_log_path, '', base_url_path)
                return resp_return('QUERY_SUCCESS', result, len(result))

            else:
                current_app.logger.warning(f"{base_log_path} missing")
                return resp_return('FILE_MISSING', new_msg="Log file missing!")

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
