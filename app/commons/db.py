# -*- coding: utf-8 -*-
# @Time    : 2020-08-03
# @Author  : GongXun

from contextlib import contextmanager
from flask_sqlalchemy import SQLAlchemy as BaseSQLAlchemy


class SQLAlchemy(BaseSQLAlchemy):

    @contextmanager
    def auto_commit_db(self):
        try:
            yield
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e

    # session = init_session()
    # try:
    #     ...  # business logic with other calls and raise-s
    #     session.commit()  # optional
    # finally:
    #     session.close()


db = SQLAlchemy()
