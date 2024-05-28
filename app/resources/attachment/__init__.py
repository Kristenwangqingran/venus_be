# -*- coding: utf-8 -*-
# @Time    : 2020/12/17
# @Author  : GongXun

from flask import Blueprint
from flask_restful import Api

from .attachment import AttachmentsView

attachment_blueprint = Blueprint('attachment_blueprint', __name__)

api = Api(app=attachment_blueprint)
api.add_resource(AttachmentsView, '/attachments/<int:id>')
