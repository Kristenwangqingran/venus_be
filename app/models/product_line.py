# -*- coding: utf-8 -*-
# @Time    : 2022/08/24
# @Author  : Chen Jiaxin

from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck
from marshmallow import ValidationError
from .member import Member


product_line_member = db.Table(
    "product_line_member",
    db.Column('product_line_id', db.Integer, db.ForeignKey('product_line.id'), primary_key=True),
    db.Column('member_id', db.Integer, db.ForeignKey('member.id'), primary_key=True)
)


class ProductLine(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'product_line'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    department = db.Column(db.String(127), nullable=True)
    # cap id
    _id = db.Column(db.Integer)
    # example: venus, cap
    platform = db.Column(db.String(127), nullable=True)

    members = db.relationship("Member", secondary=product_line_member,
                              backref=db.backref('product_lines', lazy=True),
                              lazy='select', cascade="save-update, merge, refresh-expire, expunge")

    @classmethod
    def post_check(cls, data):
        if cls.query.filter_by(name=data["name"], deleted=False).all():
            raise ValidationError(f'name has existed!')


class ProductLineSchema(ma.ModelSchema):
    class Meta:
        sqla_session = db.session
        model = ProductLine
        fields = ('id', 'name', 'department', '_id', 'platform')


product_line_schema = ProductLineSchema()
