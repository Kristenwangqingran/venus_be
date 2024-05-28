# -*- coding: utf-8 -*-
# @Time    : 2020/09/01
# @Author  : GongXun

from flask import Blueprint
from flask_restful import Api

from .task import (CasesRunView, CaseRunView, ManualCaseRunView, SuiteRunView,
                   LogsClearView, SuiteRerunView, CaseRerunView, SuiteRetryView, ManualPlanView,
                   SuiteRunForWebhookView, SuiteRunForWebhooksView)

task_blueprint = Blueprint('task_blueprint', __name__)

api = Api(app=task_blueprint)
# batch run case
api.add_resource(CasesRunView, '/casetests')

api.add_resource(CaseRunView, '/casetests/<int:id>')
api.add_resource(SuiteRunView, '/suitetests/<int:id>')

api.add_resource(ManualCaseRunView, '/manualcase')

api.add_resource(LogsClearView, '/logsclear/<int:month>')

api.add_resource(SuiteRerunView, '/suitererun/<int:id>')
api.add_resource(CaseRerunView, '/casererun/<int:id>')
api.add_resource(SuiteRetryView, '/suiteretry/<int:id>')

api.add_resource(ManualPlanView, '/manual_plan_run/<int:id>')

api.add_resource(SuiteRunForWebhookView, '/suite_run_for_webhook/<int:id>')
api.add_resource(SuiteRunForWebhooksView, '/suite_run_for_webhook')
