# -*- coding: utf-8 -*-
# @Time    : 2022/07/18
# @Author  : Chen Jiaxin

from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck


class HttpProject(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'http_project'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    yapi_id = db.Column(db.Integer, nullable=False, index=True)
    token = db.Column(db.String(127), nullable=False)
    yapi_url = db.Column(db.String(127), nullable=False)

    def rdelete(self, ):
        for plan in self.plans:
            plan.rdelete()
        for env in self.envs:
            env.rdelete()
        for api in self.apis:
            api.rdelete()
        for menu in self.menus:
            menu.rdelete()
        super().rdelete()


class HttpProjectsSchema(ma.ModelSchema):
    class Meta:
        model = HttpProject
        fields = ('id', 'name', 'yapi_id', 'yapi_url')


http_projects_schema = HttpProjectsSchema()
