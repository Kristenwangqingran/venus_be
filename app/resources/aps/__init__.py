# -*- coding: utf-8 -*-
# @Time    : 2022/3/31
# @Author  : Chen Jiaxin

from .aps import AllApsView, DeleteApsView, ChangeApsView
from flask import Blueprint
from flask_restful import Api

aps_blueprint = Blueprint('aps_blueprint', __name__)
api = Api(app=aps_blueprint)

api.add_resource(AllApsView, '/allaps')
api.add_resource(DeleteApsView, '/deleteaps/<int:id>')
api.add_resource(ChangeApsView, '/changeaps')
