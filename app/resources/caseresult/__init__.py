# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Arrow

from flask import Blueprint
from flask_restful import Api

from .caseresult import CaseResultsView, CaseResultView, TheCaseResultsView, CaseReasonView, CaseReasonsView, \
    CaseNameSuiteNameView, CaseHTMLView, CaseDeviceView, CaseItemResultView

caseresult_blueprint = Blueprint('caseresult_blueprint', __name__)

api = Api(app=caseresult_blueprint)
api.add_resource(CaseResultsView, '/caseresults')
api.add_resource(CaseResultView, '/caseresults/<int:id>')
api.add_resource(CaseReasonsView, '/casereasons')
api.add_resource(CaseReasonView, '/casereason')
api.add_resource(CaseNameSuiteNameView, '/casenamesuitename')
api.add_resource(CaseItemResultView, '/caseitemresult/<int:case_result_id>')

# add for noti
api.add_resource(TheCaseResultsView, '/thecaseresults')

api.add_resource(CaseHTMLView, '/casehtml/<int:id>')
api.add_resource(CaseDeviceView, '/caseargs/<int:id>')
