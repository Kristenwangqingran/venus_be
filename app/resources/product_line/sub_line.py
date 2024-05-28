# -*- coding: utf-8 -*-
# @Time    : 2022/08/24
# @Author  : jiaxin.chen


import traceback
from flask import request, current_app
from app.commons import resp_return
from app.models import ProductLine, sub_line_schema, SubLine
from app.resources import BaseResource


class SubLinesView(BaseResource):
    def get(self, product_line_id):
        try:
            product_line = ProductLine.query.get(product_line_id)
            if not product_line:
                return resp_return('NOFOUND_ERROR', new_msg='Not found product line!')

            data = SubLine.query.filter_by(deleted=False, product_line_id=product_line_id).all()
            ret = sub_line_schema.dump(data, many=True)

            return resp_return('QUERY_SUCCESS', ret)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class AddSubLineView(BaseResource):
    def post(self, ):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            json_data['platform'] = 'venus'
            SubLine.post_check(json_data)
            sub_line = sub_line_schema.load(json_data)
            sub_line.save()
            return resp_return('CREATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SubLineView(BaseResource):
    def get(self, sub_line_id):
        try:
            sub_line = SubLine.query.get(sub_line_id)
            if not sub_line:
                return resp_return('NOFOUND_ERROR', new_msg='Not found sub line!')

            ret = sub_line_schema.dump(sub_line)

            return resp_return('QUERY_SUCCESS', ret)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, sub_line_id):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            sub_line = SubLine.query.get(sub_line_id)
            if not sub_line:
                return resp_return('NOFOUND_ERROR', new_msg='Not found sub line!')

            sub_line.put_save(json_data)
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self, sub_line_id):
        try:
            sub_line = SubLine.query.get(sub_line_id)
            if not sub_line:
                return resp_return('NOFOUND_ERROR', new_msg='Not found sub line!')

            sub_line.delete()

            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
