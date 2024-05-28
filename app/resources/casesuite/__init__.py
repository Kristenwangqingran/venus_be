# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Arrow

from flask import Blueprint
from flask_restful import Api

from .casesuite import CasesuiteView, CasesuitesView, SuiteCloneView, PlanVerifyView, BGView, CasesuitePageView, \
    CasesuiteSetTopView, EditCaseExecDepView, CronExpressionToDateTime

casesuite_blueprint = Blueprint('casesuite_blueprint', __name__)

api = Api(app=casesuite_blueprint)
api.add_resource(CasesuitesView, '/casesuites')
api.add_resource(CasesuiteView, '/casesuites/<int:id>')
api.add_resource(CasesuitePageView, '/casesuitepage/<int:id>')
api.add_resource(CasesuiteSetTopView, '/casesuitesettop/<int:id>')
api.add_resource(EditCaseExecDepView, '/editcaseexecdep')
api.add_resource(SuiteCloneView, '/suiteclone/<int:id>')
api.add_resource(CronExpressionToDateTime, '/crontodate')

api.add_resource(PlanVerifyView, '/planverify')
api.add_resource(BGView, '/bgsuite')
