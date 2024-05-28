# -*- coding: utf-8 -*-
# @Time    : 2022/08/16
# @Author  : peipei.cai


import traceback
from sqlalchemy import any_
from flask import request, current_app
from app.commons import resp_return, ma
from app.models import Member, member_schema, ProductLine, Feature
from app.resources import BaseResource
from app.libs import sync_member


class MembersRequestArgs(ma.Schema):
    leader = ma.String()
    role = ma.String()
    department_name = ma.String()
    product_line_id = ma.Integer()
    product_line = ma.String()
    sub_line_id = ma.Integer()
    sub_line = ma.String()
    feature_id = ma.Integer()
    feature = ma.String()
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=10)


class MembersView(BaseResource):
    def get(self, ):
        try:
            try:
                query_args = MembersRequestArgs().dump(request.args)
                leader = query_args.get('leader')
                role = query_args.get('role')
                department_name = query_args.get('department_name')
                product_line_id = query_args.get('product_line_id')
                product_line = query_args.get('product_line')
                sub_line_id = query_args.get('sub_line_id')
                sub_line = query_args.get('sub_line')
                feature_id = query_args.get('feature_id')
                feature = query_args.get('feature')
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            query = Member.query.filter_by(deleted=False)
            if leader:
                query = query.filter_by(leader=leader)

            if role:
                query = query.filter(any_(Member.role) == role)

            if department_name:
                query = query.filter(Member.product_lines).filter(
                    ProductLine.department == department_name)

            if product_line_id:
                query = query.filter(Member.product_lines).filter(
                    ProductLine.id.in_([product_line_id]))
            elif product_line:
                query = query.filter(Member.product_lines).filter(
                    ProductLine.name.in_([product_line]))

            if sub_line_id:
                query = query.filter(Member.features).filter(
                    Feature.sub_line_id.in_([sub_line_id]))
            elif sub_line:
                query = query.filter(Member.features).filter(
                    Feature.sub_line.name.in_([sub_line]))

            if feature_id:
                query = query.filter(Member.features).filter(
                    Feature.id.in_([feature_id]))
            elif feature:
                query = query.filter(Member.features).filter(
                    Feature.name.in_([feature]))

            data = query.paginate(
                page=query_args["page"], per_page=query_args["per_page"], error_out=False)

            ret = member_schema.dump(data.items, many=True)

            return resp_return('QUERY_SUCCESS', ret, data.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def post(self, ):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            json_data['platform'] = 'venus'
            Member.post_check(json_data)
            member = member_schema.load(json_data)
            member.save()
            return resp_return('CREATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class MemberQueryRequestArgs(ma.Schema):
    id = ma.Integer()
    email = ma.String()


class MemberView(BaseResource):
    def _find_member(self, data):
        if data.get('id'):
            member = Member.query.get(data['id'])
        elif data.get('email'):
            query = Member.query.filter_by(deleted=False)
            member = query.filter_by(email=data['email']).first()
        else:
            member = None
        return member

    def get(self):
        try:
            try:
                query_args = MemberQueryRequestArgs().dump(request.args)
            except Exception as err:
                return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

            member = self._find_member(query_args)

            if not member:
                return resp_return('NOFOUND_ERROR', new_msg='Not found member!')

            member_info = member_schema.dump(member)

            return resp_return('QUERY_SUCCESS', member_info)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def put(self):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            member = self._find_member(json_data)

            if not member:
                return resp_return('NOFOUND_ERROR', new_msg='Not found member!')

            member.put_save(json_data)
            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')

    def delete(self):
        try:
            json_data = request.get_json()
            if not json_data:
                return resp_return('JSON_ERROR')

            member = self._find_member(json_data)

            if not member:
                return resp_return('NOFOUND_ERROR', new_msg='Not found member!')

            member.delete()

            return resp_return('DELETE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')


class SyncMemberView(BaseResource):
    def post(self, ):
        try:
            sync_member()
            return resp_return('EXECUTE_OK')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=f'{str(err)}')
