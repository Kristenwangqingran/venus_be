# -*- coding: utf-8 -*-
# @Time    : 2020-09-21
# @Author  : GongXun
import copy
import os
import traceback
import datetime

import requests
from flask_apscheduler import APScheduler as _BaseAPScheduler
from app.commons import utils, MyRedis


class APScheduler(_BaseAPScheduler):

    def run_job(self, id, jobstore=None):
        with self.app.app_context():
            self.app.logger.info(self.app, self.app.app_context)
            super().run_job(id=id, jobstore=jobstore)


class MyScheduler:

    def __init__(self, app, env):
        scheduler = APScheduler()
        scheduler.init_app(app)
        scheduler.start()
        self.app = app
        self.env = env
        self.scheduler = scheduler

    def show_tasks(self):
        if not self.check_server():
            return

        tasks = []
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            info = {
                "func": job.func_ref,
                "args": job.args,
                "kwargs": job.kwargs,
                # "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": str(job.next_run_time),
                "id": job.id
            }
            tasks.append(info)
        return tasks

    def get_job(self, id):
        info = {}
        job = self.scheduler.get_job(id)
        if job:
            info = {
                "func": job.func_ref,
                "args": job.args,
                "kwargs": job.kwargs,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": str(job.next_run_time),
                "id": job.id
            }
        return info

    def check_server(self, ):
        hd = MyRedis(self.app.config['URL_FOR_RESULT'])
        current = hd.get('CURRENT_WEBSERVER')
        if current:
            current = current.decode('utf-8')
        else:
            current = os.environ.get('CURRENT_WEBSERVER')
        hd.disconnect()
        if current == os.environ.get('CURRENT_WEBSERVER'):
            return True
        else:
            self.app.logger.info(f'This service does not perform timed tasks.')
            return False

    def run_suite(self, suite_id, data):
        from app.libs import ExecMgr
        self.app.logger.info(f'ASP to run suite: {suite_id}, args={data}')
        if self.env != 'live' or not self.check_server():
            return
        else:
            with self.scheduler.app.app_context():
                data["author"] = 'scheduler'
                err = ExecMgr.run_suite_v2(suite_id=suite_id, data=data)
                if err:
                    self.app.logger.error(err)

    def add_seconds_task(self, task_id, func, kwargs, seconds):
        self.app.logger.info(f'To add a new task: {task_id} {func}')
        if self.is_task_exist(task_id):
            self.remove_task(task_id=task_id)

        job = self.scheduler.add_job(id=task_id, func=func, trigger='date', kwargs=kwargs,
                                     next_run_time=datetime.datetime.now(
                                     ) + datetime.timedelta(seconds=seconds), max_instances=1, replace_existing=True)
        return job

    def init_task(self, suite_cls):
        with self.scheduler.app.app_context():
            suites = suite_cls.query.filter_by(deleted=False).all()
            for suite in suites:
                if suite.schedule and suite.schedule.get('status', 'disabled') == "enabled":

                    try:
                        task_dict = suite.schedule['time_info']
                        kwargs = {
                            "suite_id": suite.id,
                            "data": {
                                "author": 'scheduler',
                                "code_coverage": suite.runtime_config.get("code_coverage", {}),
                                "official_mobile": suite.runtime_config.get("official_mobile", {}),
                                "official_web": suite.runtime_config.get("official_web", {}),
                                "api": suite.runtime_config.get("api", {}),
                                "common": suite.runtime_config.get("common", {})
                            }
                        }
                        self.add_task(task_id=str(suite.id), task_name='run_suite',
                                      trigger=suite.schedule['trigger'], kwargs=kwargs, task_dict=task_dict)
                    except Exception:
                        self.app.logger.error(
                            f'add task {suite} faild: {traceback.format_exc()}')

    def is_task_exist(self, task_id):
        task_exist = False
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            if job.id == task_id:
                task_exist = True
                break
        return task_exist

    def get_task_dict(self, trigger, task_dict):
        if trigger == "interval":
            dst_task_dict = {
                'seconds': int(task_dict['seconds'])
            }
        else:
            dst_task_dict = {
                'year': task_dict['year'],
                'month': task_dict['month'],
                # 'day_of_week': task_dict.get('day_of_week', '1'),
                # 'day': task_dict['day'],
                'hour': task_dict['hour'],
                'minute': "0" if task_dict['minute'] == '*' else task_dict['minute'],
                'second': "0" if task_dict['second'] == '*' else task_dict['second'],
            }
            if task_dict.get('day_of_week', '?') == '?':
                dst_task_dict['day'] = task_dict['day']
            else:
                dst_task_dict['day_of_week'] = task_dict['day_of_week']

            dst_task_dict = utils.del_empty(dst_task_dict)
        return dst_task_dict

    def add_task(self, *, task_id, task_name, trigger, kwargs, task_dict):
        self.app.logger.info(f'To add a new task: {task_id} {task_name}')
        if self.is_task_exist(task_id):
            self.app.logger.info(
                f'New task: {task_id} {task_name} exist, del it 1st...')
            self.remove_task(task_id=task_id)

        task_dict = self.get_task_dict(trigger, task_dict)

        job = self.scheduler.add_job(id=task_id, func=getattr(self, task_name),
                                     trigger=trigger, kwargs=kwargs, **task_dict, max_instances=1,
                                     replace_existing=True, misfire_grace_time=10*60)
        return job

    def modify_task(self, *, task_id, task_name, trigger, kwargs, task_dict):
        if not self.is_task_exist(task_id):
            return self.add_task(task_id=task_id, task_name=task_name, trigger=trigger, kwargs=kwargs,
                                 task_dict=task_dict)
        else:
            self.app.logger.info(f'To modify task: {task_id} {task_name}')
            task_dict = self.get_task_dict(trigger, task_dict)
            job = self.scheduler.modify_job(id=task_id, func=getattr(self, task_name),
                                            trigger=trigger, kwargs=kwargs, **task_dict, max_instances=1)
            return job

    def remove_task(self, *, task_id):
        if not self.is_task_exist(task_id):
            return False
        else:
            self.scheduler.remove_job(id=task_id)
            return True

    def add_debug_task(self):
        self.scheduler.add_job(name='show current tasks', id='0', func=self.show_tasks,
                               trigger='interval', seconds=1 * 60 * 60, max_instances=1, replace_existing=True)
        return True

    def clean(self, days, platform=False):
        from app.libs import clean_logs
        if not self.check_server():
            return

        with self.scheduler.app.app_context():
            err = clean_logs.queue(
                days=days, platform=platform, timeout=24 * 60 * 60)
            if err:
                self.app.logger.error(err)

    def clean_old_logs(self, case_log_clean_day=7, platform_log_clean_day=7):
        """
        Timed cleanup of logs that have existed for longer than the specified time.

        :param case_log_clean_month: Set how long ago the case logs were cleaned, in months, default is 3
        :type case_log_clean_month: int
        :param platform_log_clean_day: Set how long ago the platform logs were cleaned, in days, default is 14
        :type platform_log_clean_day: int
        """
        try:
            self.scheduler.add_job(name='clean old logs', id='100000', func=self.clean,
                                   args=(case_log_clean_day, False), trigger='cron',
                                   day=f'*/{case_log_clean_day}',
                                   start_date='2021-10-1', max_instances=1, replace_existing=True)
            self.scheduler.add_job(name='clean old platform logs', id='100001', func=self.clean,
                                   args=(platform_log_clean_day, True), trigger='cron',
                                   day=f'*/{platform_log_clean_day}',
                                   start_date='2021-10-1', max_instances=1, replace_existing=True)
        except Exception as e:
            self.app.logger.error(
                f"An error occurred while adding a task to clean up logs regularly: {e}")

    def statistics(self, ):
        from app.libs import start_statistics
        if not self.check_server():
            return

        with self.scheduler.app.app_context():
            self.app.logger.info(
                f"ASP to start statistics of {datetime.datetime.now().strftime('%Y%m%d')}")
            err = start_statistics.queue(timeout=24 * 60 * 60)
            if err:
                self.app.logger.error(err)

    def stat_job(self, ):
        try:
            self.scheduler.add_job(name='statistics', id='100002', func=self.statistics, args=(),
                                   trigger='cron', day=f'*/1', start_date='2021-10-1',
                                   max_instances=1, replace_existing=True)
        except Exception:
            self.app.logger.error(
                f"An error occurred while adding a task to statistics: {traceback.format_exc()}")

    def products_clean(self, days):
        from app.libs import clean_products_folder
        if not self.check_server():
            return

        with self.scheduler.app.app_context():
            err = clean_products_folder.queue(days=days, timeout=24 * 60 * 60)
            if err:
                self.app.logger.error(err)

    def clean_products_logs(self, clean_days=7):
        try:
            self.scheduler.add_job(name='clean old products logs', id='100003', func=self.products_clean,
                                   args=(clean_days,), trigger='cron', day=f'*/{clean_days}',
                                   start_date='2021-10-1', max_instances=1, replace_existing=True)
        except Exception as e:
            self.app.logger.error(
                f"An error occurred while adding a task to clean up products logs regularly: {e}")

    def clean_db(self):
        from app.libs import clean_database
        if not self.check_server():
            return

        with self.scheduler.app.app_context():
            err = clean_database.queue(timeout=24 * 60 * 60)
            if err:
                self.app.logger.error(err)

    def clean_db_scheduler(self, days=3):
        try:
            self.scheduler.add_job(name='clean database', id='100004', func=self.clean_db,
                                   args=(), trigger='cron', day=f'*/{days}',
                                   start_date='2021-10-1', max_instances=1, replace_existing=True)
        except Exception as e:
            self.app.logger.error(
                f"An error occurred while adding a task to clean up products logs regularly: {e}")

    def _update_spex_resources(self, ):
        from app.libs import scheduled_update
        if not self.check_server():
            return

        with self.scheduler.app.app_context():
            scheduled_update()

    def update_spex_resources(self, ):
        try:
            self.scheduler.add_job(name='update spex resources', id='100006', func=self._update_spex_resources,
                                   args=(), trigger='cron', day_of_week='sat', hour=1, max_instances=1,
                                   replace_existing=True)
        except Exception:
            self.app.logger.error(
                f"An error occurred while adding a task to update spex resources: {traceback.format_exc()}")

    def _clean_old_dependency(self, ):
        from app.libs import clean_old_dependency
        if not self.check_server():
            return

        with self.scheduler.app.app_context():
            err = clean_old_dependency.queue(timeout=24 * 60 * 60)
            if err:
                self.app.logger.error(err)

    def clean_old_dependency(self, frequency=1):
        try:
            self.scheduler.add_job(name='clean old dependency', id='100007', func=self._clean_old_dependency,
                                   args=(),
                                   trigger='cron', day=f'*/{frequency}', start_date='2021-10-1',
                                   max_instances=1, replace_existing=True)
        except Exception as e:
            self.app.logger.error(
                f"An error occurred while adding a task to clean up logs regularly: {e}")

    def _sync_from_cap(self, ):
        from app.libs import sync_product_line, sync_member
        if not self.check_server():
            return

        with self.scheduler.app.app_context():
            sync_product_line()
            sync_member()

    def sync_from_cap(self, frequency=1):
        try:
            self.scheduler.add_job(name='sync from cap', id='100008', func=self._sync_from_cap,
                                   args=(),
                                   trigger='cron', day=f'*/{frequency}', start_date='2021-10-1',
                                   max_instances=1, replace_existing=True)
        except Exception as e:
            self.app.logger.error(
                f"An error occurred while adding a task to clean up logs regularly: {e}")


MYASP = None


def init_aps(app, suite_cls, env):
    global MYASP
    MYASP = MyScheduler(app, env)
    app.logger.info(f'To init Scheduler...')
    MYASP.init_task(suite_cls)
    MYASP.add_debug_task()
    MYASP.clean_old_logs()
    MYASP.clean_products_logs()
    MYASP.clean_db_scheduler()
    MYASP.stat_job()
    MYASP.update_spex_resources()
    MYASP.clean_old_dependency()
    # MYASP.sync_from_cap()
    MYASP.show_tasks()
    app.logger.info(f'Init Scheduler done!')
