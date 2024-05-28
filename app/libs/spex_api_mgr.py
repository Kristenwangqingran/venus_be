# -*- coding: utf-8 -*-
# @Time    : 2022/02/15
# @Author  : Chen Jiaxin

import os
import re
import szqa_utils
import copy
import time
import json
import queue
import datetime
import shutil
import asyncio
import datetime
import requests
import traceback
import multiprocessing
from collections import defaultdict
from multiprocessing import Queue, Event
from flask import current_app
from app.commons import myrq, Process, RunLogger, utils
from app.commons.hc_gen_case import default_template
from app.models import (SpexServiceGroup, SpexService, SpexApi, spex_service_group_schema,
                        spex_service_schema, spex_api_schema, HcTemplate)


class ResponseError(Exception):
    def __init__(self, msg):
        self.message = msg

    def __str__(self):
        return self.message


class SpexApiManagement:
    def __init__(self, token, process):
        self.spex_services = {}
        self.api = {}
        self.old = {"groups": {}, "services": {}, "apis": {}}
        self.process = process
        self.process.update({
            "name": f"init spex api management",
            "status": "ongoing",
            "details": f"..."
        })
        self.process.reset()
        self.prefix = f"[{process.project_id}]"

        self.save_queue = Queue()
        self.generate_template_queue = Queue()

        self.db_th_count = 16
        self.db_th = {}

        self.gen_th_count = 16
        self.gen_th = {}

        self.log_th = None

        self.new_api = []

        self.process.update({
            "name": f"init spex api management",
            "status": "success",
            "details": f"Initialization successful"
        })

    def start_db_thread(self, topics_dict):
        def _db_thread(app, tid, topics_dict):
            with app.app_context():
                current_app.logger.info(
                    f"{self.prefix} Start db thread {tid} ... ")
                while True:
                    try:
                        info = self.save_queue.get(block=True, timeout=10)
                        self.db_th[tid]["flag"] = True
                        save_type = info.get("type")
                        data = info.get("data")
                        if save_type == "group":
                            path = info.get("path")
                            sid = info.get("sid")
                            mum = SpexServiceGroup.query.filter_by(
                                name=path.split(".")[-1], space_id=sid, deleted=False).first() if path else None
                            if mum:
                                data["mum_id"] = mum.id

                            spex_service_group = SpexServiceGroup.query.filter_by(
                                space_id=data.get("space_id"), deleted=False).first()
                            if spex_service_group:
                                spex_service_group.put_save(data)
                                if spex_service_group.id in self.old["groups"]:
                                    self.old["groups"][spex_service_group.id] = True
                            else:
                                spex_service_group = spex_service_group_schema.load(
                                    data)
                                spex_service_group.save()
                        elif save_type == "service":
                            path = info.get("path")
                            sid = info.get("sid")
                            group = SpexServiceGroup.query.filter_by(
                                name=path.split(".")[-1], space_id=sid, deleted=False).first() if path else None
                            if group:
                                data["group_id"] = group.id
                            else:
                                current_app.logger.error(
                                    f"spex group[sid:{sid}]: not found")

                            spex_service = SpexService.query.filter_by(
                                space_id=data.get('space_id'), deleted=False).first()
                            if spex_service:
                                current_app.logger.warn(
                                    f"update service: {data['space_id']} {data['path']}.{data['name']}")
                                spex_service.put_save(data)
                            else:
                                current_app.logger.warn(
                                    f"add new service: {data['space_id']} {data['path']}.{data['name']}")
                                spex_service = spex_service_schema.load(data)
                                spex_service.save()
                        elif save_type == 'topic':
                            space_id = info.get("space_id")
                            spex_service = SpexService.query.filter_by(
                                space_id=space_id, deleted=False).first()
                            if spex_service:
                                current_app.logger.warn(
                                    f"to update spex service [id:{spex_service.id}, space_id:{space_id}]: {data}")
                                spex_service.put_save(data)
                                if self.old["services"].get(spex_service.id, None) is not None:
                                    for topic in data.get("topics", []):
                                        self.old["services"][spex_service.id][topic] = True
                            else:
                                current_app.logger.error(
                                    f"no spex service found [space_id:{space_id}]")
                        elif save_type == 'api':
                            service_space_id = info.get("service_space_id")
                            topic = info.get("topic")
                            service_cls = SpexService.query.filter_by(
                                space_id=int(service_space_id), deleted=False).first()
                            data['service_id'] = service_cls.id

                            spex_api = SpexApi.query.filter_by(
                                name=data['name'], topic=data['topic'],
                                service_id=data['service_id'], deleted=False).first()
                            if spex_api:
                                spex_api.put_save(data)
                                if self.old["apis"].get(service_cls.id, None) and \
                                        self.old["apis"][service_cls.id].get(topic, None):
                                    self.old["apis"][service_cls.id][topic][spex_api.id] = True
                            else:
                                spex_api = spex_api_schema.load(data)
                                spex_api.save()
                                self.new_api.append({
                                    "service": f"{service_cls.path}.{service_cls.name}",
                                    "topic": spex_api.topic,
                                    "api": spex_api.name
                                })

                            self.generate_template_queue.put(spex_api.id)

                        elif save_type == 'gameover':
                            current_app.logger.warn(
                                f"{self.prefix} DB thread {tid} end")
                            self.generate_template_queue.put(0)
                            break

                    except queue.Empty:
                        pass

                    except Exception:
                        current_app.logger.error(
                            f"{self.prefix} Some wrong happened in db thread: {traceback.format_exc()}")

                    finally:
                        self.db_th[tid]["flag"] = False

        for i in range(1, self.db_th_count + 1):
            th = szqa_utils.thread.ExtThread(target=_db_thread, args=(
                current_app._get_current_object(), i, topics_dict))
            th.start()
            self.db_th[i] = {
                "thread": th,
                "flag": False
            }

    def start_gen_template_thread(self):
        def _gen_template(app, tid):
            with app.app_context():
                current_app.logger.info(
                    f"{self.prefix} Start generate template thread {tid} ... ")
                while True:
                    api_id = self.generate_template_queue.get()
                    if api_id == 0:
                        current_app.logger.warn(
                            f"{self.prefix} GEN thread {tid} end")
                        break
                    self.gen_th[tid]["flag"] = True
                    api = SpexApi.query.get(api_id)
                    # current_app.logger.debug(
                    #     f"{self.prefix} To generate basic template of [{api.id}][{api.topic}] {api.name}")
                    try:
                        fields = default_template(
                            api.request, api.response, list(api.errors.values()))
                        updated = False
                        for template in api.templates:
                            if template.type == "basic":
                                template.put_check({
                                    "fields": fields
                                })
                                updated = True
                            else:
                                nd = HcTemplate.update_old_template(
                                    template.fields, fields)
                                template.put_check({
                                    "fields": nd
                                })
                            template.save()

                        if not updated:
                            template = HcTemplate(**{
                                "name": "basic",
                                "type": "basic",
                                "is_default": True,
                                "fields": fields,
                                "api_id": api.id,
                                "api_type": "spex",
                            })
                            template.save()
                        # current_app.logger.debug(
                        #     f"{self.prefix} Generate basic template success: [{api.id}] {api.name}")

                    except Exception:
                        current_app.logger.error(f"{self.prefix} Generate [{api.id}]{api.name} basic template failed! "
                                                 f"details: {traceback.format_exc()}")

                    finally:
                        self.gen_th[tid]["flag"] = False

        for i in range(1, self.gen_th_count + 1):
            th = szqa_utils.thread.ExtThread(
                target=_gen_template, args=(current_app._get_current_object(), i))
            th.start()
            self.gen_th[i] = {
                "thread": th,
                "flag": False
            }

    def start_log_thread(self):
        def _log_thread(app):
            with app.app_context():
                current_app.logger.info(f"{self.prefix} Start log thread ... ")
                while True:
                    try:
                        current_app.logger.info(
                            f"{self.prefix} Main process running:\n"
                            f"gen queue size: {self.generate_template_queue.qsize()}, "
                            f"status: {['running' if info['flag'] else 'idle' for _, info in self.gen_th.items()]}\n"
                            f"db queue size: {self.save_queue.qsize()}, "
                            f"status: {['running' if info['flag'] else 'idle' for _, info in self.db_th.items()]}")

                        time.sleep(30)

                    except Exception:
                        current_app.logger.error(
                            f"{self.prefix} Some wrong happened while logging: {traceback.format_exc()}")

        self.log_th = szqa_utils.thread.ExtThread(
            target=_log_thread, args=(current_app._get_current_object(),))
        self.log_th.start()

    def get_old(self, groups, services, topics_dict=None):
        try:
            if groups:
                for group_space_id in groups:
                    mum_group_instance = SpexServiceGroup.query.filter_by(space_id=group_space_id,
                                                                          deleted=False).first()
                    if not mum_group_instance:
                        continue
                    for service in mum_group_instance.services:
                        self.old["services"][service.id] = {}
                        if service.topics:
                            for topic in service.topics:
                                self.old["services"][service.id][topic] = False
                    child_group_instances = SpexServiceGroup.query.filter_by(mum_id=mum_group_instance.id,
                                                                             deleted=False).all()
                    for child in child_group_instances:
                        self.old["groups"][child.id] = False
                        for service in child.services:
                            self.old["services"][service.id] = {}
                            self.old["apis"][service.id] = {}
                            if service.topics:
                                for topic in service.topics:
                                    self.old["services"][service.id][topic] = False
                                    self.old["apis"][service.id][topic] = {}
                            if service.apis:
                                for api in service.apis:
                                    if not api.deleted:
                                        if api.topic not in self.old["apis"][service.id]:
                                            self.old["apis"][service.id][api.topic] = {
                                            }
                                        self.old["apis"][service.id][api.topic][api.id] = False

            if services:
                for service_space_id in services:
                    service_instance = SpexService.query.filter_by(
                        space_id=service_space_id, deleted=False).first()
                    if service_instance:
                        if not self.old["services"].get(service_instance.id):
                            self.old["services"][service_instance.id] = {}
                        if not self.old["apis"].get(service_instance.id):
                            self.old["apis"][service_instance.id] = {}

                        topics = service_instance.topics if not topics_dict \
                            else topics_dict.get(str(service_space_id), service_instance.topics)

                        if topics:
                            for topic in topics:
                                self.old["services"][service_instance.id][topic] = False
                                self.old["apis"][service_instance.id][topic] = {}
                        for api in service_instance.apis:
                            if not api.deleted:
                                if api.topic in self.old["apis"][service_instance.id]:
                                    self.old["apis"][service_instance.id][api.topic][api.id] = False
                                # else:
                                #     self.old["apis"][service_instance.id][api.topic] = {api.id: False}
                    else:
                        current_app.logger.error(
                            f"{self.prefix} service not found, service_space_id:{service_space_id}")

        except Exception:
            current_app.logger.error(
                f"{self.prefix}Get old error: {traceback.format_exc()}")

    def delete_old(self, ):
        try:
            for group_id, updated in self.old["groups"].items():
                if not updated:
                    group = SpexServiceGroup.query.get(group_id)
                    group.delete()
                    current_app.logger.info(
                        f"{self.prefix} group {group.id} {group.name} delete success!")
            with open("old.json", 'w') as f:
                json.dump(self.old, f)

            for service_id, topic_info in self.old["services"].items():
                service = SpexService.query.get(service_id)
                if not any(topic_info.values()):
                    service.delete()
                    current_app.logger.info(
                        f"{self.prefix} service {service.id} {service.name} delete success!")
                for topic, updated in topic_info.items():
                    if not updated:
                        pb_dir = os.path.join(current_app.instance_path, current_app.config['PB_DIR'],
                                              utils.ensure_dirname(
                                                  service.path + '.' + service.name),
                                              utils.ensure_dirname(os.path.join(topic)))
                        shutil.rmtree(pb_dir, ignore_errors=True)
                        current_app.logger.info(
                            f"{self.prefix}{pb_dir} remove success!")

            for service_id, topic_info in self.old["apis"].items():
                for topic, api_info in topic_info.items():
                    for api_id, updated in api_info.items():
                        if not updated:
                            api = SpexApi.query.get(api_id)
                            api.delete()
                            current_app.logger.info(
                                f"{self.prefix} {api.id} {api.name}[{api.topic}] delete success!")

        except Exception:
            current_app.logger.error(
                f"{self.prefix}Delete old error: {traceback.format_exc()}")

    def check_done(self, ):

        def _stop_other_process(need_to_stop):
            need_end = False
            while need_end is False:
                need_end = True
                for th in need_to_stop:
                    try:
                        if th and th.is_alive():
                            need_end = False
                            current_app.logger.warn(
                                f"{self.prefix} Some DB/GEN th still ongoing!")
                            time.sleep(1)
                            break

                        break
                    except Exception:
                        current_app.logger.error(f"{self.prefix} Some wrong happened while stop sub process!\n"
                                                 f"{traceback.format_exc()}")

        try:

            _stop_other_process([info["thread"] for _, info in self.db_th.items()]
                                + [info["thread"]
                                    for _, info in self.gen_th.items()])

        except Exception:
            current_app.logger.error(f"Some wrong happened while checking done!\n"
                                     f"{traceback.format_exc()}")

    def wait_idel(self, ):
        try:
            ok = False
            while ok is False:
                ok = True
                if self.save_queue.qsize() > 0:
                    ok = False
                    current_app.logger.info(
                        f"save_queue is not empty, wait 10s...")
                    time.sleep(10)
                    continue

                for i, info in self.db_th.items():
                    if info['flag'] is True:
                        ok = False
                        current_app.logger.info(
                            f"db th {i} is busy, wait 5s...")
                        time.sleep(5)
                        break

        except Exception:
            current_app.logger.error(f"Some wrong happened while checking done!\n"
                                     f"{traceback.format_exc()}")

    def send_message(self, author):
        MAX_LINES = 200
        msg_list = []
        try:
            if not self.new_api:
                # No messages without new api
                current_app.logger.info(f"no new api found")
                return

            msg = f"{author} triggered sync, ends at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                  f"This sync adds the following api [format: <service> | <topic> | <api>]\n"
            current_line = 0
            for info in self.new_api:
                msg += f'{info.get("service")} | {info.get("topic")} | {info.get("api")}\n'
                current_line += 1

                if current_line == MAX_LINES:
                    msg_list.append(msg)
                    msg = ""
                    current_line = 0
            if msg:
                msg_list.append(msg)

            for people in current_app.config['SPEX_API_UPDATE_NOTI']:
                for msg in msg_list:
                    body = {
                        "channel": "st",
                        "content": msg,
                        "g_name": "",
                        "u_name": people
                    }
                    requests.post(url=current_app.config['QABOT_NOTI'], headers={
                        "accept": "application/json", "Content-Type": "application/json"}, json=body)

                current_app.logger.info(
                    f"{self.prefix}Send message to {people} success!")

        except Exception:
            current_app.logger.error(
                f"{self.prefix}Send message error: {traceback.format_exc()}")

    def parser(self, logpath):
        group_file = os.path.join(logpath, "groups.json")
        if os.path.exists(group_file):
            with open(group_file) as f:
                groups = json.load(f)
                for info in groups:
                    data = {
                        "name": info['display_name'],
                        "space_id": info['self_id'],
                        "path": info['path'],
                        "info": {
                            "create_time": '-',
                            "update_time": '-'
                        }
                    }
                    self.save_queue.put({
                        "type": "group",
                        "path": info['path'],
                        "sid": info['mum_id'],
                        "data": data
                    }, block=False)
        self.wait_idel()

        service_file = os.path.join(logpath, "services.json")
        if os.path.exists(service_file):
            with open(service_file) as f:
                services = json.load(f)
                for info in services:
                    data = {
                        "name": info['display_name'],
                        "space_id": info['self_id'],
                        "path": info['path'],
                        "info": {
                            "error_code_range": info['error_code_range'],
                            "create_time": '-',
                            "update_time": '-'
                        }
                    }
                    current_app.logger.warn(
                        f"to update service: {info['self_id']} {info['path']}.{info['display_name']}")
                    self.save_queue.put({
                        "type": "service",
                        "path": info['path'],
                        "sid": info['mum_id'],
                        "data": data
                    }, block=False)
        self.wait_idel()

        topic_file = os.path.join(logpath, "topics.json")
        if os.path.exists(topic_file):
            service_topic_map = {}
            with open(topic_file) as f:
                topics = json.load(f)
                for info in topics:
                    if info['service_id'] not in service_topic_map:
                        service_topic_map[info['service_id']] = {
                            "service_name": info['service_name'],
                            "topics": []
                        }
                    service_topic_map[info['service_id']
                                      ]["topics"].append(info['display_name'])
            for service_id, info in service_topic_map.items():
                self.save_queue.put({
                    "type": "topic",
                    "full_name": service_topic_map[service_id]["service_name"],
                    "space_id": service_id,
                    "data": {
                        "topics": service_topic_map[service_id]["topics"]
                    }
                }, block=False)
        self.wait_idel()

        # scan all files under logpath forder, to record all apis to DB
        all_things = os.listdir(logpath)
        for item in all_things:
            if not item.startswith('.') and os.path.isdir(os.path.join(logpath, item)):
                dir_m = re.match(
                    r'(?P<service_id>\d+)\-(?P<service_name>[\w.]+)', item)
                if dir_m:
                    all_topics = os.listdir(os.path.join(logpath, item))
                    for topic in all_topics:
                        apis = defaultdict(dict)
                        errorcodes = {}
                        ec_file = os.path.join(
                            logpath, item, topic, "errorcodes.json")
                        if os.path.exists(ec_file):
                            with open(ec_file) as f:
                                errorcodes = json.load(f)
                        if not errorcodes:
                            errorcodes = {
                                "ERROR_NOERRORCODE_MIN": 99999998,
                                "ERROR_NOERRORCODE_MAX": 99999999
                            }

                        all_filse = os.listdir(
                            os.path.join(logpath, item, topic, "apis"))

                        for the_file in all_filse:
                            cmd_m = re.match(
                                r'(?P<api_name>\w+)--(?P<msg_name>\w+)--(?P<msg_type>req|resp).json', the_file)
                            if cmd_m:
                                apis[cmd_m.group('api_name')]["name"] = cmd_m.group(
                                    'api_name')
                                apis[cmd_m.group('api_name')]["topic"] = topic
                                apis[cmd_m.group('api_name')
                                     ]["errors"] = errorcodes

                                if cmd_m.group('msg_type') == "req":
                                    apis[cmd_m.group('api_name')]["req_name"] = cmd_m.group(
                                        'msg_name')
                                    with open(os.path.join(logpath, item, topic, "apis", the_file)) as f:
                                        apis[cmd_m.group(
                                            'api_name')]["request"] = json.load(f)
                                else:
                                    apis[cmd_m.group('api_name')]["resp_name"] = cmd_m.group(
                                        'msg_name')
                                    with open(os.path.join(logpath, item, topic, "apis", the_file)) as f:
                                        apis[cmd_m.group('api_name')
                                             ]["response"] = json.load(f)

                        for _, api in apis.items():
                            self.save_queue.put({
                                "type": "api",
                                "service_space_id": int(dir_m.group('service_id')),
                                "topic": topic,
                                "data": api
                            }, block=False)
        self.wait_idel()

        # let them die
        for _ in range(1, self.gen_th_count + 1):
            self.save_queue.put({
                "type": "gameover"
            }, block=False)

    def get_api_from_space(self, space_id_dict=None, update_all=True, message=True, author='System'):
        next_group = [0] if update_all else space_id_dict.get("groups", [])
        next_service = space_id_dict.get("services", [])

        try:
            self.start_db_thread(space_id_dict.get('topics', {}))
            self.start_gen_template_thread()
            self.get_old(next_group, space_id_dict.get(
                "services", []), space_id_dict.get('topics', {}))

            # TODO call spexmgr
            logpath = os.path.join(
                current_app.instance_path, current_app.config['LOG_FOLDER'], f"spexmgr_{datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S.%f')}")
            if not os.path.exists(logpath):
                os.makedirs(logpath, exist_ok=True)
            logfile = os.path.join(logpath, "spexmgr.log")

            if next_group:
                for group in next_group:
                    cmd = f"spexmgr group {group} --output-path={logpath}"
                    with open(logfile, 'a+') as f:
                        utils.run_cmd_record_log(
                            cmd, os.getcwd(), log_stream=f, env=None, timeout=1800, prefix=self.prefix)
                    # only handle the mum group
                    break
            else:
                # no need to query service
                for service in next_service:
                    service_ins = SpexService.query.filter_by(
                        space_id=service, deleted=False).first()
                    if not service_ins:
                        continue

                    cmd = f"spexmgr topic --service-ID={service} --service-Name={service_ins.path}.{service_ins.name} --output-path={logpath}"
                    with open(logfile, 'a+') as f:
                        utils.run_cmd_record_log(
                            cmd, os.getcwd(), log_stream=f, env=None, timeout=900, prefix=self.prefix)

            self.start_log_thread()
            self.process.update({
                "name": f"update api",
                "status": "ongoing",
                "details": f"Updating"
            })
            self.parser(logpath)
            self.log_th.stop()
            self.check_done()
            self.process.update({
                "name": f"update api",
                "status": "success",
                "details": f"Update api success"
            })

            self.process.update({
                "name": f"delete old api",
                "status": "ongoing",
                "details": f"delete old api ongoing"
            })
            self.delete_old()
            self.process.update({
                "name": f"delete old api",
                "status": "success",
                "details": f"delete old api success"
            })
            if message:
                self.send_message(author)

        except Exception:
            current_app.logger.error(
                f"{self.prefix}Some errors occurred while getting api from space: {traceback.format_exc()}")


