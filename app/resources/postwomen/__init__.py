# -*- coding: utf-8 -*-
# @Time    : 2022/4/14
# @Author  : Jiaxin Chen

from flask import Blueprint
from flask_restful import Api
from .postwomen import SpexPostWomenView, PostWomenResultView, HttpPostWomenView
from .postwomen_template import PostWomenTemplatesView, PostWomenTemplateView, AddTemplateView

postwomen_blueprint = Blueprint("postwomen_blueprint", __name__)
postwomen_template_blueprint = Blueprint("postwomen_template_blueprint", __name__)

postwomen_template_api = Api(app=postwomen_template_blueprint)
postwomen_template_api.add_resource(PostWomenTemplatesView, '/postwomen_templates/<int:api_id>')
postwomen_template_api.add_resource(PostWomenTemplateView, '/postwomen_template/<int:id>')
postwomen_template_api.add_resource(AddTemplateView, '/add_postwomen_template')

postwomen_api = Api(app=postwomen_blueprint)
postwomen_api.add_resource(SpexPostWomenView, '/postwomen/spex/<int:api_id>')
postwomen_api.add_resource(HttpPostWomenView, '/postwomen/http')
postwomen_api.add_resource(PostWomenResultView, '/postwomenresult/<int:exec_id>')
