# -*- coding: utf-8 -*-
# @Time    : 2020-08-03
# @Author  : GongXun

import os
import socket
from datetime import timedelta


def host_ip():
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        if s:
            s.close()
    return ip


RedisPass = '1234567890'

SUITE_LIMIT_PATTERN = os.environ.get(
    "APP_SUITE_LIMIT_PATTERN", "10/day;5/hour")
SUITERETRY_LIMIT_PATTERN = os.environ.get(
    "APP_SUITE_LIMIT_PATTERN", "20/day;10/hour")
CASE_LIMIT_PATTERN = os.environ.get("APP_CASE_LIMIT_PATTERN", "1/minute")
UES_LIMIT_PATTERN = os.environ.get("APP_UES_LIMIT_PATTERN", "1/minute")
GIT_LIMIT_PATTERN = os.environ.get("APP_GIT_LIMIT_PATTERN", "1/minute")
# VENUS_LIMITS = [
#     "20000 per day",
#     "5000 per hour"
# ]


class Config(object):
    """Base config, uses staging database server."""

    # DB
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 100,
        "max_overflow": 20,
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "pool_use_lifo": True,
        "connect_args": {
            "keepalives": 1,
            "keepalives_idle": 10,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
    }
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_POOL_SIZE = 200
    SQLALCHEMY_MAX_OVERFLOW = 40

    # files
    SCRIPT_FOLDER = "scripts/"
    PIP_FOLDER = "pip/"
    PRODUCT_FOLDER = "products/"
    LOG_FOLDER = "logs/"
    SUITE_LOG_FOLDER = "instance/logs/suite/"
    TMP_FOLDER = "/var/tmp/"  # os.path.join(os.getcwd(), 'tmp')
    PIC_SUB_FOLDER = "superStar/people/"
    PIC_FOLDER = "logs/superStar/people/"
    FILE_SUB_FOLDER = "files/"
    FILE_FOLDER = "logs/files/"
    APP_LOG_FOLDER = ''

    SCHEDULER_EXECUTORS = {
        'default': {'type': 'threadpool', 'max_workers': 1}
    }

    SCHEDULER_JOB_DEFAULTS = {
        'coalesce': False,
        'max_instances': 1
    }
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = 'Asia/Shanghai'

    REDIS = {
        "URL_FOR_WEBSERVER": f'redis://:{RedisPass}@redis:6379/0',
        "URL_FOR_RESULT": f'redis://:{RedisPass}@redis:6379/1',
        "URL_FOR_TASK": f'redis://:{RedisPass}@redis:6379/2',
        "RQ_REDIS_URL": f'redis://:{RedisPass}@redis:6379/3',
        "URL_FOR_XFILE": f'redis://:{RedisPass}@redis:6379/4',
        "URL_FOR_PRODUCTLINES": f'redis://:{RedisPass}@redis:6379/5',
        "URL_FOR_GIT": f'redis://:{RedisPass}@redis:6379/6',
        "URL_FOR_WORKER": f'redis://:{RedisPass}@redis:6379/7',
        "URL_FOR_WORKER_CAPACITY": f'redis://:{RedisPass}@redis:6379/8',
        "URL_FOR_UE": f'redis://:{RedisPass}@redis:6379/9',
        "URL_FOR_POSTWOMEN_TASK": f'redis://:{RedisPass}@redis:6379/11',
        "URL_FOR_DEPENDENCY": f'redis://:{RedisPass}@redis:6379/12'
    }

    MONGO = {
        'URI': 'mongodb://kobe:kobe@10.105.39.242:27017',
        'PORT': 27017,
        'COLLECTION': f'statistics-{os.environ.get("ENV_CONFIG", "test")}'
    }

    MAIL_HOST = "http://qa.sz.shopee.io:8010"
    MAIL_SERVER = f"{MAIL_HOST}/v1/syncmails"
    MATTERMOST_SERVER = f"{MAIL_HOST}/v1/mattermost"
    SEATALK_SERVER = f"{MAIL_HOST}/v1/seatalk"
    SERVER_IP = '0.0.0.0'
    SERVER_PORT = 5001

    SEND_FILE_MAX_AGE_DEFAULT = timedelta(seconds=1)
    # MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # qabot noti url
    QABOT_NOTI = 'http://10.105.36.254:6001/openapi/noti'

    # cap
    CAP_URL = "http://10.105.39.39:8009"
    CAP_PRODUCTLINE_URL = f"{CAP_URL}/api/productline"
    CAP_MEMBERS_URL = f"{CAP_URL}/api/user_info?department_id="
    CAP_DEPARTMENT_URL = f"{CAP_URL}/api/departments"
    CAP_MEMBER_INFO_URL = f"{CAP_URL}/api/user_info?user_email="

    STF_HOST = 'http://10.105.39.189:8804'
    STF_DEVICES = '/api/v1/devices?present=true'
    STF_HEADERS = {
        "Content-Type": "application/json"
    }
    STF_USER_DEVICE = '/api/v1/user/devices'
    STF_SIGNAL_DEVICE = '/api/v1/device'

    LINK_AUTO_CASE = '/api/v1/linkAuto'
    CASE_MANAGEMENT_CALL_BACK = '/api/v1/caseexecutes/'

    AUTOMATION_TOKEN = 'x8FpqZOCzaTnXh8sunNG5pml1gL9b2yxbV9E5iPv'

    # goc
    GOC_INSTANCE = '/api/instance'
    GOC_CLEAR = '/api/clear'
    GOC_PROFILE = '/api/profile'
    GOC_UNLOCK = '/api/unlock'
    GOC_CHECK = '/api/check'
    GOC_UPDATE = '/api/update'

    # auth server
    AUTH_URL = "http://login.qa.sz.shopee.io:8805/api/refresh_token"
    # AUTH_URL = "http://qa.sz.shopee.io:8805/api/refresh_token"
    AUTH_HEADERS = {
        "Content-Type": "application/json"
    }

    # api that won't do auth action
    WHITE_LIST_API = ("/api/cases/many", '/api/elements', '/api/caseresults', '/api/devices',
                      '/api/statistic', '/api/spexupdate', '/api/hc_plan_result/',
                      '/api/spexapi/', '/api/pics', '/api/files', '/api/projects/update',
                      "/suite_run_for_webhook", "/scpdata", "/tcmdata", "/deploy", "/jira")

    # pb file storage path
    PB_DIR = 'spex_pb/'

    SPCLI_USER = 'kobe'
    SPCLI_PSD = 'Kobe_491100'
    SPACE_AUTH_URL = 'https://space.shopee.io/v1/sessions'

    HC_PATH = 'health_check/'
    SPEX_API_SCHEDULE_FAIL_NOTI = [
        "jiaxin.chen@shopee.com", "xun.gong@shopee.com"]
    SPEX_API_UPDATE_NOTI = ['xun.gong@shopee.com']

    POSTWOMEN_LOG = 'logs/postwomen/'

    TOPO_MAP = {
        "TopoAndroid": "app",
        "TopoIos": "app",
        "TopoAndroidIos": "app",
        "TopoIosAndroid": "app",
        "TopoTwoAndroid": "app",
        "TopoTwoIos": "app",
        "TopoMobile": "app",
        "TopoTwoMobile": "app",
        "TopoWeb": "web",
        "TopoHttp": "api",
        "TopoSpex": "api",
    }

    DEPENDENCY_PATH = "/home/admin/instance/running_env"
    SZQA_DEPENDENCY = "szqa_pips"

    ADMIN = ['libo@shopee.com', 'xun.gong@shopee.com',
             'jiaxin.chen@shopee.com', 'chengbo.li@shopee.com', 'hongzhi.liu@shopee.com', 'hailong.huang@shopee.com']

    LOGS_PATH = '/home/admin/instance/logs/'
    SETUP_SCRIPT_PATH = '/home/admin/instance/goc_auto_deploy/'
    SETUP_LOG_PATH = f'{LOGS_PATH}/setup/'

    GIT_CREDENTIALS = '/root/.git-credentials'
    ORIGIN_GIT_CREDENTIALS = '/home/admin/dockerfiles/.git-credentials'


