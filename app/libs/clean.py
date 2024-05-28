# -*- coding: utf-8 -*-
# @Time    : 2022/4/12
# @Author  : Jiaxin Chen

import datetime
import os
import traceback

from flask import current_app

from app.commons import myrq, utils, db
from app.models import Run_Log_Type, Env, HcTemplate, HcPlanResult, SuiteResult, \
    env_schema, hc_templates_schema, hc_plan_result_schema, CaseResult, caseresults_schema, suiteresult_schema


def _clean_or_not(file_path, days):
    current_time = datetime.datetime.now()
    delta = datetime.timedelta(days=days)
    # Get the time when the case_result folder was generated
    r_time = datetime.datetime.fromtimestamp(os.path.getctime(file_path))

    # If the log was generated before the specified time, delete
    if r_time < (current_time - delta):
        if os.path.isdir(file_path):
            ret, outputs = utils.send_cmd(
                f'rm -rf {file_path}', False)
        else:
            ret, outputs = utils.send_cmd(
                f'rm -f {file_path}', False)

        if ret:
            current_app.logger.info(
                f"{file_path} has existed for more than {days} days, delete it!")
            record_deleted_logs(file_path)
        else:
            current_app.logger.info(
                f"Some problems were encountered when cleaning up the files: {outputs}")


def record_deleted_logs(file):
    try:
        record_file = os.path.join(current_app.instance_path, 'deleted_records.txt')
        context = datetime.datetime.now().strftime('%Y-%m-%d') + ': ' + file

        with open(record_file, encoding="utf-8", mode='a+') as f:
            f.write(f'{context}\n')

    except Exception as e:
        current_app.logger.error('Record failed! ' + str(e))


def record_deleted_database(data):
    try:
        record_file = os.path.join(current_app.instance_path, 'deleted_database_records.txt')
        context = datetime.datetime.now().strftime('%Y-%m-%d') + ': ' + data

        with open(record_file, encoding="utf-8", mode='a+') as f:
            f.write(f'{context}\n')

    except Exception as e:
        current_app.logger.error('Record failed! ' + str(e))


@myrq.job('clean')
def clean_logs(days, platform=False):
    """
    Clean up logs that have existed for more than the specified length of time.
    """

    base_dir = os.path.join(
        current_app.instance_path, current_app.config['LOG_FOLDER'])
    case_exec_log_dir = os.path.join(base_dir, Run_Log_Type["case"])
    suite_exec_log_dir = os.path.join(base_dir, Run_Log_Type["suite"])
    hc_log_dir = os.path.join(base_dir, 'health_check')
    postwomen_log_dir = os.path.join(base_dir, 'postwomen')
    try:
        if platform:
            # Clearing the platform's log
            for path in [case_exec_log_dir, suite_exec_log_dir, hc_log_dir, postwomen_log_dir]:
                if os.path.exists(path):
                    for log in os.listdir(path):
                        _clean_or_not(os.path.join(path, log), days)

        else:
            # Get the log directory path of all cases
            cases_dir = [
                os.path.join(project_dir, case_file)
                for project_dir in [
                    os.path.join(base_dir, project_file)
                    for project_file in os.listdir(base_dir)
                    if project_file.isdigit()
                ]
                if os.path.isdir(project_dir)
                for case_file in os.listdir(project_dir)
            ]

            for case_dir in cases_dir:
                # Get the log directory path of all case_results
                results_dir = [os.path.join(case_dir, result_file) for result_file in
                               os.listdir(case_dir)] if os.path.isdir(case_dir) else []
                for result in results_dir:
                    _clean_or_not(result, days)

        current_app.logger.info(f"All expired logs are cleaned up.")
    except Exception as e:
        current_app.logger.info(
            f"Some problems were encountered when cleaning up the files: {e}")


@myrq.job('clean')
def clean_products_folder(days=7):
    base_dir = os.path.join(current_app.instance_path,
                            current_app.config['PRODUCT_FOLDER'])
    need_delete = []
    # del_folder_name = ['logs', 'log', 'report', 'reports']
    del_folder_name = ['logs', 'reports']

    def find_logs(file_path):
        current_app.logger.info(f"Current path is: {file_path}")
        for file in os.listdir(file_path):
            if file == '.git':
                continue
            new_path = os.path.join(file_path, file)
            if os.path.isdir(new_path):
                if file in del_folder_name:
                    need_delete.append(new_path)
                else:
                    find_logs(new_path)
            else:
                continue

    try:
        find_logs(base_dir)

        for file in need_delete:
            _clean_or_not(file, days)

        current_app.logger.info(f"Products logs are cleaned up.")
    except Exception as e:
        current_app.logger.error(
            f"Some problems were encountered when cleaning up the files: {e}")


