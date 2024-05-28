# -*- coding: utf-8 -*-
# @Time    : 2022/08/29
# @Author  : Chen Jiaxin


import requests
import traceback
from flask import current_app
from app.models import Feature, ProductLine, SubLine


class ProductLineMgr:
    def __init__(self, ):
        self.updated = {
            "product_line": {},
            "sub_line": {},
            "feature": {}
        }

    def _get_old(self, ):
        for product_line in [p for p in ProductLine.query.all() if not p.deleted and p.platform and p.platform == 'cap']:
            self.updated["product_line"][product_line.id] = False
            for sub_line in [s for s in product_line.sub_lines if not s.deleted and s.platform and s.platform == 'cap']:
                self.updated["sub_line"][sub_line.id] = False
                for feature in [f for f in sub_line.features if not f.deleted and f.platform and f.platform == 'cap']:
                    self.updated["feature"][feature.id] = False

    def _update_product_line(self, product_line_id, info):
        try:
            p = ProductLine.query.filter_by(_id=product_line_id, deleted=False).first()
            if not p:
                data = {
                    "_id": product_line_id,
                    "name": info['name'],
                    "department": info['department'],
                    "platform": "cap"
                }
                ProductLine.post_check(data)
                p = ProductLine(**data)
                p.save()
            else:
                p.put_save({
                    "name": info['name'],
                    "department": info['department']
                })
                self.updated["product_line"][p.id] = True

            for sub_line_name, sub_line_info in info['sub_line'].items():
                self._update_feature(p.id, sub_line_name, sub_line_info)

        except Exception:
            current_app.logger.error(f"Update product line fail: {traceback.format_exc()}")

    def _update_feature(self, product_line_id, sub_line_name, info):
        try:
            sub_line = SubLine.query.filter_by(product_line_id=product_line_id, name=sub_line_name, deleted=False).first()
            if not sub_line:
                sub_line = SubLine(**{
                    "name": sub_line_name,
                    "product_line_id": product_line_id,
                    "platform": "cap"
                })
                sub_line.save()
            else:
                self.updated['sub_line'][sub_line.id] = True

            for feature_id, feature_name in info:
                feature = Feature.query.filter_by(id=feature_id, deleted=False).first()
                data = {
                    "name": feature_name,
                    "sub_line_id": sub_line.id,
                    "platform": "cap"
                }
                if not feature:
                    data['id'] = feature_id
                    feature = Feature(**data)
                    feature.save()
                else:
                    feature.put_save(data)
                    self.updated["feature"][feature_id] = True

        except Exception:
            current_app.logger.error(f"Update feature fail: {traceback.format_exc()}")

    @staticmethod
    def _get_data_from_cap():
        data = {}
        try:
            r = requests.get(url=current_app.config["CAP_PRODUCTLINE_URL"])
            r.raise_for_status()
            product_lines = r.json()["data"]["items"]

            for product_line in product_lines:
                product_line_id = product_line['product_line_id']
                if product_line_id not in data:
                    data[product_line_id] = {
                        "name": product_line['product_line'],
                        "department": product_line['department_name'],
                        "sub_line": {}
                    }

                sub_line = product_line['sub_line']
                if sub_line not in data[product_line_id]['sub_line']:
                    data[product_line_id]['sub_line'][sub_line] = []

                feature_id = product_line['id']
                feature = product_line['feature']
                if feature not in data[product_line_id]['sub_line'][sub_line]:
                    data[product_line_id]['sub_line'][sub_line].append([feature_id, feature])

        except Exception:
            current_app.logger.error(f"Get data from cap error: {traceback.format_exc()}")

        return data

    def _delete_old(self, ):
        for item, info in self.updated.items():
            model = ''.join(list(map(lambda x: x.capitalize(), item.split("_"))))
            query = getattr(eval(model), 'query')
            for item_id, updated in info.items():
                if not updated:
                    instance = query.get(item_id)
                    if instance:
                        instance.delete()

    def sync_product_line_from_cap(self, ):
        try:
            self._get_old()
            data = self._get_data_from_cap()
            for product_line_id, info in data.items():
                self._update_product_line(product_line_id, info)
            self._delete_old()

        except Exception:
            current_app.logger.error(f"Sync productline from cap error: {traceback.format_exc()}")


def sync_product_line():
    product_line_mgr = ProductLineMgr()
    product_line_mgr.sync_product_line_from_cap()
