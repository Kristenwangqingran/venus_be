# -*- coding: utf-8 -*-
# @Time    : 2020/8/6
# @Author  : Arrow

import copy
import traceback

from flask import request, current_app
from sqlalchemy import or_, and_

import app.commons.utils as utils
from app.commons import ma, resp_return, get_config
from app.models import Env, Project, project_schema, projects_schema, Group, Page, Feature, SubLine
from app.resources import BaseResource
from app.tasks import modify_notification


CONF = get_config()

env_extra_json_data = {"notifications": {"emails": [], "seatalks": [], "mattermosts": [], "at_all": False},
                       "runtime_args": {},
                       "pfbs": {},
                       "spex_info": {}
                       }


class RequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    name = ma.String()
    status = ma.String()
    feature_id = ma.Integer()
    initial_env = ma.String()
    author = ma.String()
    product_line_id = ma.Integer()
    sub_line = ma.String()
    public_project = ma.Boolean(default=True)


class ProjectsView(BaseResource):
    def get(self, ):
        try:
            query_args = RequestArgs().dump(request.args)

        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        try:
            product_line_id = query_args.pop('product_line_id', -1)
            sub_line = query_args.pop('sub_line', None)
            public_project = query_args.pop('public_project', True)

            query = Project.query
            if product_line_id > -1 and sub_line:
                sub_line_instance = SubLine.query.filter_by(
                    name=sub_line, product_line_id=product_line_id, deleted=False).first()
                if sub_line_instance:
                    query = query.join(Feature, Feature.id == Project.feature_id).filter(
                        Feature.sub_line_id == sub_line_instance.id, Feature.deleted == False)
                else:
                    return resp_return('PARAM_INVALID', new_msg=f'Not found sub line')

            param = self.get_common_params(query_args, Project)

            if public_project:
                public_project_param = [Project.public_project == True,
                                        Project.deleted == False, Project.status == 'active']
                query = query.filter(
                    or_(and_(*param), and_(*public_project_param)))
            else:
                query = query.filter(*param)
            projects = query.order_by(Project.public_project.desc(), Project.status, Project.updated_time.desc()).paginate(
                page=query_args["page"], per_page=query_args["per_page"], error_out=False)
            result = projects_schema.dump(projects.items, many=True)

            return resp_return('QUERY_SUCCESS', result, projects.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))

    @staticmethod
    def create_project(json_data):
        Project.post_check(json_data)
        project = project_schema.load(utils.del_id_none(json_data))
        project.save()

        default_group = Group(
            name=project.name, description='default group', project_id=project.id)
        default_group.save()

        default_page = Page(
            name=project.name, description='default page', project_id=project.id)
        default_page.save()

        default_env = Env(
            name='test-env', host="1.2.3.4:8888", description='standard test env', project_id=project.id,
            extra=env_extra_json_data)
        default_env.save()

        default_env = Env(
            name='uat-env', host="1.2.3.4:8888", description='standard uat env', project_id=project.id,
            extra=env_extra_json_data)
        default_env.save()

        default_env = Env(
            name='staging-env', host="1.2.3.4:8888", description='standard staging env', project_id=project.id,
            extra=env_extra_json_data)
        default_env.save()

        default_env = Env(
            name='live-env', host="1.2.3.4:8888", description='standard live env', project_id=project.id,
            extra=env_extra_json_data)
        default_env.save()

        # create related folders
        project.init_dir()
        return project

    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        if not json_data:
            return resp_return('JSON_ERROR')

        try:
            project = self.create_project(json_data)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
        else:
            return resp_return('CREATE_SUCCESS', project.id)


class ProjectView(BaseResource):
    def get(self, id):
        project = Project.query.filter_by(id=id).first()
        if project:
            result = project_schema.dump(project)
            return resp_return('QUERY_SUCCESS', result)
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding project found!")

    def put(self, id):
        json_data = request.get_json()
        if not json_data:
            return resp_return('JSON_ERROR')
        project = Project.query.filter_by(id=id).first()
        if project:
            try:
                user = request.headers.get('email') if not json_data.get(
                    "admin") else project.author
                self.common_put_for_project(project, json_data)

                # has been deleted
                if project.status != 'active':
                    # to disable all suite
                    suites = project.suites
                    for suite in suites:
                        if not suite.schedule:
                            continue
                        tmp_v = copy.deepcopy(suite.schedule)
                        tmp_v['status'] = 'disabled'
                        suite.schedule = tmp_v
                        suite.save()

            except Exception as err:
                current_app.logger.error(traceback.format_exc())
                return resp_return('COMMON_ERROR', new_msg=str(err))
            else:
                if user != project.author:
                    modify_notification.queue(
                        project.name, user, project.author)
                return resp_return('UPDATE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding project found!")

    def delete(self, id):
        project = Project.query.filter_by(id=id).first()
        if project:
            try:
                project.delete()
            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding project found!")


class DeleteProjectView(BaseResource):
    def delete(self, id):
        project = Project.query.filter_by(id=id).first()
        if project:
            try:
                project.rdelete()
            except Exception as err:
                current_app.logger.error(f"Error: {traceback.format_exc()}")
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding project found!")


class UpdateProjectInfo(BaseResource):
    def put(self):
        try:
            projects = Project.query.filter(
                or_(Project.public_project.is_(None)), Project.deleted == False).all()
            if projects:
                for project in projects:
                    if project.public_project is None:
                        project.public_project = False
                    project.save()

            # 旧project补增live-env
            all_projects_id = Project.query.with_entities(Project.id).filter(Project.deleted == False,
                                                                             Project.status == 'active').all()
            for project_id in all_projects_id:
                env = Env.query.filter(Env.project_id == project_id[0]).all()
                if not env:
                    new_env = Env(name='live-env', host="1.2.3.4:8888", description='standard live env',
                                  project_id=project_id[0], extra=env_extra_json_data)
                    new_env.save()

            return resp_return('UPDATE_SUCCESS')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('DB_ERROR', new_msg=str(err))


class PublicProjectCreator(BaseResource):
    def get(self):
        result = current_app.config['ADMIN']
        return resp_return('QUERY_SUCCESS', result)
