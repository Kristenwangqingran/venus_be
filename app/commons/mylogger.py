# -*- coding: utf-8 -*-
# @Time    : 2022-01-14
# @Author  : Jiaxin Chen

import os
import threading
import logging
from logging.handlers import RotatingFileHandler
from flask import current_app


FMT = '[%(asctime)s %(levelname)s %(filename)s %(funcName)s %(lineno)s] %(message)s'


class ColorFormatter(logging.Formatter):
    """
    Log printing with colour
    """
    log_colors = {
        'CRITICAL': '\033[1;31m',  # light red
        'ERROR': '\033[0;31m',  # red
        'WARNING': '\033[1;33m',  # yellow
        'INFO': '\033[0m',  # none
        'DEBUG': '\033[0;32m',  # green
    }

    def format(self, record):
        s = super().format(record)

        level_name = record.levelname
        if level_name in self.log_colors:
            return self.log_colors[level_name] + s + '\033[0m'
        return s


class RunLogger(object):
    _instance_lock = threading.Lock()
    _instance = {}
    _handler = None

    def __new__(cls, exec_id, *args, **kw):
        exec_id = str(exec_id)
        if exec_id not in RunLogger._instance.keys():
            with RunLogger._instance_lock:
                if exec_id not in RunLogger._instance.keys():
                    RunLogger._instance[exec_id] = super().__new__(cls)
        return RunLogger._instance[exec_id]

    def __init__(self, exec_id, log_dir):
        self.log_dir = log_dir
        self.exec_id = str(exec_id)

        self._create()

    def filter(self, record):
        if record.msg.startswith(f"[{self.exec_id}]"):
            return True
        return False

    def _create(self):
        if not os.path.exists(self.log_dir):
            os.mkdir(self.log_dir)
        log_path = os.path.join(self.log_dir, f'{self.exec_id}.log')

        if not self._handler:
            logging_filter = logging.Filter()
            logging_filter.filter = self.filter

            handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=100 * 1024 * 1024, encoding='UTF-8')
            formatter = logging.Formatter(FMT)
            handler.setFormatter(formatter)
            handler.addFilter(logging_filter)
            self._handler = handler
            current_app.logger.addHandler(handler)

    def release(self):
        if self._handler:
            current_app.logger.removeHandler(self._handler)


def init_logger(app):
    app.logger = logging.getLogger('gunicorn.access')
    app.logger.setLevel(logging.DEBUG)
    logger = app.logger
    default_handler = logger.handlers[0] if logger.handlers else logging.StreamHandler()
    logger.handlers = []
    # logging_level = logging.INFO
    # logger.setLevel(logging_level)
    fmt = logging.Formatter(FMT)
    fmt_color = ColorFormatter(FMT)
    default_handler.setFormatter(fmt_color)
    logger.addHandler(default_handler)

    fh = logging.handlers.RotatingFileHandler(
        os.path.join(app.instance_path, app.config['APP_LOG_FOLDER'], 'app.log'), maxBytes=100 * 1024 * 1024,
        backupCount=7, encoding='UTF-8')
    fh.setFormatter(fmt)
    logging_filter = logging.Filter()
    logging_filter.filter = lambda record: isinstance(
        record.msg, str) and not record.msg.startswith("[")
    fh.addFilter(logging_filter)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    # sh = logging.StreamHandler()
    # sh.setFormatter(fmt)
    # logger.addHandler(sh)


class MyLogger:

    def _convert_level(self, level):
        if getattr(logging, level.upper(), None):
            return getattr(logging, level.upper())
        else:
            return logging.INFO

    def __init__(self, name, level='info', path=None):
        logger = logging.getLogger(name)
        logger.setLevel(self._convert_level(level))

        fmt = logging.Formatter(FMT)
        fmt_color = ColorFormatter(FMT)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt_color)
        logger.addHandler(sh)

        if path:
            fh = RotatingFileHandler(
                path, maxBytes=10*1024*1024, backupCount=7, encoding='UTF-8')
            fh.setFormatter(fmt)
            logger.addHandler(fh)

        self.logger = logger

    def __getattr__(self, name):
        return getattr(self.__dict__['logger'], name)


if __name__ == '__main__':
    l = MyLogger("test1")
    l.info('123')
    l.warning('123')

    l2 = MyLogger('test2', 'debug', 'log/print.log')
    l2.info('456')
    l2.warning('456')
