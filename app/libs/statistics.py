# -*- coding: utf-8 -*-
# @Time    : 2022/3/17
# @Author  : Jiaxin Chen


import requests
import calendar
import datetime
import traceback
from flask import current_app
from app.commons import db, myrq
from app.models import Statistic, CASE_UNPASS_REASON


class CaseStatistics:
    def __init__(self, ):
        self.today = datetime.datetime.now().strftime("%Y%m%d")
        self.id = int(self.today)
        self.project_stat = {}
        self.author_stat = {}

    def stat_by(self, by):
        total_num = db.session.execute(
            # Total number of cases per type
            f'''select {by}, type, COUNT(type)
            from "case"
            where deleted=false and created_time < '{self.today}' and project_id in (
            select id from "project" where deleted=false and status='active')
            group by {by}, type'''
        )

        executed_stat = db.session.execute(
            # Number of executed cases per type
            f'''select {by}, type, COUNT(type)
            from "case"
            where id in (select distinct case_id from "case_result" where updated_time < '{self.today}')
            and project_id in (select id from "project" where deleted=false and status='active')
            and deleted=false
            group by {by}, type'''
        )

        never_pass_stat = db.session.execute(
            # Number of cases per type that never passed
            f'''select {by}, type, COUNT(type)
            from "case" where id in (
            select distinct case_id from "case_result" where case_id in (
            select id from "case" where deleted=false and project_id in (
            select id from "project" where deleted=false and status='active')) and case_id not in (
            select case_id from "case_result" where (deleted=false and (
            status='pass' or comments is not null) and updated_time < '{self.today}') 
            group by case_id)) group by {by}, type'''
        )

        last_fail = db.session.execute(
            f'''select c.{by}, c.type, COUNT(c.type)
            from "case" c left join "case_result" cr 
            on c.id = cr.case_id
            where (cr.case_id, cr.updated_time) in (
            select case_id, max(updated_time) from "case_result" where deleted=false and case_id in (
            select id from "case" where deleted=false and project_id in (
            select id from "project" where deleted=false and status='active')) 
            and status in ('fail', 'error', 'timeout')
            and updated_time < '{self.today}'
            group by case_id)
            group by c.{by}, c.type'''
        )

        return total_num, executed_stat, never_pass_stat, last_fail

    def stat_by_project(self, ):
        project_stat, executed_stat, never_pass_stat, last_fail = self.stat_by('project_id')
        self.gen_json(project_stat, executed_stat, never_pass_stat, last_fail, self.project_stat)

    def stat_by_author(self, ):
        author_stat, executed_stat, never_pass_stat, last_fail = self.stat_by('author')
        self.gen_json(author_stat, executed_stat, never_pass_stat, last_fail, self.author_stat)

    @staticmethod
    def gen_json(stat_data, executed_data, never_pass_date, last_fail, stat_json):
        for data, detail_type, total_type in [(stat_data, "total_case_num", "total"),
                                              (executed_data, "executed_case_num", "executed_case_num"),
                                              (never_pass_date, "never_pass_case_num", "never_pass_case_num"),
                                              (last_fail, "last_fail_case_num", "last_fail_case_num")]:
            for item in data:
                stat_by = item[0]
                case_type = item[1] if item[1] else 'others'
                case_type_count = item[2]

                if stat_by not in stat_json:
                    stat_json[stat_by] = {
                        "total": 0,
                        "executed_case_num": 0,
                        "never_pass_case_num": 0,
                        "last_fail_case_num": 0,
                        "detail": {}
                    }

                if case_type not in stat_json[stat_by]["detail"]:
                    stat_json[stat_by]["detail"][case_type] = {
                        "total_case_num": 0,
                        "executed_case_num": 0,
                        "never_pass_case_num": 0,
                        "last_fail_case_num": 0
                    }

                stat_json[stat_by][total_type] += case_type_count
                stat_json[stat_by]["detail"][case_type][detail_type] += case_type_count

    def save_to_db(self, ):
        stat = Statistic.query.get(self.id)
        if stat:
            stat.project_data = self.project_stat
            stat.author_data = self.author_stat
        else:
            stat = Statistic(**{
                "id": self.id,
                "date": datetime.datetime.strptime(str(self.id), "%Y%m%d"),
                "project_data": self.project_stat,
                "author_data": self.author_stat,
                "project_exec_data": {},
                "author_exec_data": {}
            })
        stat.save()
        current_app.logger.info(f"The case data of {self.id} has been counted.")

    def start(self, ):
        self.stat_by_project()
        self.stat_by_author()
        self.save_to_db()


