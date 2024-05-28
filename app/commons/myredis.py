# -*- coding: utf-8 -*-
# @Time    : 2020-09-08
# @Author  : GongXun

import time
import traceback
from flask import current_app
from redis import StrictRedis, ConnectionPool


class MyRedis:
    def __init__(self, config):
        self.config = config
        self.hd = StrictRedis(connection_pool=ConnectionPool.from_url(config))

    def conn_retry(self, function):
        def _wrapper(*args, **kwargs):
            while True:
                try:
                    ret = function(*args, **kwargs)
                    return ret
                except Exception:
                    current_app.logger.error(f"Redis timeout, tr-connect...{traceback.format_exc()}")
                    time.sleep(2)
                    self._reset_conn()
        return _wrapper

    def _reset_conn(self, ):
        self.hd.connection_pool.disconnect()
        self.hd = StrictRedis(connection_pool=ConnectionPool.from_url(self.config))

    def get(self, k):
        return self.conn_retry(self.hd.get)(k)

    def set(self, k, v, **params):
        return self.conn_retry(self.hd.set)(k, v, **params)

    def delete(self, k):
        return self.conn_retry(self.hd.delete)(k)

    def exists(self, k):
        return self.conn_retry(self.hd.exists)(k)

    def keys(self, ):
        return self.conn_retry(self.hd.keys)()

    def disconnect(self, ):
        try:
            self.hd.connection_pool.disconnect()
        except Exception:
            current_app.logger.error(f"Disconnect error: {traceback.format_exc()}")
