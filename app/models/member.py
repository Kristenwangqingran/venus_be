# -*- coding: utf-8 -*-
# @Time    : 2022-08-15
# @Author  : peipei.cai

import copy
from app.commons import db, ma
from .mixins import TimestampMixin
from .common_check import CommonCheck
from marshmallow import fields, INCLUDE, ValidationError


class Member(CommonCheck, TimestampMixin, db.Model):
    __tablename__ = 'member'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    leader = db.Column(db.String(255), index=True)
    role = db.Column(db.ARRAY(db.String(255)))
    # example: venus, cap
    platform = db.Column(db.String(127), nullable=True)

    @classmethod
    def post_check(cls, data):
        from .product_line import ProductLine
        from .feature import Feature
        if cls.query.filter_by(email=data["email"], deleted=False).all():
            raise ValidationError(f'name has existed!')

        if data.get('product_lines'):
            product_line_ids = data.get('product_lines', [])
            product_line_instances = []
            for product_line_id in product_line_ids:
                p = ProductLine.query.get(product_line_id)
                if p:
                    product_line_instances.append(p)
                else:
                    raise ValidationError(f'Not found product line[id: {product_line_id}]')
            data['product_lines'] = product_line_instances

        if data.get('features'):
            feature_ids = data.get('features', [])
            product_line_instances = data.get('product_lines', [])
            product_line_ids = [p.id for p in data.get('product_lines', [])]
            feature_instances = []
            for feature_id in feature_ids:
                f = Feature.query.get(feature_id)
                if f:
                    feature_instances.append(f)
                    fp_id = f.sub_line.product_line.id
                    if fp_id not in product_line_ids:
                        product_line_instances.append(f.sub_line.product_line)
                        product_line_ids.append(fp_id)
                else:
                    raise ValidationError(f'Not found feature[id: {feature_id}]')
            data['features'] = feature_instances
            data['product_lines'] = product_line_instances

    def put_save(self, data):
        for k, v in data.items():
            if k in ('id', 'created_time', 'updated_time'):
                continue
            elif k in ('product_lines'):
                from .product_line import ProductLine
                product_line_instance = []
                for product_line_id in v:
                    p = ProductLine.query.get(product_line_id)
                    if p:
                        product_line_instance.append(p)
                self.product_lines = product_line_instance
            elif k in ('features'):
                from .feature import Feature
                feature_instances = []
                product_line_instances = self.product_lines
                product_line_ids = [p.id for p in self.product_lines]
                for feature_id in v:
                    f = Feature.query.get(feature_id)
                    if f:
                        feature_instances.append(f)
                        fp_id = f.sub_line.product_line.id
                        if fp_id not in product_line_ids:
                            product_line_instances.append(f.sub_line.product_line)
                            product_line_ids.append(fp_id)
                self.features = feature_instances
                self.product_lines = product_line_instances
            elif isinstance(v, (dict, list)):
                tmp_v = copy.deepcopy(v)
                setattr(self, k, tmp_v)
            else:
                setattr(self, k, v)
        self.save()


class MemberSchema(ma.ModelSchema):
    class Meta:
        sqla_session = db.session
        unknown = INCLUDE
        model = Member
        fields = ('id', 'email', 'leader', 'role', 'product_line_id', 'product_line', 'sub_line_id', 'sub_line',
                  'feature_id', 'feature', 'platform', 'department')

    product_line_id = fields.Function(lambda obj: [p.id for p in obj.product_lines])
    product_line = fields.Function(lambda obj: [p.name for p in obj.product_lines])
    sub_line_id = fields.Function(lambda obj: [f.sub_line.id for f in obj.features])
    sub_line = fields.Function(lambda obj: [f.sub_line.name for f in obj.features])
    feature_id = fields.Function(lambda obj: [f.id for f in obj.features])
    feature = fields.Function(lambda obj: [f.name for f in obj.features])
    department = fields.Method("get_department")

    def get_department(self, obj):
        d = [p.department for p in obj.product_lines]
        return d[0] if d else None


member_schema = MemberSchema()
