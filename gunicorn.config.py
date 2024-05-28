# -*- coding: utf-8 -*-
# @Time    : 2022/6/9
# @Author  : Jiaxin Chen

import os
from gevent import monkey
monkey.patch_all()

port = os.getenv("PORT", 5001)

loglevel = "debug"
accesslog = '-'
errorlog = '-'

workers = 1
worker_class = "gevent"
bind = f"0.0.0.0:{port}"

preload = False
timeout = 3600
x_forwarded_for_header = 'X-FORWARDED-FOR'

logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': True,
    'loggers': {
        "gunicorn.error": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": 1,
            "qualname": "gunicorn.error"
        },

        "gunicorn.access": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": 0,
            "qualname": "gunicorn.access"
        }
    },
    'handlers': {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "generic",
            "level": "DEBUG",
            "stream": 'ext://sys.stdout'
        }
    },
    'formatters': {
        "generic": {
            "format": "[%(asctime)s %(levelname)s %(filename)s %(module)s %(funcName)s %(lineno)s] %(message)s",
            "class": "logging.Formatter"
        }
    }
}
