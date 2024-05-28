# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Arrow

from flask import Blueprint
from flask_restful import Api

from .suiteresult import SuiteResultsView, SuiteResultView, AppSuiteResultView, AppSuiteResultDeviceDetail

suiteresult_blueprint = Blueprint('suiteresult_blueprint', __name__)

suiteresult = Api(app=suiteresult_blueprint)
suiteresult.add_resource(SuiteResultsView, '/suiteresults')
suiteresult.add_resource(SuiteResultView, '/suiteresults/<int:id>')
suiteresult.add_resource(AppSuiteResultView, '/appsuiteresults/<int:id>')
suiteresult.add_resource(AppSuiteResultDeviceDetail, '/appsuiteresults/<int:suite_result_id>/<string:device_id>')
