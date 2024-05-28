# -*- coding: utf-8 -*-
# @Time    : 2022/01/25
# @Author  : Chen Jiaxin

from flask import Blueprint
from flask_restful import Api
from .spex import SpexUpdateView, SpexTopicView, SpexApisView, SpexMenuView, \
    SpexDetailView, SpexServiceView, SpexServiceApisView, SpexGroupInfo, \
    SpexApiView, SpexPbView, SpexApiListView, SpexApisv2View, SpexApiErrorsView, PfbView

spex_blueprint = Blueprint('spex_blueprint', __name__)
api = Api(app=spex_blueprint)

api.add_resource(SpexMenuView, '/spexmenu/<int:group_id>')
api.add_resource(SpexGroupInfo, '/spexgroupinfo/<int:group_id>')
api.add_resource(SpexTopicView, '/spextopic/<int:service_id>')
api.add_resource(SpexServiceApisView, '/spexapi/<int:service_id>')
api.add_resource(SpexApiView, '/spexapi/<int:planresult_id>')
api.add_resource(SpexApiListView, '/spexapilist')
api.add_resource(SpexDetailView, '/spexdetail/<int:api_id>')
api.add_resource(SpexUpdateView, '/spexupdate')
api.add_resource(SpexServiceView, '/spexservice')
api.add_resource(SpexApisView, '/spexapis')
api.add_resource(SpexApiErrorsView, '/spex_api_errors/<int:api_id>')
api.add_resource(SpexApisv2View, '/spexapisv2')
api.add_resource(SpexPbView, '/spexpb')
api.add_resource(PfbView, '/pfbs/<int:api_id>')
