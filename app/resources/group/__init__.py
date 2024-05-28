# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Arrow

from flask import Blueprint
from flask_restful import Api

from .group import GroupsView, GroupView, GroupINFOView

group_blueprint = Blueprint('group_blueprint', __name__)

api = Api(app=group_blueprint)
api.add_resource(GroupsView, '/groups')
api.add_resource(GroupView, '/groups/<int:id>')
api.add_resource(GroupINFOView, '/groupinfo/<int:id>')