class SpaceTokenManagement:

    @staticmethod
    def get_token_from_space():
        token = ''
        try:
            s = requests.session()
            s.auth = (current_app.config['SPCLI_USER'],
                      current_app.config['SPCLI_PSD'])
            r = s.post(current_app.config['SPACE_AUTH_URL'])
            if r.status_code == 200:
                r = json.loads(r.text)
                token = r['token']
            else:
                current_app.logger.error(
                    f'Get token return err: [{r.status_code}] {r.text}')

        except Exception:
            current_app.logger.error(
                f'Get space token error: {traceback.format_exc()}')

        return token


@myrq.job('update_spex_api')
def get_spex_api(token, space_id_dict=None, update_all=False, process_id=0, message=True, author='System'):
    process = None
    logger = None
    try:
        logger = RunLogger(process_id, os.path.join(
            current_app.instance_path, "logs", current_app.config['HC_PATH']))
        process = Process(process_id)
        sam = SpexApiManagement(token, process)
        sam.get_api_from_space(space_id_dict=space_id_dict,
                               update_all=update_all, message=message, author=author)

    except Exception:
        current_app.logger.error(
            f"[RQ]Update spex api failed: {traceback.format_exc()}")

    finally:
        if process:
            process.finish()
        if logger:
            logger.release()


def scheduled_update():
    try:
        stm = SpaceTokenManagement()
        token = stm.get_token_from_space()
        if not token:
            msg = f"There is no valid token to update the spex resource, " \
                  f"please go to the automation platform to trigger it manually!"
            for people in current_app.config['SPEX_API_SCHEDULE_FAIL_NOTI']:
                body = {
                    "channel": "st",
                    "content": msg,
                    "g_name": "",
                    "u_name": people
                }
                requests.post(url=current_app.config['QABOT_NOTI'], headers={
                    "accept": "application/json", "Content-Type": "application/json"}, json=body)
        else:

            process_id = int(time.time())
            get_spex_api.queue(token=token, space_id_dict={"groups": [90009]},
                               update_all=False, process_id=process_id, timeout=2 * 60 * 60, result_ttl=4 * 60 * 60)

    except Exception:
        current_app.logger.error(
            f"Some wrong happend while update spex resources: {traceback.format_exc()}")
