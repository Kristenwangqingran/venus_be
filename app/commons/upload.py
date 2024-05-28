# -*- coding: utf-8 -*-
# @Time    : 2020-09-23
# @Author  : GongXun


from flask_uploads import UploadSet, patch_request_class, configure_uploads
from flask import current_app


uploads = None


def init_upload(app):
    global uploads

    uploads = UploadSet('files', default_dest=lambda app: app.instance_path)

    configure_uploads(app, uploads)
    patch_request_class(app, size=10 * 1024 * 1024)
