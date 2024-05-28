# -*- coding: utf-8 -*-
# @Time    : 2022/08/29
# @Author  : Chen Jiaxin

import requests
import traceback
from flask import current_app
from app.models import Member, ProductLine


class MemberMgr:
    def __init__(self, ):
        self.updated = {}

    def _get_old(self, ):
        for member in Member.query.filter_by(deleted=False).all():
            if member.platform == "cap":
                self.updated[member.email] = False

    def _delete_old(self, ):
        for email, updated in self.updated.items():
            if not updated:
                member = Member.query.filter_by(email=email, deleted=False).first()
                if member:
                    member.delete()

    @staticmethod
    def _get_department_ids_from_cap():
        r = requests.get(url=current_app.config["CAP_DEPARTMENT_URL"])
        r.raise_for_status()
        departments = r.json()["data"]["items"]
        ids = []
        for department in departments:
            ids.append(department["id"])
        return ids

    def _get_member_info_from_cap(self, ):
        data = {}
        try:
            department_ids = self._get_department_ids_from_cap()
            for department_id in department_ids:
                CAP_MEMBER_URL = f"{current_app.config['CAP_MEMBERS_URL']}{department_id}"
                r = requests.get(url=CAP_MEMBER_URL)
                r.raise_for_status()
                members = r.json()["data"]["items"]
                for member in members:
                    email = member.get("user_email")
                    m = Member.query.filter(Member.email == member.get("user_email"), Member.deleted == False).first()
                    data = {
                        "email": email,
                        "role": member.get("role", []),
                        "leader": member.get("leader", ""),
                        "product_lines": [p.id for p in
                                         [ProductLine.query.filter_by(_id=i).first()
                                          for i in member.get("line_ids", [])] if p],
                        "features": member.get("feature_ids", []),
                        "platform": "cap"
                    }
                    if m:
                        m.put_save(data)
                        self.updated[email] = True
                    else:
                        Member.post_check(data)
                        m = Member(**data)
                        m.save()

        except Exception:
            current_app.logger.error(f"Get data from cap error: {traceback.format_exc()}")

        return data

    def sync_member_from_cap(self, ):
        try:
            self._get_old()
            self._get_member_info_from_cap()
            self._delete_old()

        except Exception:
            current_app.logger.error(f"Sync member from cap error: {traceback.format_exc()}")


def sync_member():
    member_mgr = MemberMgr()
    member_mgr.sync_member_from_cap()
