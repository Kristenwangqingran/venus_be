# -*- coding: utf-8 -*-
# @Time    : 2022-08-01
# @Author  : peipei.cai


from app.commons import db, ma
from .mixins import TimestampMixin
from .common_check import CommonCheck
from marshmallow import ValidationError, INCLUDE, fields, post_load
from .sub_line import SubLine
from .member import Member


feature_member = db.Table(
    "feature_member",
    db.Column('feature_id', db.Integer, db.ForeignKey('feature.id'), primary_key=True),
    db.Column('member_id', db.Integer, db.ForeignKey('member.id'), primary_key=True)
)


class Feature(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'feature'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127))
    # example: venus, cap
    platform = db.Column(db.String(127), nullable=True)

    sub_line_id = db.Column(db.Integer, db.ForeignKey('sub_line.id'), nullable=True)
    sub_line = db.relationship('SubLine', backref=db.backref('features', lazy=True), lazy='select',
                               cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    members = db.relationship("Member", secondary=feature_member,
                              backref=db.backref('features', lazy=True),
                              lazy='select', cascade="save-update, merge, refresh-expire, expunge")

    @classmethod
    def post_check(cls, data):
        if cls.query.filter_by(sub_line_id=data["sub_line_id"], name=data["name"], deleted=False).all():
            raise ValidationError(f'name has existed!')


class FeatureSchema(ma.ModelSchema):
    class Meta:
        sqla_session = db.session
        unknown = INCLUDE
        model = Feature
        fields = ('id', 'name', 'sub_line_id', 'sub_line', 'product_line_id', 'product_line', 'platform')

    product_line_id = fields.Function(lambda obj: obj.sub_line.product_line.id)
    product_line = fields.Function(lambda obj: obj.sub_line.product_line.name)
    sub_line = fields.Function(lambda obj: obj.sub_line.name)


feature_schema = FeatureSchema()
