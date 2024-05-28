# -*- coding: utf-8 -*-
# @Time    : 2020/8/4
# @Author  : Arrow

from .mixins import TimestampMixin


class CommonCheck(TimestampMixin):

    def put_check(self, data):
        super().put_check(data)

    @classmethod
    def post_check(cls, data):
        super().post_check(data)
