# -*- coding: utf-8 -*-
# @Time    : 2020-08-03
# @Author  : GongXun

import sys
import os
from app import create_app
from app.commons import DevelopmentConfig, ProductionConfig


env = os.environ.get("ENV_CONFIG", "")
app = create_app(env, withasp=True)
port = os.getenv("PORT", 5001)


if __name__ == '__main__':
    app.logger.info("Start Running...")
    app.run(host='0.0.0.0', port=port)
