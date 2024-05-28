# -*- coding: utf-8 -*-
# @Time    : 2022/08/24
# @Author  : jiaxin.chen


import traceback
from flask import request, current_app
from app.commons import resp_return
from app.models import SubLine, Feature, feature_schema
from app.resources import BaseResource


class FeaturesView(BaseResource):
    def get(self, sub_line_id):
        try:
            sub_line = SubLine.query.get(sub_line_id)
            if not sub_line:
                return resp_return('NOFOUND_ERROR', new_msg='Not found sub line!')

            data = Feature.query.filter_by(deleted=False, sub_line_id=sub_line_id).all()
            ret = feature_schema.dump(data, many=True)

            return resp_return('QUERY_SUCCESS', ret)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class AddFeatureView(BaseResource):
    def post(self, ):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            json_data['platform'] = 'venus'
            Feature.post_check(json_data)
            feature = feature_schema.load(json_data)
            feature.save()
            return resp_return('CREATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class FeatureView(BaseResource):
    def get(self, feature_id):
        try:
            feature = Feature.query.get(feature_id)
            if not feature:
                return resp_return('NOFOUND_ERROR', new_msg='Not found feature!')

            ret = feature_schema.dump(feature)

            return resp_return('QUERY_SUCCESS', ret)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self, feature_id):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            feature = Feature.query.get(feature_id)
            if not feature:
                return resp_return('NOFOUND_ERROR', new_msg='Not found feature!')

            feature.put_save(json_data)
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self, feature_id):
        try:
            feature = Feature.query.get(feature_id)
            if not feature:
                return resp_return('NOFOUND_ERROR', new_msg='Not found feature!')

            feature.delete()

            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
