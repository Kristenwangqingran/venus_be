# -*- coding: utf-8 -*-
# @Time    : 2020/8/13
# @Author  : Arrow
import json
import os

import jinja2
import pymongo
from flask import current_app
import traceback
import re
import requests
import threading
from urllib.parse import ParseResult
from urllib import parse
from collections import defaultdict
from .mixins import TimestampMixin, TaskStatus, TaskStatus_DONE, CASE_UNPASS_REASON
from app.commons import db, ma, utils
from marshmallow import ValidationError, fields
from .casesuite import Casesuite
from .group import Group
from .env import Env
from sqlalchemy.orm.attributes import flag_modified
from .notification import PhoneNoti


class SuiteResult(TimestampMixin, db.Model):
    LOCK = threading.Lock()
    normal = {
        "author": "kobe",
        "status": "running",
        "casesuite_name": "case1",
        "project_name": "project1",
        "env_name": "env1",
        "total": 0,
        "pass_num": 0,
        "fail_num": 0,
        "error_num": 0,
        "casesuite_id": 1
    }

    stastic_items = ("pass_num", "fail_num", "error_num", "timeout_num",
                     "skip_num", "canceled_num", "pending_num", "running_num")

    status_chan = {
        "running": "pending",
        "pass": "running",
        "fail": "running",
        "error": "running",
        "timeout": "running",
        "skip": "running",
        "canceled": "running",
    }

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(127), nullable=False,
                       default=TaskStatus["pending"])

    # 基本信息
    casesuite_name = db.Column(db.String, nullable=False)
    project_name = db.Column(db.String, nullable=False)
    env_name = db.Column(db.String, nullable=False)

    total = db.Column(db.Integer, nullable=False, default=0)
    pass_num = db.Column(db.Integer, nullable=False, default=0)
    fail_num = db.Column(db.Integer, nullable=False, default=0)
    error_num = db.Column(db.Integer, nullable=False, default=0)
    skip_num = db.Column(db.Integer, nullable=True)
    timeout_num = db.Column(db.Integer, nullable=True)

    pending_num = db.Column(db.Integer, nullable=False, default=0)
    running_num = db.Column(db.Integer, nullable=False, default=0)
    canceled_num = db.Column(db.Integer, nullable=False, default=0)
    success_rate = db.Column(db.Float, nullable=False, default=0)
    finish_rate = db.Column(db.Float, nullable=True)
    debug_mode = db.Column(db.Boolean, default=False)

    # mobile info
    device_info = db.Column(db.JSON, nullable=True, default={})

    log = db.Column(db.String(512), nullable=True)
    html_file = db.Column(db.String(512), nullable=True)

    casesuite_id = db.Column(
        db.Integer, db.ForeignKey('casesuite.id'), nullable=True)

    casesuite = db.relationship('Casesuite', backref=db.backref(
        'results', lazy=True), lazy='select', cascade="save-update, merge, refresh-expire, expunge",
        single_parent=True)

    extra = db.Column(db.JSON, nullable=True, default={})
    runner = db.Column(db.String(64), nullable=True)
    pfb = db.Column(db.String(256), nullable=True)

    def __format_summary(self, summmary, format, status_list, fmt='text', is_silence=True, **kwargs):
        '''
        fmt: md/html/text/None
        '''
        # summary = {
        #     "feature": {
        #         "feature1": [{}, {}],
        #         "feature2": [{}, {}],
        #     },
        infos = {
            "format": "table",
            "header": kwargs.get('headers'),
            "data": [],
            "rate": {}
        }
        tital = [format] + sorted(status_list)
        infos["data"].append(tital)
        datas = defaultdict(dict)
        # datas = {
        #         "feature1": {
        #                 "pass": 8,
        #                 "fail": 9
        #         },
        #         "feature2": [{}, {}],
        # },
        summmary = summmary.get(format, {})
        tmp_status_stastic = defaultdict(dict)
        for k, v in summmary.items():
            for status in status_list:
                datas[k][status] = 0

            for item in v:
                if item["status"] not in status_list:
                    if item["status"] not in tmp_status_stastic[k]:
                        tmp_status_stastic[k][item["status"]] = 0
                    tmp_status_stastic[k][item["status"]] += 1
                else:
                    datas[k][item["status"]] += 1

        for k, v in datas.items():
            if 'pass' in datas[k]:
                pass_num = datas[k]['pass']
            else:
                pass_num = tmp_status_stastic[k].get('pass', 0)
            total_num = sum(list(datas[k].values()) +
                            list(tmp_status_stastic[k].values()))
            infos["rate"][k] = round(
                pass_num / total_num, 3) if total_num else 0

            sorted_v = sorted(v)
            this_line = [k]
            usefull_count = 0
            for status in sorted_v:
                count = v[status]
                link = kwargs.get('base_url')
                the_fmt = 'group_name' if format == 'group' else format
                link_with_params = link + '?' + \
                    parse.urlencode({
                        "status": status,
                        the_fmt: k
                    })
                if count:
                    usefull_count += 1
                    if fmt == 'md':
                        this_line.append(f"[{count}]({link_with_params})")
                    elif fmt == 'html':
                        this_line.append(
                            f'<a href="{link_with_params}">{count}</a>')
                    elif fmt == 'text':
                        this_line.append(f"{count}, {link_with_params}")
                    elif fmt == 'None':
                        this_line.append(count)
                else:
                    this_line.append(count)
            if usefull_count:
                infos["data"].append(this_line)

        if len(infos["data"]) <= 1 and is_silence:
            infos = None
        return infos

    def __format_mail(self, text):
        with open('template.html') as f:
            template = jinja2.Template(f.read())
            html = template.render(text)

        return html

    def _send_mail(self, summmary, noti, **kwargs):
        user_list = noti.get("email", {}).get("list", [])
        format = noti.get("email", {}).get("format", 'group')
        status_list = noti.get("email", {}).get("status", [])
        is_silence = noti.get("email", {}).get(
            "details", {}).get("is_silence", True)
        user_list = [
            user for user in user_list if user.endswith("@shopee.com")]

        if not user_list or not status_list:
            return

        infos = self.__format_summary(
            summmary, format, status_list, fmt='html', is_silence=is_silence, **kwargs)

        if not infos:
            return

        msg = self.__format_mail(infos)

        url = current_app.config['MAIL_SERVER']
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }

        body = {
            "subject": f"test result of project {kwargs.get('project_name')} suite {kwargs.get('casesuite_name')}",
            "recipients": user_list,
            "html": msg
        }
        requests.post(url=url, headers=headers, json=body)

        current_app.logger.info(
            f"[{self.id}]Send email success!")

    def __format_seatalk(self, text):
        # project: antifraud_api
        # suite: antifraud_api_auto
        # total: 2082, pass: 1788, success rate: 0.8604
        # time cost: 26 days, 12:58:10.524290

        # |👉---------author: yan.xiao@shopee.com
        # |  ❌ fail: 79, http://10.12.78.79:7001/api/thecaseresults?suiteresult_id=18678&status=fail&author=yan.xiao%40shopee.com
        # |  ✅ pass: 413, http://10.12.78.79:7001/api/thecaseresults?suiteresult_id=18678&status=pass&author=yan.xiao%40shopee.com
        # |
        # |👉---------author: xiaoxiang.wu@shopee.com
        # |  ❌ fail: 36, http://10.12.78.79:7001/api/thecaseresults?suiteresult_id=18678&status=fail&author=xiaoxiang.wu%40shopee.com

        status_to_emoji = {
            "pass": '✅',
            "error": '⛔',
            "fail": '❌',
            "skip": '⏩',
            "timeout": '⏱️',
            "canceled": '❎'
        }

        to_show = ''
        if text['format'] == 'table':
            headers = text['data'][0]
            to_show += text['header'] + '\n'
            for item in text['data'][1:]:
                tmp_h_show = f"|👉----{headers[0]}: {item[0]}, pass rate: {round(text['rate'][item[0]] * 100, 1)}%\n"
                tmp_show = ""
                for i in range(1, len(headers)):
                    if isinstance(item[i], str):
                        count, link = item[i].split(', ')
                        if count:
                            tmp_show += f"|    {status_to_emoji[headers[i]]} {headers[i]}: {count}, {link}\n"
                    elif isinstance(item[i], int) and item[i]:
                        tmp_show += f"|    {status_to_emoji[headers[i]]} {headers[i]}: {item[i]}\n"
                if tmp_show:
                    to_show += tmp_h_show + tmp_show
                    to_show += '|\n'
            return to_show
        else:
            return text

    def __sorted(self, data, rate):
        return sorted(data, key=lambda x: rate[x[0]])

    def _send_seatalk(self, summmary, noti, **kwargs):
        st_url_list = noti.get("seatalk", {}).get("list", [])
        format = noti.get("seatalk", {}).get("format", 'group')
        status_list = noti.get("seatalk", {}).get("status", [])
        details = noti.get("seatalk", {}).get("details", {})
        withlink = details.get('withlink', True)
        is_silence = details.get("is_silence", True)

        st_url_list = [
            url for url in st_url_list if url.strip()]
        if not st_url_list or not status_list:
            return

        if withlink:
            infos = self.__format_summary(
                summmary, format, status_list, fmt='text', is_silence=is_silence, **kwargs)
        else:
            infos = self.__format_summary(
                summmary, format, status_list, fmt='None', is_silence=is_silence, **kwargs)

        if not infos:
            return

        infos['data'][1:] = self.__sorted(infos['data'][1:], infos['rate'])

        msg = self.__format_seatalk(infos)

        for url in st_url_list:
            current_app.logger.info(f"sent msg to seatalk hook: {url}")
            requests.post(url=url, json={
                "tag": "text",
                "text": {
                    "content": msg
                }
            })
        current_app.logger.info(f"st {kwargs.get('headers')} done!")
        current_app.logger.info(
            f"[{self.id}]Send seatalk success!")

    def __format_mattermost(self, text):
        to_show = ''
        if text['format'] == 'table':
            headers = text['data'][0]
            to_show = text['header']

            to_show += '\n|'
            for _, v in enumerate(headers):
                to_show += ' %s |' % (str(v).replace('|', " "))

            to_show += '\n|'
            for _, v in enumerate(headers):
                to_show += ' ---------- |'

            for item in text['data'][1:]:
                to_show += '\n|'
                for j in item:
                    to_show += '% s |' % str(j).replace('|', " ")

            return to_show

    def _send_mattermost(self, summmary, noti, **kwargs):
        mm_url_list = noti.get("mattermost", {}).get("list", [])
        format = noti.get(
            "mattermost", {}).get("format", 'group')
        status_list = noti.get("mattermost", {}).get("status", [])
        details = noti.get("mattermost", {}).get("details", {})
        withlink = details.get('withlink', True)
        is_silence = details.get('is_silence', True)

        mm_url_list = [
            url for url in mm_url_list if url.strip()]
        if not mm_url_list or not status_list:
            return

        if withlink:
            infos = self.__format_summary(
                summmary, format, status_list, fmt='md', is_silence=is_silence, **kwargs)
        else:
            infos = self.__format_summary(
                summmary, format, status_list, fmt='None', is_silence=is_silence, **kwargs)

        if not infos:
            return

        infos['data'][1:] = self.__sorted(infos['data'][1:], infos['rate'])
        msg = self.__format_mattermost(infos)

        for url in mm_url_list:
            res = requests.post(url, json={
                "channel": '',
                "text": msg
            })
            if res.status_code == 200:
                current_app.logger.info(
                    f"mm {kwargs.get('headers')} done! url: {url}")
            else:
                current_app.logger.error(f"mm {kwargs.get('headers')} fail! url: {url}, "
                                         f"response code: {res.status_code}, body: {res.text}")

        current_app.logger.info(
            f"[{self.id}]Send mattermost success!")

    def _send_qabot(self, summmary, noti, **kwargs):

        def __noti(channel, users, msg):
            for user in users:
                body = {
                    "channel": channel,
                    "content": msg,
                    "g_name": "",
                    "u_name": ""
                }
                if re.search(r":|：", user):
                    group_name, users = re.split(r":|：", user, 1)
                    body["u_name"] = users
                    body["g_name"] = group_name
                elif '@shopee.com' not in user:
                    body['g_name'] = user
                else:
                    body["u_name"] = user
                current_app.logger.info(f"qabot to send: {body}")
                requests.post(url=current_app.config['QABOT_NOTI'], headers={
                    "accept": "application/json", "Content-Type": "application/json"}, json=body)

        mm_users = noti.get("QABOT", {}).get("mattermost", [])
        st_users = noti.get("QABOT", {}).get("seatalk", [])
        format = noti.get("QABOT", {}).get("format", 'group')
        status_list = noti.get("QABOT", {}).get("status", [])
        details = noti.get("QABOT", {}).get("details", {})
        withlink = details.get('withlink', True)
        is_silence = details.get('is_silence', True)

        mm_users = [
            url for url in mm_users if url.strip()]
        st_users = [
            url for url in st_users if url.strip()]

        if not status_list or not (mm_users or st_users):
            return

        if withlink:
            mm_infos = self.__format_summary(
                summmary, format, status_list, fmt='md', is_silence=is_silence, **kwargs)
            st_infos = self.__format_summary(
                summmary, format, status_list, fmt='text', is_silence=is_silence, **kwargs)
        else:
            mm_infos = self.__format_summary(
                summmary, format, status_list, fmt='None', is_silence=is_silence, **kwargs)
            st_infos = self.__format_summary(
                summmary, format, status_list, fmt='None', is_silence=is_silence, **kwargs)

        if not mm_infos and not st_infos:
            return

        if mm_infos:
            mm_infos['data'][1:] = self.__sorted(
                mm_infos['data'][1:], mm_infos['rate'])
            mm_infos.update({'header': kwargs.get('mm_headers')})
            msg = self.__format_mattermost(mm_infos)
            __noti("mm", mm_users, msg)

        if st_infos:
            st_infos['data'][1:] = self.__sorted(
                st_infos['data'][1:], st_infos['rate'])
            msg = self.__format_seatalk(st_infos)
            __noti('st', st_users, msg)

        current_app.logger.info(f"qabot {kwargs.get('headers')} done!")
        current_app.logger.info(
            f"[{self.id}]Send qabot success!")

    def __get_successlike_case_count(self,):
        return self.pass_num + self.fail_num + self.error_num + self.timeout_num

    def __get_finish_case_count(self,):
        return self.pass_num + self.fail_num + self.error_num + self.timeout_num + self.skip_num + self.canceled_num

    def __init_case_count(self, force=False):
        for i in self.stastic_items:
            if getattr(self, i) is None or force is True:
                setattr(self, i, 0)

    def update_statistics(self, status=None):
        case_results = self.caseresults.all()
        if status == 'done':
            try:
                self.total = len(self.extra["cases"]) * \
                    self.extra.get("param_count", 1)
            except Exception:
                self.total = len(self.casesuite.case_id_list)

        self.__init_case_count(force=True)
        flag = True
        done, total = 0, 0
        for case_result in case_results:
            total += 1
            if case_result.status in TaskStatus_DONE:
                done += 1
            if case_result.status != 'fail':
                flag = False
            if case_result.status not in TaskStatus or (not self.extra.get("muti_param", False) and case_result.id !=
                                                        self.extra.get("cases", {}).get(str(case_result.case_id), [0])[-1]):
                continue
            item = f"{case_result.status}_num"
            setattr(self, item, getattr(self, item) + 1)

        if flag:
            data = {
                'reason': CASE_UNPASS_REASON['FAIL']["environmental_issue"]}
            self.caseresults.update(data)

        if self.total == 0:
            self.success_rate = 0
            self.finish_rate = 0
        else:
            if self.__get_finish_case_count() > 0:
                self.success_rate = round(
                    self.pass_num / self.__get_successlike_case_count(), 4) \
                    if self.__get_successlike_case_count() > 0 else 0
                self.finish_rate = round(done / max(total, self.total), 4)
            else:
                self.success_rate = 0
        self.save()

    def _get_summary(self):
        # summary = {
        #     "feature": {
        #         "feature1": [{}, {}],
        #         "feature2": [{}, {}],
        #     },
        #     "group": {
        #         "group1": [{}, {}],
        #         "group2": [{}, {}],
        #     },
        #     "author": {
        #         "author1": [{}, {}],
        #         "author2": [{}, {
        #             "case": "case1",
        #             "feature": "feature1",
        #             "group": "feature1",
        #             "author": "xiaojiji",
        #             "status": "pass",
        #             "report": "html link"
        #         }],
        #     },
        # }
        summary = {
            "group": defaultdict(list),
            "author": defaultdict(list),
        }

        def __get_basic_info(caseresult):
            return {
                "case": caseresult.case.name,
                "group": caseresult.case.get_base_group(),
                "author": caseresult.case.author,
                "status": caseresult.status,
                "report": caseresult.details[0].get("html_file", None) if caseresult.details else None
            }

        case_results = self.caseresults.all()
        for case_result in case_results:
            if case_result.id != self.extra["cases"].get(str(case_result.case_id), [0])[-1]:
                continue
            case_result_info = __get_basic_info(case_result)
            summary["group"][case_result_info["group"]].append(
                case_result_info)
            summary["author"][case_result_info["author"]].append(
                case_result_info)
        return summary

    def __get_code_coverage_content(self):
        try:
            code_coverage = self.extra.get("exec_data", {}).get("code_coverage", {}).get("status", False) \
                if self.extra else False
            cov_content = ''
            code_coverage_url = ''
            if code_coverage:
                code_coverage_url = os.path.join(current_app.config['TOMCAT_HOST'],
                                                 f'Coverage/{self.id}/report/{self.casesuite_name}.html')
                base_dir = os.path.join(
                    current_app.instance_path, current_app.config['LOG_FOLDER'])
                file_path = os.path.join(
                    base_dir, f'Coverage/{self.id}/debug/status.json')
                with open(file_path, 'r') as f:
                    data = json.load(f)
                if data and data.get("mongo_id_list", []):
                    mongo_config = current_app.config['MONGO']
                    client = pymongo.MongoClient(
                        mongo_config["URI"], mongo_config["PORT"])
                    mydb = client.goc
                    connection = mydb[mongo_config["COLLECTION"]]
                    for mongo_id in data["mongo_id_list"]:
                        cov_data = connection.find_one(
                            {'id': mongo_id}, {'git_repo': 1, 'coverage': 1})
                        repo = cov_data.get('git_repo', '')
                        inc_coverage = cov_data.get(
                            'coverage', {}).get('inc', {})
                        full_coverage = cov_data.get(
                            'coverage', {}).get('full', {})
                        if repo:
                            cov_content += f'|👉---git repo: {repo}\n'
                            if inc_coverage:
                                inc_total_rate = '{:.2%}'.format(
                                    inc_coverage['stmt']['hit'] /
                                    inc_coverage['stmt']['total']
                                    if inc_coverage['stmt']['total'] != 0 else 0)
                                cov_content += f'|     ⭐️inc total rate: {inc_total_rate}\n'
                            if full_coverage:
                                full_total_rate = '{:.2%}'.format(
                                    full_coverage['stmt']['hit'] /
                                    full_coverage['stmt']['total']
                                    if full_coverage['stmt']['total'] != 0 else 0)
                                cov_content += f'|     ⭐️full total rate: {full_total_rate}\n'
                    client.close()
            return cov_content, code_coverage_url
        except Exception:
            current_app.logger.error(
                f"[{self.id}]{traceback.format_exc()}")
            return None, None

    def __form_header(self, base_url):
        try:
            cov_content, code_coverage_url = self.__get_code_coverage_content()
            execution_time = str(self.updated_time -
                                 self.created_time).split('.')[0]
            headers = ""
            headers += f"Project: {self.project_name}\n"
            headers += f"Suite: {self.casesuite_name}\n"
            mm_headers = headers + f"[Details]({base_url}): total: {self.total}, ✅pass: {self.pass_num}, " \
                                   f"pass rate: {round(self.success_rate * 100, 2)}%\n"
            headers += f"Total: {self.total}, ✅ pass: {self.pass_num}, pass rate: {round(self.success_rate * 100, 2)}%\n"
            headers += f"Details: {base_url}\n"
            if cov_content and code_coverage_url:
                mm_headers += f"[Code Coverage]({code_coverage_url}):\n"
                mm_headers += cov_content
                headers += f"Code Coverage: {code_coverage_url}\n"
                headers += cov_content
            mm_headers += f"Time Cost: {execution_time}\n"
            headers += f"Time Cost: {execution_time}\n"

            runtime_args = self.extra.get('exec_data', {})
            api_runtime_args = runtime_args.get('api', {})
            common_runtime_args = runtime_args.get('common', {})
            mm_headers += f"Runtime args: env={api_runtime_args.get('env', {}).get('name', 'test-env')}, pfb={api_runtime_args.get('routing', {}).get('pfb', '')}, region={api_runtime_args.get('region', '')}\n"
            if common_runtime_args.get("extra", {}).get("coverage"):
                git_project_name = common_runtime_args["extra"].get(
                    "coverage").get("projectName")
                git_project_fullname = common_runtime_args["extra"].get(
                    "coverage").get("fullProjectName")
                git_branch_name = common_runtime_args["extra"].get(
                    "coverage").get("projectBranch")

                from app.libs import SCPMgr
                if git_project_fullname:
                    Total, ST, UT, *_ = SCPMgr.get_coverage_by_fullProjectName(
                        git_project_name, git_branch_name)
                else:
                    Total, ST, UT, *_ = SCPMgr.get_coverage_by_projectName(
                        git_project_name, git_branch_name)
                scp_url_info = SCPMgr.get_mergeddata_link(
                    git_project_name, git_project_fullname, git_branch_name)
                mm_headers += f"[code coverage]({scp_url_info}): Total={Total}, ST={ST}, UT={UT}\n"
                self.html_file = scp_url_info

            return headers, mm_headers
        except Exception:
            current_app.logger.error(
                f"[{self.id}]{traceback.format_exc()}")
            return None, None

    def save(self):
        with self.LOCK:
            try:
                if self.device_info is None:
                    self.device_info = {}
                flag_modified(self, "extra")
                flag_modified(self, "device_info")
                super().save()
                self.__init_case_count()
                if self.status in ["done", ] and not self.casesuite.is_manual:
                    self.status = 'pass' if self.pass_num == (
                        self.total - self.skip_num) else 'fail'

                    summmary = self._get_summary()
                    casesuite = Casesuite.query.get(self.casesuite_id)
                    noti = casesuite.noti or {}

                    base_url = parse.urljoin(
                        current_app.config['FE_SUITERESULT'], str(self.id))
                    normal_headers, mm_headers = self.__form_header(base_url)

                    try:
                        self._send_mail(summmary, noti, headers=normal_headers, project_name=self.project_name,
                                        casesuite_name=self.casesuite_name, base_url=base_url)

                    except Exception:
                        current_app.logger.error(
                            f"[{self.id}]{traceback.format_exc()}")

                    try:
                        self._send_seatalk(
                            summmary, noti, headers=normal_headers, base_url=base_url)

                    except Exception:
                        current_app.logger.error(
                            f"[{self.id}]{traceback.format_exc()}")

                    try:
                        self._send_mattermost(
                            summmary, noti, headers=mm_headers, base_url=base_url)

                    except Exception:
                        current_app.logger.error(
                            f"[{self.id}]{traceback.format_exc()}")

                    try:
                        self._send_qabot(
                            summmary, noti, base_url=base_url, headers=normal_headers, mm_headers=mm_headers)

                    except Exception:
                        current_app.logger.error(
                            f"[{self.id}]{traceback.format_exc()}")

                    if casesuite.runtime_config.get("common", {}).get("extra", {}).get("phone_noti", {}) and self.status not in ["pass"]:
                        obj = PhoneNoti(HOST_SPACE=current_app.config['HOST_SPACE'],
                                        HOST_SEE=current_app.config['HOST_SEE'],
                                        username=current_app.config['USERNAME'],
                                        password=current_app.config['PASSWORD'])
                        try:
                            for phone_number in casesuite.runtime_config["common"]["extra"]["phone_noti"].get("phone_number", []):
                                obj.send_phone_call(
                                    phone_number, "venus", casesuite.runtime_config["common"]["extra"]["phone_noti"].get("message", ""))
                        except Exception:
                            current_app.logger.error(
                                f"[{self.id}]{traceback.format_exc()}")

                    # to delete the one time suite
                    if self.casesuite.name.startswith('Batch-execution-'):
                        self.casesuite.delete()

            except Exception:
                current_app.logger.error(
                    f"[{self.id}]{traceback.format_exc()}")
            finally:
                super().save()

    @classmethod
    def post_check(cls, data):
        errors = []
        for k, v in cls.normal.items():
            if k in data:
                if isinstance(data[k], type(v)):
                    pass
                else:
                    errors.append(
                        f"{k}: value has wrong type! [{type(data[k])} != {type(v)}]")
            else:
                errors.append(f"{k} missed!")

        if errors:
            raise ValidationError(errors)

    def put_check(self, data):
        errors = []
        for k, v in self.normal.items():
            if k in data:
                if isinstance(data[k], type(v)):
                    pass
                else:
                    errors.append(
                        f"{k}: value has wrong type! [{type(data[k])} != {type(v)}]")
            else:
                pass
                # errors.append(f"{k} missed!")

        if errors:
            raise ValidationError(errors)


class SuiteResultSchema(ma.ModelSchema):
    class Meta:
        model = SuiteResult
        fields = ('author', 'created_time', 'updated_time', 'id', 'status', 'casesuite_name', 'project_name',
                  'env_name', 'total', 'pass_num', 'fail_num', 'error_num', 'skip_num', 'timeout_num',
                  'pending_num', 'running_num', 'canceled_num', 'success_rate', 'finish_rate', 'case_id', 'extra',
                  'casesuite_id', 'log', 'html_file', 'description', 'runner', 'pfb', 'is_cov', 'debug_mode', 'is_manual')

    is_cov = fields.Method("get_cov")
    is_manual = fields.Function(
        lambda obj: True if obj.casesuite and obj.casesuite.is_manual else False)

    def get_cov(self, obj):
        if obj.extra:
            return True if obj.extra.get('exec_data', {}).get('code_coverage', {}).get('status', False) else False
        else:
            return False


suiteresult_schema = SuiteResultSchema()
