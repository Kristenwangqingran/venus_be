# -*- coding: utf-8 -*-
# @Time    : 2020/09/01
# @Author  : GongXun

from flask import Blueprint
from flask_restful import Api

from .params import ParamsView
from .workers import WorkersView, UEsView

worker_blueprint = Blueprint('worker_blueprint', __name__)

api = Api(app=worker_blueprint)

api.add_resource(ParamsView, '/params')
api.add_resource(WorkersView, '/workers')
api.add_resource(UEsView, '/UEs')
