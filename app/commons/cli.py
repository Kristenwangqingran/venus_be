# -*- coding: utf-8 -*-
# @Time    : 2020-08-03
# @Author  : GongXun

from flask import current_app, g
from flask.cli import AppGroup, with_appcontext
from app.commons.db import db

db_cli = AppGroup('db_helper', help="Database create, drop, recreate.")


class CLI:
    @staticmethod
    def init_app(app):
        app.cli.add_command(db_cli)


@db_cli.command('create')
def create():
    """Creates the database."""
    db.create_all()


@db_cli.command('drop')
def drop():
    """Drops the database"""
    db.drop_all()


@db_cli.command('recreate')
def recreate():
    """Running drop_db() and create_db()."""
    db.drop_all()
    db.create_all()