class ProductionConfig(Config):
    """Uses production database server."""
    DEBUG = True

    TOMCAT_HOST = 'http://10.105.38.68:8005/'
    WEB_HOST = 'http://10.105.38.68:8001/'
    FE_SUITERESULT = 'http://venus.qa.sz.shopee.io/result/planresult/'

    REDIS_HOST = "10.105.38.68"
    REDIS_PORT = 8004
    RQ_DASHBOARD_REDIS_URL = f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/3'
    RQ_REDIS_URL = f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/3'
    REDIS = {
        "URL_FOR_WEBSERVER": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/0',
        "URL_FOR_RESULT": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/1',
        "URL_FOR_TASK": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/2',
        "RQ_REDIS_URL": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/3',
        "URL_FOR_XFILE": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/4',
        "URL_FOR_PRODUCTLINES": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/5',
        "URL_FOR_GIT": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/6',
        "URL_FOR_WORKER": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/7',
        "URL_FOR_WORKER_CAPACITY": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/8',
        "URL_FOR_UE": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/9',
        "URL_FOR_POSTWOMEN_TASK": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/11',
        "URL_FOR_LIMITER": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/12',
        "URL_FOR_DEPENDENCY": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/13'
    }

    MQ_INFO = {
        'MQ_USER': 'kobe',
        'MQ_PASSWORD': 'kobe',
        'MQ_HOST': '10.105.39.242',
        'MQ_PORT': 5672,
        'MQ_VHOST': 'vhost'
    }
    GOC_HOST = 'http://10.105.39.173:7778'
    RECORD_HOST = 'http://10.105.39.242:18001/api/records'

    # case management url
    CASEMANAGE_URL = 'http://ceres.qa.sz.shopee.io:9002'

    URL_FOR_RESULT = f'redis://:{RedisPass}@10.105.39.242:6379/15'
    SCP_HOST = 'scp.epd.i.shopee.io'
    # SCP_PROXY = 'vm2.epd.i.test.shopee.io'
    SCP_PROXY = 'scp.epd.i.shopee.io'

    HOST_SPACE = "https://space.shopee.io"
    HOST_SEE = "https://see.shopee.io/apis/see"
    USERNAME = "kobe"
    PASSWORD = "Kobe_491100"
    # HOST_SPACE = "https://space.test.shopee.io"
    # HOST_SEE = "https://see.test.shopee.io"
    # USERNAME = "szqabot"
    # PASSWORD = "Space123456"


