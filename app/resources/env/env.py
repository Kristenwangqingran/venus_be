# -*- coding: utf-8 -*-
# @Time    : 2020/8/4
# @Author  : Arrow

import traceback

from flask import request, current_app

import app.commons.utils as utils
from app.commons import ma, resp_return
from app.models import Env, env_schema, Project
from app.resources import BaseResource


class RequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    name = ma.String()
    status = ma.String()
    organized = ma.String()
    project_id = ma.Integer()
    project_name = ma.String()
    dbs = ma.Raw()


class EnvsView(BaseResource):
    def get(self, ):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')
        organized = query_args.pop("organized", None)
        project_name = query_args.pop("project_name", None)

        if organized:
            results = []

            if project_name:
                projects = Project.query.filter(Project.deleted == False, Project.status == "active",
                                                Project.name.ilike(f"%{project_name}%")).order_by(
                    Project.updated_time.desc()).all()
            else:
                projects = Project.query.filter(Project.deleted == False, Project.status == "active").order_by(
                    Project.updated_time.desc()).all()

            for project in projects:
                item = {}
                envs = Env.query.filter(
                    Env.project_id == project.id, Env.deleted == False).all()
                envs = env_schema.dump(envs, many=True)
                item["project"] = project.name
                item["project_id"] = project.id
                item["envs"] = envs
                results.append(item)

            return resp_return('QUERY_SUCCESS', results, len(results))

        else:
            param = self.get_common_params(query_args, Env)
            query = Env.query.filter(*param)
            envs = query.order_by(Env.updated_time.desc()).paginate(
                page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            result = env_schema.dump(envs.items, many=True)
            result = sorted(result, key=lambda x: x['name'])
            return resp_return('QUERY_SUCCESS', result, envs.total)

    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        if not json_data:
            return resp_return('JSON_ERROR')

        try:
            Env.post_check(json_data)
            env = env_schema.load(utils.del_id_none(json_data))
            env.save()

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
        else:
            return resp_return('CREATE_SUCCESS', append=[env.id])


class EnvView(BaseResource):
    def get(self, id):
        env = Env.query.filter_by(id=id).first()
        if env:
            result = env_schema.dump(env)
            return resp_return('QUERY_SUCCESS', result)
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding env found!")

    def put(self, id):
        json_data = request.get_json()
        if not json_data:
            return resp_return('JSON_ERROR')
        env = Env.query.filter_by(id=id).first()
        if env:
            try:
                self.common_put(env, json_data)

            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('UPDATE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding env found!")

    def delete(self, id):
        env = Env.query.filter_by(id=id).first()
        if env:
            try:
                env.delete()
            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding env found!")


class EnvsBatchRequestArgs(ma.Schema):
    project_id = ma.Integer()
    id_list = ma.String()


class EnvsBatchView(BaseResource):

    def get(self, ):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        if query_args.get('project_id', None):
            envs = Env.query.filter_by(
                project_id=query_args['project_id'], deleted=False).all()
        elif query_args.get('id_list', None):
            id_list = [int(item) for item in query_args['id_list'].split(',')]
            envs = Env.query.filter(Env.id.in_(
                id_list), Env.deleted == False).all()
        else:
            envs = None

        if envs:
            try:
                for env in envs:
                    env.delete()
            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding envs found!")
