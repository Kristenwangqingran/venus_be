# -*- coding: utf-8 -*-
# @Time    : 2022/08/24
# @Author  : Chen Jiaxin


from .mixins import TimestampMixin
from app.commons import db, ma
from .common_check import CommonCheck
from marshmallow import ValidationError, INCLUDE, fields, post_load
from .product_line import ProductLine


class SubLine(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'sub_line'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), nullable=False)
    # example: venus, cap
    platform = db.Column(db.String(127), nullable=True)

    product_line_id = db.Column(db.Integer, db.ForeignKey('product_line.id'), nullable=False)
    product_line = db.relationship('ProductLine', backref=db.backref('sub_lines', lazy=True), lazy='select',
                                   cascade="save-update, merge, refresh-expire, expunge", single_parent=True)

    @classmethod
    def post_check(cls, data):
        if cls.query.filter_by(product_line_id=data["product_line_id"], name=data["name"], deleted=False).all():
            raise ValidationError(f'name has existed!')


class SubLineSchema(ma.ModelSchema):
    class Meta:
        sqla_session = db.session
        unknown = INCLUDE
        model = SubLine
        fields = ('id', 'name', 'product_line_id', 'product_line', 'platform')

    product_line = fields.Function(lambda obj: obj.product_line.name)


sub_line_schema = SubLineSchema()
