# -*- coding: utf-8 -*-
# @Time    : 2020/8/7
# @Author  : Arrow

from flask import Blueprint
from flask_restful import Api

from .element import ElementsView, ElementView

element_blueprint = Blueprint('element_blueprint', __name__)

api = Api(app=element_blueprint)
api.add_resource(ElementsView, '/elements')
api.add_resource(ElementView, '/elements/<int:id>')