@myrq.job('clean')
def clean_old_dependency():
    def _sorted_func(dir_name):
        k = "szqa_pips_"
        if dir_name.find(k) < 0:
            return 0
        timestamp = dir_name.replace("szqa_pips_", "")
        try:
            timestamp = int(timestamp)
        except Exception:
            current_app.logger.error(f"Sorted error for {dir_name}")
            timestamp = 0
        return timestamp

    try:
        szqa_dependency_dirs = [d for d in os.listdir(current_app.config["DEPENDENCY_PATH"])
                                if d.find(current_app.config["SZQA_DEPENDENCY"]) >= 0]
        sort_list = sorted(szqa_dependency_dirs, key=lambda x: _sorted_func(x), reverse=True)
        if len(sort_list) > 1:
            for path in sort_list[1:]:
                full_path = os.path.join(current_app.config["DEPENDENCY_PATH"], path)
                _clean_or_not(full_path, 1)

        current_app.logger.info(f"Old dependency are cleaned up.")

    except Exception:
        current_app.logger.error(
            f"Some problems were encountered when cleaning up old dependency: {traceback.format_exc()}")


@myrq.job('clean')
def clean_database():
    try:
        current_date = datetime.datetime.now()
        delta = datetime.timedelta(days=90)

        db_list = [(Env, env_schema), (HcTemplate, hc_templates_schema),
                   (HcPlanResult, hc_plan_result_schema), (CaseResult, caseresults_schema),
                   (SuiteResult, suiteresult_schema)]
        for index, database in enumerate(db_list):
            if index < 2:
                delete_data = db.session.query(database[0]).filter(
                    database[0].updated_time < current_date - delta, database[0].deleted == True).all()
            elif database[0] in [CaseResult, SuiteResult]:
                delete_data = db.session.query(database[0]).filter(database[0].debug_mode == True, database[
                    0].updated_time < current_date - datetime.timedelta(days=3)).all()
                # delete debug mode case/suite result log files
                base_dir = os.path.join(
                    current_app.instance_path, current_app.config['LOG_FOLDER'])
                if database[0] == CaseResult:
                    debug_mode_case_results = [str(data.id) for data in delete_data if data.debug_mode == True]
                    cases_dir = [
                        os.path.join(project_dir, case_file)
                        for project_dir in [
                            os.path.join(base_dir, project_file)
                            for project_file in os.listdir(base_dir)
                            if project_file.isdigit()
                        ]
                        if os.path.isdir(project_dir)
                        for case_file in os.listdir(project_dir)
                    ]

                    for case_dir in cases_dir:
                        # Get the log directory path of all case_results
                        results_dir = [os.path.join(case_dir, result_file) for result_file in
                                       os.listdir(case_dir) if result_file in debug_mode_case_results] \
                                        if os.path.isdir(case_dir) else []
                        for result in results_dir:
                            _clean_or_not(result, 3)

                else:
                    debug_mode_suite_results = [str(data.id) for data in delete_data if data.debug_mode == True]
                    suite_exec_log_dir = os.path.join(base_dir, Run_Log_Type["suite"])
                    if os.path.exists(suite_exec_log_dir):
                        for log in os.listdir(suite_exec_log_dir):
                            if log.split(".log")[0] in debug_mode_suite_results:
                                _clean_or_not(os.path.join(suite_exec_log_dir, log), 3)

            else:
                delete_data = db.session.query(database[0]).filter(
                    database[0].deleted == True).order_by(
                    database[0].updated_time.desc())[6:]

            for data in delete_data:
                db.session.delete(data)

            if delete_data:
                delete_data = database[1].dump(delete_data, many=True)
                record_deleted_database(database[0].__name__ + ' ' + str(delete_data))

        param = [SuiteResult.status == 'running', SuiteResult.updated_time <
                 current_date - datetime.timedelta(days=7)]
        result = db.session.query(SuiteResult).filter(*param).all()
        for data in result:
            data.status = 'timeout'

        db.session.commit()
        db.session.close()

    except Exception as e:
        current_app.logger.info(
            f"Some problems were encountered when cleaning up the DB: {e}")
