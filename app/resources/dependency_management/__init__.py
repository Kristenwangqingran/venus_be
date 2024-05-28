# -*- coding: utf-8 -*-
# @Time    : 2022/08/01
# @Author  : Chen Jiaxin

from flask import Blueprint
from flask_restful import Api
from .szqa_dependency import SzqaDependencyView, DependencyResultView

dependency_blueprint = Blueprint("dependency_mgr", __name__)
api = Api(app=dependency_blueprint)
api.add_resource(SzqaDependencyView, '/szqa_dependency')
api.add_resource(DependencyResultView, '/dependency_result/<int:key>')
