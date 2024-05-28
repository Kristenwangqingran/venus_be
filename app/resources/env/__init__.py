# -*- coding: utf-8 -*-
# @Time    : 2020/8/4
# @Author  : Arrow

from flask import Blueprint
from flask_restful import Api

from .env import EnvsView, EnvView, EnvsBatchView

env_blueprint = Blueprint('env_blueprint', __name__)

api = Api(app=env_blueprint)
api.add_resource(EnvsView, '/envs')
api.add_resource(EnvView, '/envs/<int:id>')

api.add_resource(EnvsBatchView, '/envsbatch')
