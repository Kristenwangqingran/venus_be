# -*- coding: utf-8 -*-
# @Time    : 2020/8/6
# @Author  : Arrow

from flask import Blueprint
from flask_restful import Api

from .project import ProjectsView, ProjectView, UpdateProjectInfo, PublicProjectCreator, DeleteProjectView
from .git import GitView, GitLogView, ProcessView

project_blueprint = Blueprint('project_blueprint', __name__)

api = Api(app=project_blueprint)
api.add_resource(ProjectsView, '/projects')
api.add_resource(ProjectView, '/projects/<int:id>')
api.add_resource(UpdateProjectInfo, '/projects/update')
api.add_resource(PublicProjectCreator, '/projects/authcreators')
api.add_resource(DeleteProjectView, '/delete_project/<int:id>')

api.add_resource(GitView, '/executors/<int:id>')
api.add_resource(GitLogView, '/executorlog/<int:id>')
api.add_resource(ProcessView, '/process/<int:id>')
