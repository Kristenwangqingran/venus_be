# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Arrow

from flask import Blueprint
from flask_restful import Api

from .page import PagesView, PageView

page_blueprint = Blueprint('page_blueprint', __name__)

api = Api(app=page_blueprint)
api.add_resource(PagesView, '/pages')
api.add_resource(PageView, '/pages/<int:id>')
