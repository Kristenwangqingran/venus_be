# -*- coding: utf-8 -*-
# @Time    : 2020/09/23
# @Author  : GongXun

from flask import Blueprint
from flask_restful import Api

from .file import FilesView, FilelistView, CaseFilesView, PicsView

file_blueprint = Blueprint('file_blueprint', __name__)

api = Api(app=file_blueprint)
api.add_resource(FilesView, '/files/<int:id>', endpoint="files")
api.add_resource(CaseFilesView, '/casefiles/<int:id>', endpoint="casefiles")
api.add_resource(FilelistView, '/filelist/<int:id>')
api.add_resource(PicsView, '/pics')
