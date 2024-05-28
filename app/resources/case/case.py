# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Xun.Gong

import random
import traceback
from flask import request, current_app
from sqlalchemy.dialects.postgresql import ARRAY
import app.commons.utils as utils
from app.commons import ma, resp_return
from app.models import Case, case_schema, CT_map
from app.resources import BaseResource
from app.libs import CaseUpdateMgr, update_cases


class RequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    name = ma.String()
    category = ma.String()
    project_id = ma.Integer()
    group_id_list = ma.String()
    group_id = ma.Integer()
    priority = ma.String()
    case_id_list = ma.String()
    author = ma.String()
    type = ma.String()
    api = ma.String()


class CasesView(BaseResource):

    def get(self, ):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')
        group_id_list = query_args.pop('group_id_list', None)
        case_id_list = query_args.pop('case_id_list', None)
        api = query_args.pop('api', '')
        param = self.get_common_params(query_args, Case)

        if group_id_list:
            param.append(Case.group_id.in_(
                group_id_list.strip(',').split(',')))

        if api:
            param.append(Case.apis.contains([api]))

        query = Case.query.filter(*param)

        # add to support get a lot of cases name base on cases id list striing (e.g 3,4,5,6,17)
        if case_id_list:
            ids = case_id_list.strip(',').split(',')
            cases = Case.query.filter(Case.id.in_(ids)).all()
            result = case_schema.dump(cases, many=True)
            return resp_return('QUERY_SUCCESS', result, len(cases))
        else:
            cases = query.order_by(Case.updated_time.desc()).paginate(
                page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            result = case_schema.dump(cases.items, many=True)
            return resp_return('QUERY_SUCCESS', result, cases.total)

    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        if not json_data:
            return resp_return('JSON_ERROR')

        try:
            Case.post_check(json_data)
            case = case_schema.load(utils.del_id_none(json_data))
            case.save()

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
        else:
            return resp_return('CREATE_SUCCESS', {"id": case.id})

    def delete(self):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')
        case_id_list = query_args.pop('case_id_list', None)

        if case_id_list:
            ids = case_id_list.strip(',').split(',')
            ids = [int(i) for i in ids]
            cases = Case.query.filter(Case.id.in_(ids)).all()
            for case in cases:
                try:
                    case.delete()
                except Exception as err:
                    return resp_return('DB_ERROR', new_msg=str(err))

            return resp_return('DELETE_SUCCESS')


class CasesByGroupView(BaseResource):
    def post(self, ):
        try:
            json_data = request.get_json()
            group_id_list = json_data.get('group_id_list', [])
            page = json_data.get('page', 1)
            per_page = json_data.get('per_page', 10)

            query_args = {}
            if json_data.get('filter', {}):
                for k, v in json_data['filter'].items():
                    query_args[k] = v

            param = self.get_common_params(query_args, Case)
            cases = Case.query.filter(*param).filter(Case.group_id.in_(group_id_list)).order_by(Case.updated_time).paginate(
                page=page, per_page=per_page, error_out=False)
            result = case_schema.dump(cases.items, many=True)
            return resp_return('QUERY_SUCCESS', result, cases.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))


class WorkerRequestArgs(ma.Schema):
    normal = ma.Boolean(default=False)


class CaseView(BaseResource):

    def get(self, id):
        case = Case.query.filter_by(id=id).first()
        if case:
            result = case_schema.dump(case)
            return resp_return('QUERY_SUCCESS', result)
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding case found!")

    def put(self, id):
        json_data = request.get_json()
        if not json_data:
            return resp_return('JSON_ERROR')
        case = Case.query.filter_by(id=id).first()
        if case:
            try:
                case.put_check(json_data)
                manual_case_id = json_data.get("manual_case_id", None)
                old_manual_case_id = case.manual_case_id if case.manual_case_id is not None else 0

                # if manual_case_id and manual_case_id != old_manual_case_id:
                #     res = CaseUpdateMgr.manual_case_id_sync(
                #         [case.id], [manual_case_id], [old_manual_case_id])
                #     if res:
                #         raise Exception(res)

                for k, v in json_data.items():
                    if k in ('id', 'created_time', 'updated_time'):
                        continue
                    setattr(case, k, v)
                case.save()

            except Exception as err:
                current_app.logger.error(traceback.format_exc())
                return resp_return('COMMON_ERROR', new_msg=str(err))
            else:
                return resp_return('UPDATE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding case found!")

    def delete(self, id):
        case = Case.query.filter_by(id=id).first()
        if case:
            try:
                case.delete()
            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding case found!")


class CaseCloneView(BaseResource):
    def post(self, id):

        case = Case.query.filter_by(id=id).first()
        if case:
            email = request.headers.get(
                'email', '')
            result = case_schema.dump(case)
            result['author'] = email if email else result["author"]
            for item in ("updated_time", "created_time", "id"):
                result.pop(item)
            result['name'] += '-' + str(random.randint(1000, 9999)) + 'copy'
            current_app.logger.info(f"result: {result}")
            new_case = case_schema.load(utils.del_id_none(result))
            new_case.save()

            return resp_return('CLONE_SUCCESS', {'id': new_case.id})
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding case found!")


class CaseManysView(BaseResource):
    def post(self):
        try:
            json_data = request.get_json()

            if not json_data:
                return resp_return('JSON_ERROR')

            update_cases.queue(json_data, timeout=2 * 60 *
                               60, result_ttl=24 * 60 * 60)
            return resp_return(f'CREATE_SUCCESS', new_msg=f"updating...")

        except Exception as err:
            current_app.logger.warn(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
