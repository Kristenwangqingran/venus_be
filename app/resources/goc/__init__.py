# -*- coding: utf-8 -*-
# @Time    : 2021/11/23
# @Author  : Chen Jiaxin

from flask import Blueprint
from flask_restful import Api
from .goc import InstanceView, CovLogView, CovUpdateView, ConfigView

goc_blueprint = Blueprint('goc_blueprint', __name__)

api = Api(app=goc_blueprint)
api.add_resource(InstanceView, '/instances')
api.add_resource(ConfigView, '/config/<int:suite_id>')
api.add_resource(CovLogView, '/covlog/<int:suiteresult_id>')
api.add_resource(CovUpdateView, '/covupdate/<int:suiteresult_id>')
