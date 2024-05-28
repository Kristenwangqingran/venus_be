# -*- coding: utf-8 -*-
# @Time    : 2020/09/23
# @Author  : GongXun


import os
import io
import random
import uuid
import urllib.parse
from flask import request, current_app, send_file, url_for
from flask.helpers import send_file
from werkzeug.utils import secure_filename
from app.commons import db, ma, resp_return
from app.models import Project, Case, Group
from app.resources import BaseResource
import marshmallow

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png',
                      'jpg', 'jpeg', 'gif', 'csv', 'json', 'har', 'webp', 'xml', 'html', 'xlsx', 'word'}

PIC_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_pic(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in PIC_EXTENSIONS


class RequestArgs(ma.Schema):
    file = ma.String(required=True)


class FilesView(BaseResource):

    def get(self, id):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', f'{str(err.args)}')

        try:
            project = Project.query.get(id)
            full_filename = os.path.join(
                project.get_product_path(), query_args['file'])

            if os.path.isfile(full_filename):
                return send_file(full_filename, as_attachment=True)
            else:
                current_app.logger.error(f"{full_filename} not found!")
                return resp_return('FILE_MISSING', new_msg=f"file: {query_args['file']} not found!")

        except Exception as err:
            return resp_return('COMMON_ERROR', str(err))

    def post_check(self, value):
        errors = []
        if "project_id" in value and Project.query.filter(Project.id == value["project_id"]).count() == 1:
            pass
        else:
            errors.append(f"project_id not found!")

        if errors:
            raise marshmallow.ValidationError(errors)

    def post(self, id):
        try:
            if 'file' in request.files and request.files['file'].filename:
                file = request.files['file']

                if allowed_file(file.filename):
                    project = Project.query.get(id)
                    filepath = project.get_product_path()

                    filename = secure_filename(file.filename)
                    full_filename = os.path.join(filepath, filename)

                    if not os.path.exists(filepath):
                        os.makedirs(filepath, exist_ok=True)
                    file.save(full_filename)

                    return resp_return('CREATE_SUCCESS', [{
                        "name": filename,
                        "url": url_for('file_blueprint.files', id=id).rstrip(
                            os.path.sep) + '?' + urllib.parse.urlencode({"name": filename}),
                        "filePath": full_filename
                    }])
                else:
                    return resp_return('FILE_NOT_ALLOWED')

            else:
                return resp_return('FILE_MISSING')

        except Exception as err:
            return resp_return('COMMON_ERROR', str(err))


class FilelistView(BaseResource):

    def walkdir(self, dst_dir, recurse=False):
        file_list = []
        if not os.path.exists(dst_dir):
            return file_list

        all_things = os.listdir(dst_dir)
        for item in all_things:
            if os.path.isfile(os.path.join(
                    dst_dir,
                    os.path.basename(item))) and not item.startswith('.'):
                file_list.append(
                    {
                        "dir": False,
                        "name": item
                    }
                )
            elif os.path.isdir(os.path.join(dst_dir, item)):
                if recurse:
                    file_list += self.walkdir(
                        os.path.join(dst_dir, os.path.basename(item)), recurse)
                else:
                    file_list.append(
                        {
                            "dir": True,
                            "name": item
                        }
                    )
            else:
                continue
        return file_list

    def get(self, id):
        try:
            project = Project.query.get(id)
            dst_dir = project.get_product_path()

            result = self.walkdir(dst_dir)

            return resp_return('QUERY_SUCCESS', result, len(result))

        except Exception as err:
            return resp_return('COMMON_ERROR', str(err))


class CaseFilesView(BaseResource):

    def post(self, id):
        try:
            if 'file' in request.files and request.files['file'].filename:
                file = request.files['file']
                if not file.filename.endswith('.csv'):
                    raise Exception(
                        'Only support .csv file as case parameter file.')
                case = Case.query.get(id)
                if not case:
                    raise Exception('Could not find case in db.')

                project = Project.query.get(case.project_id)
                group = Group.query.get(case.group_id)
                project_path = project.get_product_path()
                filepath = os.path.join(
                    project_path, 'case_data', group.name, case.name)

                filename = secure_filename(file.filename)
                full_filename = os.path.join(filepath, filename)

                if not os.path.exists(filepath):
                    os.makedirs(filepath, exist_ok=True)
                file.save(full_filename)

                with io.open(full_filename, 'r+', encoding='utf-8') as f:
                    header = f.readline()
                    cols = header.strip(os.path.sep).split(',')
                    params = '-'.join(map(lambda x: x.strip(), cols))

                return resp_return('CREATE_SUCCESS', [{
                    "name": filename,
                    "url": url_for('file_blueprint.casefiles', id=id).rstrip(os.path.sep) + '?' +
                    urllib.parse.urlencode({"name": filename}),
                    "filePath": full_filename,
                    "params": params
                }])
            else:
                return resp_return('FILE_MISSING')

        except Exception as err:
            return resp_return('COMMON_ERROR', str(err))


class PicsView(BaseResource):

    def post(self,):
        try:
            if 'file' in request.files and request.files['file'].filename:
                file = request.files['file']

                if allowed_file(file.filename):
                    filename = f"{uuid.uuid4().hex}-{file.filename}"
                    if is_pic(file.filename):
                        filepath = os.path.join(current_app.instance_path,
                                                current_app.config['PIC_FOLDER'])
                        dest_url = os.path.join(
                            current_app.config['TOMCAT_HOST'], current_app.config['PIC_SUB_FOLDER'], filename)
                    else:
                        filepath = os.path.join(current_app.instance_path,
                                                current_app.config['FILE_FOLDER'])
                        dest_url = os.path.join(
                            current_app.config['TOMCAT_HOST'], current_app.config['FILE_SUB_FOLDER'], filename)

                    full_filename = os.path.join(
                        filepath, filename)

                    if not os.path.exists(filepath):
                        os.makedirs(filepath, exist_ok=True)
                    file.save(full_filename)

                    return resp_return('CREATE_SUCCESS', [{
                        "name": filename,
                        "url": dest_url,
                        "filePath": full_filename
                    }])
                else:
                    return resp_return('FILE_NOT_ALLOWED')

            else:
                return resp_return('FILE_MISSING')

        except Exception as err:
            return resp_return('COMMON_ERROR', str(err))
