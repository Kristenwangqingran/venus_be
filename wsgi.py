# -*- coding: utf-8 -*-
# @Time    : 2020-09-25
# @Author  : GongXun


from gevent import monkey
monkey.patch_all()
import sys
from app.commons.config import ProductionConfig
import os

sys.setrecursionlimit(1000000)


# max_requests = 50000
# max_requests_jitter = 2
# timeout = 70
# graceful_timeout = 30
# limit_request_line = 8190
# limit_request_fields = 200
# limit_request_fields_size = 8190

# pidfile = "gunicorn.pid"
# # user = "admin"
# pythonpath = "/Users/admin/CODE/cmdb/"
# accesslog = "gunicorn_access.log"
# errorlog = "gunicorn_error.log"
# loglevel = 'debug'
# access_log_format = '%(h)s %(t)s %(l)s %(u)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
# daemon = False
# # daemon = True
# raw_env = "CONFIG_ENV=uat"
# capture_output = True
# work_class = "sync"


preload = False
timeout = 3600
bind = '{0}:{1}'.format(
    os.environ.get("SERVER_IP", ProductionConfig.SERVER_IP),
    os.environ.get("SERVER_PORT", ProductionConfig.SERVER_PORT))
workers = 1
worker_class = 'gevent'
x_forwarded_for_header = 'X-FORWARDED-FOR'
loglevel = 'debug'