class DevelopmentConfig(Config):
    DEBUG = True

    TOMCAT_HOST = 'http://10.12.78.89:8005/'
    WEB_HOST = 'http://10.12.78.89:8001/'
    FE_SUITERESULT = 'http://10.12.78.89:9999/result/planresult/'

    REDIS_HOST = "redis"
    REDIS_PORT = 6379
    RQ_DASHBOARD_REDIS_URL = f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/3'
    RQ_REDIS_URL = f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/3'
    REDIS = {
        "URL_FOR_WEBSERVER": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/0',
        "URL_FOR_RESULT": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/1',
        "URL_FOR_TASK": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/2',
        "RQ_REDIS_URL": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/3',
        "URL_FOR_XFILE": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/4',
        "URL_FOR_PRODUCTLINES": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/5',
        "URL_FOR_GIT": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/6',
        "URL_FOR_WORKER": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/7',
        "URL_FOR_WORKER_CAPACITY": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/8',
        "URL_FOR_UE": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/9',
        "URL_FOR_POSTWOMEN_TASK": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/11',
        "URL_FOR_LIMITER": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/12',
        "URL_FOR_DEPENDENCY": f'redis://:{RedisPass}@{REDIS_HOST}:{REDIS_PORT}/13'
    }

    MQ_INFO = {
        'MQ_USER': 'kobe',
        'MQ_PASSWORD': 'kobe',
        'MQ_HOST': '10.12.78.89',
        'MQ_PORT': 5672,
        'MQ_VHOST': 'vhost'
    }
    GOC_HOST = 'http://10.12.78.89:7778'
    RECORD_HOST = 'http://10.12.78.89:18001/api/records'

    # case management url
    CASEMANAGE_URL = 'http://10.143.251.94:9002'

    URL_FOR_RESULT = f'redis://:{RedisPass}@10.12.78.89:6379/15'
    SCP_HOST = 'scp.epd.i.test.shopee.io'
    SCP_PROXY = 'scp.epd.i.test.shopee.io'

    HOST_SPACE = "https://space.test.shopee.io"
    HOST_SEE = "https://see.test.shopee.io"
    USERNAME = "szqabot"
    PASSWORD = "Space123456"


def build_env(kwargs):

    return {

        "SQLALCHEMY_DATABASE_URI": f"postgresql://{kwargs['user']}:{kwargs['passwd']}@{kwargs['ip']}:{kwargs['port']}/{kwargs['db']}"

    }


def get_config():
    env = os.environ.get("ENV_CONFIG", "")
    if env == "live":
        conf = ProductionConfig
    else:
        conf = DevelopmentConfig

    return conf
