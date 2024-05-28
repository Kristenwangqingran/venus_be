# -*- coding: utf-8 -*-
# @Time    : 2020-08-04
# @Author  : GongXun

from .member import Member, member_schema
from .env import Env, env_schema
from .project import Project, project_schema, projects_schema
from .feature import Feature, feature_schema
from .case import Case, case_schema, simplecase_schema
from .casesuite import Casesuite, casesuite_schema
from .suiteresult import SuiteResult, suiteresult_schema
from .caseresult import CaseResult, caseresult_schema, caseresults_schema
from .group import Group, group_schema
from .page import Page, page_schema
from .element import Element, element_schema
from .mixins import (CaseType, TaskStatus, TaskStatus_DONE, TaskStatus_UNSUCCESS, ExecutorType, CT_map, TC_map,
                     DEFAULT_CASE_TIMEOUT, CASE_UNPASS_REASON, ValidateMethod, PriorityType, THR_ExecutorType,
                     OFFICIAL_ExecutorType, OFFICIAL_ENVType, CaseType_to_ARGS, ALL_Device_ARGS, MAX_CaseType, Run_Log_Type,
                     REGIONs, PLATFORMs, APPTYPEs, MobileCaseType, TaskStatus_UNDONE, HTTP_TYPE)
from .record import Record, record_schema
from .spexservicegroup import SpexServiceGroup, spex_service_group_schema, spex_service_group_detail_schema
from .spexservice import SpexService, spex_service_schema, spex_service_query_schema, spex_service_detail_schema
from .spexapi import SpexApi, spex_api_schema, spex_api_overview_schema
from .hc_template import HcTemplate, hc_template_schema, hc_templates_schema, hc_template_detail_schema, \
    http_template_schema, http_template_detail_schema
from .hc_plan import HcPlan, hc_plan_detail_schema, hc_plans_schema, \
    HttpPlan, http_plans_schema, http_plan_detail_schema
from .hc_planresult import HcPlanResult, hc_plan_result_schema
from .statistics import Statistic, statistic_schema
from .postwomen_template import PostWomenTemplate, postwomen_templates_schema, postwomen_template_detail_schema, \
    postwomen_template_schema
from .http_project import HttpProject, http_projects_schema
from .http_menu import HttpMenu, http_menus_schame
from .http_api import HttpApi, http_apis_schame, http_api_detail_schema
from .http_env import HttpEnv, http_envs_schema, http_env_detail_schema
from .product_line import ProductLine, product_line_schema
from .sub_line import SubLine, sub_line_schema
from .hc_case import HcCase, HcCaseSchema
from .hc_case_result import HcCaseResult, HcCaseResultSchema
