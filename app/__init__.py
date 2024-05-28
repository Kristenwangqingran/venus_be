# -*- coding: utf-8 -*-
# @Time    : 2020-08-03
# @Author  : GongXun

import requests
import traceback
import rq_dashboard
from flask import Flask, request, abort, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_cors import CORS
from app.commons import (
    DevelopmentConfig, ProductionConfig, build_env, db, CLI, init_aps, myrq, request_record,
    init_logger, resp_return, RETURN, MyRedis, get_config)
# from celery import Celery
import os
import json

# import sentry_sdk
# from sentry_sdk.integrations.flask import FlaskIntegration

# sentry_sdk.init(
#     dsn="http://777fbc28b6104af79d719704e8898ea4@10.12.184.187:9000/2",
#     integrations=[FlaskIntegration()]
# )
CONF = get_config()

# default_limits=con.VENUS_LIMITS,
limiter = Limiter(key_func=get_remote_address,
                  storage_uri=CONF.REDIS["URL_FOR_LIMITER"])


def create_app(cfg="test", withasp=False):
    # global celery
    app = Flask(__name__, instance_relative_config=True)
    os.environ["instance_path"] = app.instance_path
    if cfg == "test":
        config = DevelopmentConfig
        config_file = "config_test.json"
    else:
        config = ProductionConfig
        config_file = "config_live.json"

    app.config.from_object(config)
    with open(config_file) as f:
        path_config = json.load(f)
        app.config.from_mapping(build_env(path_config["postgres"]))
        app.config.from_mapping(path_config)

    # set log
    init_logger(app)
    app.logger.info(f"ENV: {cfg}")

    # xxx
    app.register_blueprint(rq_dashboard.blueprint, url_prefix="/rq")
    myrq.init_app(app)

    # set secret key for authorization
    app.secret_key = os.urandom(24)

    # Register DB, migrate, marshmallow.
    db.init_app(app)
    Migrate(app, db)
    CORS(app, resources=r'/*', supports_credentials=True, allow_headers="*")

    # MongoDB
    # mongo = PyMongo(app)
    # user_activity_collection = mongo.db[app.config["MONGO_USERACTIVITY_COLLECTION"]]

    # celery = Celery(app.import_name, broker=config.broker_url,
    #                 backend=config.result_backend)
    # init_celery(app=app, celery=celery)

    from app import models, resources
    # Register cli CMD,
    CLI.init_app(app)

    @app.shell_context_processor
    def make_shell_context():
        return dict(app=app, db=db, models=models, myrq=myrq)

    # Register scheduler
    if withasp and os.environ.get("APS_CONFIG", False) in [True, "true"] and cfg in ("live", 'test'):
        # pass
        app.logger.info(f"APS_CONFIG: {os.environ['APS_CONFIG']}")
        init_aps(app, models.Casesuite, env=cfg)

    # Register API
    app.register_blueprint(resources.project_blueprint, url_prefix="/api")
    app.register_blueprint(resources.env_blueprint, url_prefix="/api")
    app.register_blueprint(resources.case_blueprint, url_prefix="/api")
    app.register_blueprint(resources.casesuite_blueprint, url_prefix="/api")
    app.register_blueprint(resources.caseresult_blueprint, url_prefix="/api")
    app.register_blueprint(resources.group_blueprint, url_prefix="/api")
    app.register_blueprint(resources.suiteresult_blueprint, url_prefix="/api")
    app.register_blueprint(resources.task_blueprint, url_prefix="/api")
    app.register_blueprint(resources.worker_blueprint, url_prefix="/api")
    app.register_blueprint(resources.file_blueprint, url_prefix="/api")
    app.register_blueprint(resources.others_blueprint, url_prefix="/api")
    app.register_blueprint(resources.attachment_blueprint, url_prefix="/api")
    app.register_blueprint(resources.page_blueprint, url_prefix="/api")
    app.register_blueprint(resources.element_blueprint, url_prefix="/api")
    app.register_blueprint(resources.goc_blueprint, url_prefix="/api")
    app.register_blueprint(resources.product_blueprint, url_prefix="/api")
    app.register_blueprint(resources.spex_blueprint, url_prefix="/api")
    app.register_blueprint(resources.hc_template_blueprint, url_prefix="/api")
    app.register_blueprint(resources.hc_plan_blueprint, url_prefix="/api")
    app.register_blueprint(
        resources.hc_plan_result_blueprint, url_prefix="/api")
    app.register_blueprint(resources.hc_task_blueprint, url_prefix="/api")
    app.register_blueprint(resources.aps_blueprint, url_prefix="/api")
    app.register_blueprint(resources.postwomen_blueprint, url_prefix="/api")
    app.register_blueprint(
        resources.postwomen_template_blueprint, url_prefix="/api")
    app.register_blueprint(resources.http_blueprint, url_prefix="/api")
    app.register_blueprint(resources.dependency_blueprint, url_prefix="/api")
    app.register_blueprint(resources.member_blueprint, url_prefix="/api")

    limiter.init_app(app)

    @app.route('/test')
    def hello_world():
        return 'Hello World'

    @app.route('/debug-sentry')
    def trigger_error():
        division_by_zero = 1 / 0

    def _get_body(request):
        body = None
        if request.method in ["PUT", "POST"]:
            try:
                body = request.json
            except Exception as err:
                body = {"exception": str(err)}
        elif request.method in ["DELETE", "GET"]:
            body = {}
        return body

    def _auth(request):
        ok, msg, status_code = True, "", 401

        if [item for item in app.config['WHITE_LIST_API'] if item in request.path]:
            msg = f"method: {request.method}, path: {request.path} in whitelist, skip token checking!"
            g.user = request.headers.get('email', "nobody")

        elif request.method in ["PUT", "POST", "DELETE"]:
            body = _get_body(request)
            if request.headers.get('token', None):
                token = request.headers.get('token')
                try:
                    r = requests.get(
                        app.config['AUTH_URL'], headers=app.config['AUTH_HEADERS'],
                        params={"sso_c": token, "platform": 5}, timeout=2)
                    if r.status_code in (200,):
                        g.token = token
                        auth_info = r.json()
                        if auth_info.get('email'):
                            if auth_info['email'] != request.headers.get('email', None):
                                ok = False
                                msg = f"user auth fail: email and token auth user not match!"
                                status_code = 403
                            else:
                                g.user = auth_info['email']
                                msg = f"user: {auth_info['email']} authed!"

                                # insert record to record server
                                record = {
                                    "service": "automation",
                                    "user": auth_info['email'],
                                    "path": request.path,
                                    "method": request.method,
                                    "data": body if body is not None else {}
                                }
                                request_record.send(app, **record)
                        else:
                            ok = False
                            msg = f"token auth fail: {token} invalid! auth info: {auth_info}"
                            status_code = 403

                    else:
                        ok = False
                        msg = f"auth server crash: status code {r.status_code} for token {token}"
                        status_code = 500

                except Exception:
                    ok = False
                    msg = f"auth get exception: {traceback.format_exc()}"
                    status_code = 500

            else:
                ok = False
                msg = f"token missing for method: {request.method}, path: {request.path}, args: {dict(request.args)}, body: {body}"
                status_code = 401
        else:
            msg = f"method: {request.method}, path: {request.path}, skip token checking!"

        return ok, msg, status_code

    @app.before_request
    def before_request():
        if cfg in ("test",):
            body = _get_body(request)
            if body is not None:
                app.logger.info(
                    f"method: {request.method}, path: {request.path}, args: {dict(request.args)}, body: {body}")

        ok, msg, status_code = _auth(request)
        if not ok:
            app.logger.error(msg)
            if cfg in ("test",):
                pass
            else:
                abort(status_code)
        else:
            pass
            # app.logger.info(msg)

    return app
