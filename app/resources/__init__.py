# -*- coding: utf-8 -*-
# @Time    : 2020-08-04
# @Author  : GongXun

from .base_resource import BaseResource, OpenAPIRequestArgs
from .env import env_blueprint
from .project import project_blueprint
from .case import case_blueprint
from .casesuite import casesuite_blueprint
from .caseresult import caseresult_blueprint
from .group import group_blueprint
from .suiteresult import suiteresult_blueprint
from .task import task_blueprint
from .worker import worker_blueprint
from .file import file_blueprint
from .page import page_blueprint
from .element import element_blueprint
from .others import others_blueprint
from .attachment import attachment_blueprint
from .product_line import product_blueprint
from .goc import goc_blueprint
from .spex_management import spex_blueprint
from .health_check import hc_template_blueprint, hc_plan_blueprint, hc_plan_result_blueprint, hc_task_blueprint
from .aps import aps_blueprint
from .postwomen import postwomen_blueprint, postwomen_template_blueprint
from .http_management import http_blueprint
from .member import member_blueprint
from .dependency_management import dependency_blueprint
