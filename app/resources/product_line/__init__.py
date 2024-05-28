# -*- coding: utf-8 -*-
# @Time    : 2021/06/02
# @Author  : minhao.zhang


from flask import Blueprint
from flask_restful import Api

from .product_line import ProductsView, ProductsSelectorView, ProductLineView, ProductLinesView, \
    SyncProductLineView, DepartmentView
from .sub_line import SubLineView, AddSubLineView, SubLinesView
from .feature import FeatureView, FeaturesView, AddFeatureView

product_blueprint = Blueprint('product_blueprint', __name__)

api = Api(app=product_blueprint)

api.add_resource(ProductLineView, '/product_line/<int:product_line_id>')
api.add_resource(ProductLinesView, '/product_lines')
api.add_resource(ProductsView, '/productlines')
api.add_resource(ProductsSelectorView, '/productlines/selector')
api.add_resource(SyncProductLineView, '/sync_product_line')

api.add_resource(DepartmentView, '/departments')

api.add_resource(SubLineView, '/sub_line/<int:sub_line_id>')
api.add_resource(AddSubLineView, '/sub_line')
api.add_resource(SubLinesView, '/sub_lines/<int:product_line_id>')

api.add_resource(FeatureView, '/feature/<int:feature_id>')
api.add_resource(FeaturesView, '/features/<int:sub_line_id>')
api.add_resource(AddFeatureView, '/feature')
