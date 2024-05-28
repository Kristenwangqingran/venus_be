# -*- coding: utf-8 -*-
# @Time    : 2022/07/20
# @Author  : Chen Jiaxin


from flask import Blueprint
from flask_restful import Api
from .yapi import HttpProjectsView, HttpProjectView, HttpMenuView, HttpApisView, HttpApiDetailView, HttpEnvsView, \
    HttpEnvDetailView, HttpUpdateView, HttpApiErrorsView


http_blueprint = Blueprint("http_blueprint", __name__)

http_api = Api(app=http_blueprint)
http_api.add_resource(HttpProjectsView, '/http_projects')
http_api.add_resource(HttpProjectView, '/http_project/<int:project_id>')
http_api.add_resource(HttpMenuView, '/http_menu/<int:project_id>')
http_api.add_resource(HttpApisView, '/http_apis')
http_api.add_resource(HttpApiDetailView, '/http_api_detail/<int:api_id>')
http_api.add_resource(HttpEnvsView, '/http_envs')
http_api.add_resource(HttpEnvDetailView, '/http_env_detail/<int:env_id>')
http_api.add_resource(HttpUpdateView, '/http_update')
http_api.add_resource(HttpApiErrorsView, '/http_api_errors/<int:api_id>')
