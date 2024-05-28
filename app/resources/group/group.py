# -*- coding: utf-8 -*-
# @Time    : 2020/8/10
# @Author  : Arrow

import traceback
from collections import defaultdict

from flask import request, current_app

import app.commons.utils as utils
from app.commons import ma, resp_return
from app.models import Group, group_schema, Project, Feature
from app.resources import BaseResource


class RequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    name = ma.String()
    project_id = ma.Integer()
    mum_id = ma.Integer()
    organized = ma.String()
    public_project = ma.Boolean(default=False)


class GroupsView(BaseResource):

    def __public_project(self):
        try:
            projects = Project.query.filter(
                Project.public_project == True, Project.deleted == False).all()
            public_projects = []
            feature_list = []
            for project in projects:
                if not project.feature_id:
                    continue
                feature = Feature.query.filter(
                    Feature.id == project.feature_id, Feature.deleted == False).first()
                if not feature:
                    continue
                if feature.id not in feature_list:
                    feature_list.append(feature.id)
                    feature_node = {
                        "title": feature.name,
                        "key": feature.id,
                        "type": "feature",
                        "children": []
                    }
                    public_projects.append(feature_node)
                else:
                    feature_node = public_projects[feature_list.index(
                        feature.id)]

                project_node = self.__format_project_node(project)
                feature_node["children"].append(project_node)

            return public_projects

        except Exception:
            current_app.logger.error(traceback.format_exc())
            return []

    def __form_public_projects(self, public_projects, feature_node, project_id_list):
        del_feature_index = None
        for index, feature_info in enumerate(public_projects):
            if feature_info["key"] == feature_node["key"]:
                del_feature_index = index
                for project_info in feature_info["children"]:
                    if project_info["key"] not in project_id_list:
                        feature_node["children"].append(project_info)
                break
        if del_feature_index is not None:
            public_projects.pop(del_feature_index)

        return public_projects

    def __format_group_node(self, project_id):
        all_groups = defaultdict(dict)
        groups = Group.query.filter(Group.project_id == project_id,
                                    Group.deleted == False).order_by(Group.updated_time.desc()).all()
        for group in groups:
            all_groups[(group.name, group.id)] = {
                "title": group.name,
                "key": group.id,
                "type": "group",
                "children": []
            }
        need_del = []
        for group in groups:
            if group.mum and group.mum.deleted == False:
                all_groups[(group.mum.name, group.mum.id)]["children"].append(
                    all_groups[(group.name, group.id)])
                need_del.append((group.name, group.id))

        for item in need_del:
            all_groups.pop(item)

        return all_groups

    def __format_project_node(self, project):
        project_node = {
            "title": project.name,
            "key": project.id,
            "type": "project",
            "children": []
        }
        all_groups = self.__format_group_node(project.id)
        project_node["children"].extend(list(all_groups.values()))

        return project_node

    def get(self, ):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        try:
            organized = query_args.pop("organized", None)
            public_project_flag = query_args.pop("public_project", None)
            project_id = query_args.get("project_id", None)
            project, feature = None, None
            if project_id:
                project = Project.query.filter(Project.id == project_id, Project.status == "active",
                                               Project.deleted == False).first()
                if project:
                    feature = Feature.query.filter(
                        Feature.id == project.feature_id, Feature.deleted == False).first()
            if project and feature:
                feature_node = {
                    "title": feature.name,
                    "key": feature.id,
                    "type": "feature",
                    "children": []
                }
            else:
                return resp_return('NOFOUND_ERROR')

            res = []
            project_id_list = []
            if organized == "1":
                res.append(feature_node)
                project_id_list.append(project.id)
                project_node = self.__format_project_node(project)
                feature_node["children"].append(project_node)
                if public_project_flag:
                    public_projects = self.__public_project()
                    public_projects = self.__form_public_projects(
                        public_projects, feature_node, project_id_list)
                    res.extend(public_projects)

                return resp_return('QUERY_SUCCESS', res, len(res))
            # add to support cross project
            elif organized == "2":
                sub_line = feature.sub_line
                for feature in sub_line.features:
                    if not feature.deleted:
                        feature_node = {
                            "title": feature.name,
                            "key": feature.id,
                            "type": "feature",
                            "children": []
                        }
                        projects = Project.query.filter(
                            Project.feature_id == feature.id, Project.deleted == False, Project.status == "active").all()
                        for project in projects:
                            project_id_list.append(project.id)
                            project_node = self.__format_project_node(project)
                            feature_node["children"].append(project_node)
                        res.append(feature_node)

                if public_project_flag:
                    public_projects = self.__public_project()
                    for feature_node in res:
                        public_projects = self.__form_public_projects(
                            public_projects, feature_node, project_id_list)

                    res.extend(public_projects)

                return resp_return('QUERY_SUCCESS', res, len(res))

            else:
                param = self.get_common_params(query_args, Group)
                groups = Group.query.filter(*param).order_by(Group.updated_time.desc()).paginate(
                    page=query_args["page"], per_page=query_args["per_page"], error_out=False)
                result = group_schema.dump(groups.items, many=True)
                return resp_return('QUERY_SUCCESS', result, groups.total)
        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))

    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        if not json_data:
            return resp_return('JSON_ERROR')

        try:
            Group.post_check(json_data)
            group = group_schema.load(utils.del_id_none(json_data))
            group.save()

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
        else:
            return resp_return('CREATE_SUCCESS', {"id": group.id})


class GroupView(BaseResource):
    def get(self, id):
        group = Group.query.filter_by(id=id).first()
        if group:
            result = group_schema.dump(group)

            return resp_return('QUERY_SUCCESS', result)
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding group found!")

    def put(self, id):
        json_data = request.get_json()
        if not json_data:
            return resp_return('JSON_ERROR')

        group = Group.query.filter_by(id=id).first()
        if group:
            try:
                self.common_put(group, json_data)

            except Exception as err:
                current_app.logger.error(traceback.format_exc())
                return resp_return('COMMON_ERROR', new_msg=str(err))
            else:
                return resp_return('UPDATE_SUCCESS', {"id": group.id})
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding group found!")

    def delete(self, id):
        group = Group.query.filter_by(id=id).first()
        if group:
            try:
                if group.children:
                    for child in group.children:
                        child.rdelete()
                group.rdelete()

            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding group found!")


class GroupINFOView(BaseResource):

    def _is_empty(self, group):

        if group:
            if group.cases:
                for case in group.cases:
                    if case.deleted == False:
                        return False

        if group.children:
            for child in group.children:
                if not self._is_empty(child):
                    return False

        return True

    def get(self, id):
        group = Group.query.filter_by(id=id).first()
        if group:
            empty = self._is_empty(group)
            return resp_return('QUERY_SUCCESS', {"empty": empty})
        else:
            return resp_return('NOFOUND_ERROR', new_msg="No corresponding group found!")