class ExecStatistics:
    def __init__(self, ):
        self.today = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        self.id = int(self.today)
        self.exec_stat_by_project = {}
        self.exec_stat_by_author = {}

    @staticmethod
    def stat_by(by, day, exec_data):
        data = db.session.execute(
            f'''select c.{by}, c.type, cr.status, cr.reason, COUNT(cr.status)
            from "case" c left join "case_result" cr
            on c.id = cr.case_id
            where c.deleted = false
            and (cr.debug_mode is null or cr.debug_mode = false)
            and to_char(cr.updated_time, 'yyyymmdd') = '{day}' and c.project_id in (
            select id from "project" where deleted=false and status='active')
            group by c.{by}, c.type, cr.status, cr.reason'''
        )

        exec_record = db.session.execute(
            f'''select c.{by}, c.type, c.id, cr.id, cr.status
            from "case" c left join "case_result" cr
            on c.id = cr.case_id
            where c.deleted = false 
            and (cr.debug_mode is null or cr.debug_mode = false)
            and to_char(cr.updated_time, 'yyyymmdd') = '{day}' and c.project_id in (
            select id from "project" where deleted=false and status='active')'''
        )

        for item in data:
            by, case_type, status, reason, count = item[0], item[1], item[2], item[3], item[4]
            if by not in exec_data:
                exec_data[by] = {
                    'pass': 0,
                    'undefined_fail': 0,
                    'dependency_issue': 0,
                    'environmental_issue': 0,
                    'script_issue': 0,
                    'platform_issue': 0,
                    'business_issue': 0,
                    'system_error': 0,
                    'case_error': 0,
                    'undefined_error': 0,
                    'timeout': 0,
                    'total': 0,
                    'detail': {}
                }
            if case_type not in exec_data[by]['detail']:
                exec_data[by]['detail'][case_type] = {
                    'pass': 0,
                    'undefined_fail': 0,
                    'dependency_issue': 0,
                    'environmental_issue': 0,
                    'script_issue': 0,
                    'platform_issue': 0,
                    'business_issue': 0,
                    'last_fail': 0,
                    'system_error': 0,
                    'case_error': 0,
                    'undefined_error': 0,
                    'timeout': 0,
                    'total': 0,
                    "exec_record": {}
                }
            if status in ['pass', 'timeout']:
                exec_data[by]['detail'][case_type][status] = count
                exec_data[by][status] += count
            elif status in ['error']:
                if reason in CASE_UNPASS_REASON['ERROR'].keys():
                    exec_data[by]['detail'][case_type][reason] = count
                    exec_data[by][reason] += count
                else:
                    exec_data[by]['detail'][case_type]["undefined_error"] = count
                    exec_data[by]["undefined_error"] += count
            elif status in ['fail']:
                if reason in CASE_UNPASS_REASON['FAIL'].keys():
                    exec_data[by]['detail'][case_type][reason] = count
                    exec_data[by][reason] += count
                else:
                    exec_data[by]['detail'][case_type]["undefined_fail"] = count
                    exec_data[by]["undefined_fail"] += count
            exec_data[by]['detail'][case_type]["total"] += count
            exec_data[by]["total"] += count

        for item in exec_record:
            by, case_type, case_id, case_result_id, status = item[0], item[1], item[2], item[3], item[4]
            if case_id not in exec_data[by]['detail'][case_type]['exec_record']:
                exec_data[by]['detail'][case_type]['exec_record'][case_id] = {}
            exec_data[by]['detail'][case_type]['exec_record'][case_id][case_result_id] = status

    def stat_exec_data_by_project(self, day):
        self.stat_by('project_id', day, self.exec_stat_by_project)

    def stat_exec_data_by_author(self, day):
        self.stat_by('author', day, self.exec_stat_by_author)

    def save_to_db(self, force=False):
        stat = Statistic.query.get(self.id)
        if stat:
            if not stat.project_exec_data or not stat.author_exec_data or force:
                stat.project_exec_data = self.exec_stat_by_project
                stat.author_exec_data = self.exec_stat_by_author
            else:
                current_app.logger.info(f"The exec data of {self.id} already exists, pass.")
                return
        else:
            stat = Statistic(**{
                "id": self.id,
                "date": datetime.datetime.strptime(str(self.id), "%Y%m%d"),
                "project_data": {},
                "author_data": {},
                "project_exec_data": self.exec_stat_by_project,
                "author_exec_data": self.exec_stat_by_author
            })
        stat.save()
        current_app.logger.info(f"The exec data of {self.id} has been counted.")

    def start(self, day=None, force=False):
        self.exec_stat_by_project = {}
        self.exec_stat_by_author = {}
        if not day:
            day = self.today
        else:
            self.id = int(day)
        self.stat_exec_data_by_project(day)
        self.stat_exec_data_by_author(day)
        self.save_to_db(force=force)


@myrq.job('statistic')
def start_statistics():
    try:
        case_stat = CaseStatistics()
        case_stat.start()

        exec_stat = ExecStatistics()
        exec_stat.start()

    except Exception:
        msg = f"Some errors occurred during the statistics: {traceback.format_exc()}"
        current_app.logger.error(f"Some errors occurred during the statistics: {traceback.format_exc()}")
        body = {
            "channel": "st",
            "content": msg,
            "g_name": "",
            "u_name": "jiaxin.chen@shopee.com"
        }
        requests.post(url=current_app.config['QABOT_NOTI'], headers={
            "accept": "application/json", "Content-Type": "application/json"}, json=body)


@myrq.job('statistic')
def stat_history_exec_data(start='', end='', force=False):
    try:
        stat = ExecStatistics()
        if not start and not end:
            # Statistics for the day only
            stat.start(force=force)
        else:
            start_day = datetime.datetime.strptime(start, '%Y%m%d') if start \
                else datetime.datetime.strptime('20210301', '%Y%m%d')
            end_day = datetime.datetime.strptime(end, '%Y%m%d') if end \
                else datetime.datetime.strptime(stat.today, '%Y%m%d')
            delta = datetime.timedelta(days=1)
            while start_day <= end_day:
                day = start_day.strftime("%Y%m%d")
                stat.start(day=day, force=force)
                start_day += delta

    except Exception:
        current_app.logger.error(f"Some errors occurred during statistic history exec data: {traceback.format_exc()}")
