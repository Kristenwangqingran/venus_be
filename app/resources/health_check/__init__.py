# -*- coding: utf-8 -*-
# @Time    : 2022/2/28
# @Author  : Jiaxin Chen

from flask import Blueprint
from flask_restful import Api
from .template import SpexTemplateView, AddSpexTemplateView, SpexTemplatesView, SpexBasicTemplateView,\
    HttpTemplatesView, AddHttpTemplateView, HttpTemplateView, ApiTemplateView
from .plan import HcPlansView, AddSpexPlanView, SpexPlanView, SpexConfigView, AddHttpPlanView, HttpPlanView
from .plan_result import HcPlanResultsView, HcPlanResultView, HcPlanResultDetailView
from .case_result import HcCaseResultsView, HcCaseResultView
from .task import HcRunView, HcRerunView, SpexAutoCheckView, SpexBatchAutoCheckView, \
    HttpAutoCheckView, HttpBatchAutoCheckView


hc_template_blueprint = Blueprint("hc_template_blueprint", __name__)
hc_plan_blueprint = Blueprint("hc_plan_blueprint", __name__)
hc_plan_result_blueprint = Blueprint("hc_plan_result_blueprint", __name__)
hc_task_blueprint = Blueprint("hc_task_blueprint", __name__)

template_api = Api(app=hc_template_blueprint)
template_api.add_resource(SpexTemplatesView, '/spex_templates/<int:api_id>')
template_api.add_resource(AddSpexTemplateView, '/spex_template')
template_api.add_resource(SpexTemplateView, '/spex_template/<int:template_id>')
template_api.add_resource(SpexBasicTemplateView, '/spex_basic_template/<int:api_id>')
template_api.add_resource(ApiTemplateView, '/api_templates')
# for http
template_api.add_resource(HttpTemplatesView, '/http_templates/<int:api_id>')
template_api.add_resource(AddHttpTemplateView, '/http_template')
template_api.add_resource(HttpTemplateView, '/http_template/<int:template_id>')

plan_api = Api(app=hc_plan_blueprint)
plan_api.add_resource(HcPlansView, '/hc_plans')
plan_api.add_resource(AddSpexPlanView, '/spex_plan')
plan_api.add_resource(SpexPlanView, '/spex_plan/<int:plan_id>')
plan_api.add_resource(SpexConfigView, '/spex_config')
# for http
plan_api.add_resource(AddHttpPlanView, '/http_plan')
plan_api.add_resource(HttpPlanView, '/http_plan/<int:plan_id>')

result_api = Api(app=hc_plan_result_blueprint)
result_api.add_resource(HcPlanResultsView, '/hc_plan_results')
result_api.add_resource(HcPlanResultView, '/hc_plan_result/<int:planresult_id>')
result_api.add_resource(HcPlanResultDetailView, '/hc_plan_result_detail/<int:plan_result_id>')
result_api.add_resource(HcCaseResultsView, '/hc_case_results')
result_api.add_resource(HcCaseResultView, '/hc_case_result/<int:case_result_id>')

task_api = Api(app=hc_task_blueprint)
task_api.add_resource(HcRunView, '/hc_run/<int:plan_id>')
task_api.add_resource(HcRerunView, '/hc_rerun/<int:plan_id>')
task_api.add_resource(SpexAutoCheckView, '/spex_autocheck/<int:api_id>')
task_api.add_resource(SpexBatchAutoCheckView, '/spex_batch_autocheck/<int:service_id>')
# for http
task_api.add_resource(HttpAutoCheckView, '/http_autocheck/<int:api_id>')
task_api.add_resource(HttpBatchAutoCheckView, '/http_batch_autocheck/<int:project_id>')
