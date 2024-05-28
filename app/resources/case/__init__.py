# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Arrow

from flask import Blueprint
from flask_restful import Api

from .case import CasesView, CaseView, CaseManysView, CaseCloneView, CasesByGroupView

case_blueprint = Blueprint('case_blueprint', __name__)

case = Api(app=case_blueprint)
case.add_resource(CasesView, '/cases')
case.add_resource(CaseView, '/cases/<int:id>')
case.add_resource(CasesByGroupView, '/cases/by_group_id')

case.add_resource(CaseManysView, '/cases/many')

case.add_resource(CaseCloneView, '/caseclone/<int:id>')
