# -*- coding: utf-8 -*-
# @Time    : 2022/07/18
# @Author  : Chen Jiaxin

from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck
from .http_project import HttpProject


class HttpMenu(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'http_menu'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    yapi_id = db.Column(db.Integer, nullable=False, index=True)
    desc = db.Column(db.String(127), nullable=True)

    http_project_id = db.Column(db.Integer, db.ForeignKey('http_project.id'))
    http_project = db.relationship('HttpProject', backref=db.backref('menus', lazy=True), lazy='select',
                                   cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    def rdelete(self):
        for http_api in self.apis:
            http_api.rdelete()
        with db.auto_commit_db():
            db.session.delete(self)


class HttpMenusSchema(ma.ModelSchema):
    class Meta:
        model = HttpMenu
        fields = ('id', 'name')


http_menus_schame = HttpMenusSchema()
