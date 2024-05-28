# -*- coding: utf-8 -*-
# @Time    : 2020/09/01
# @Author  : GongXun

from flask import Blueprint
from flask_restful import Api

from .others import (ValidatesView, PlatformsView, APPtypesView, RegionsView,
                     APPInfosView, APPVersionsView, SCPView, TCMView, DeployView, JiraView)

others_blueprint = Blueprint('others_blueprint', __name__)

api = Api(app=others_blueprint)
api.add_resource(ValidatesView, '/validates')

api.add_resource(PlatformsView, '/platforms')
api.add_resource(RegionsView, '/regions')
api.add_resource(APPtypesView, '/apptypes')
api.add_resource(APPInfosView, '/appinfos')
api.add_resource(APPVersionsView, '/appversions')

api.add_resource(SCPView, '/scpdata')
api.add_resource(TCMView, '/tcmdata')
api.add_resource(DeployView, '/deploy')
api.add_resource(JiraView, '/jira')
