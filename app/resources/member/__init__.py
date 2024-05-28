# -*- coding: utf-8 -*-
# @Time    : 2022/08/16
# @Author  : peipei.cai

from flask import Blueprint
from flask_restful import Api

from .member import MemberView, MembersView, SyncMemberView

member_blueprint = Blueprint('member_blueprint', __name__)

api = Api(app=member_blueprint)
api.add_resource(MemberView, '/member')
api.add_resource(MembersView, '/members')
api.add_resource(SyncMemberView, '/sync_member')
