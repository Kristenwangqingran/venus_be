# -*- coding: utf-8 -*-
# @Time    : 2020/8/24
# @Author  : GongXun
import datetime
import traceback

from flask import request, current_app

import app.commons.utils as utils
from app.commons import ma, resp_return
from app.models import CaseResult, Project, Casesuite, SuiteResult, suiteresult_schema, caseresult_schema, Case
from app.resources import BaseResource


class RequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    status = ma.String()
    project_id = ma.Integer()
    casesuite_id = ma.Integer()
    casesuite_name = ma.String()
    reverse = ma.Boolean(default=False)
    author = ma.String()
    is_manual = ma.Boolean(default=False)
    pfb = ma.String()


class SuiteResultsView(BaseResource):
    def get(self, ):
        try:
            query_args = RequestArgs().dump(request.args)
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        project_id = query_args.pop('project_id', None)
        reverse = query_args.pop('reverse', None)
        is_manual = query_args.pop('is_manual', False)

        param = self.get_common_params(query_args, SuiteResult)
        query = SuiteResult.query.filter(*param)
        query = query.join(Casesuite, SuiteResult.casesuite_id ==
                           Casesuite.id)

        if project_id:
            query = query.filter(Casesuite.project_id == project_id)

        if is_manual:
            query = query.filter(Casesuite.is_manual == is_manual)
        else:
            query = query.filter((Casesuite.is_manual == is_manual) | (
                Casesuite.is_manual == None))

        suiteresults = query.order_by(SuiteResult.updated_time.desc()).paginate(
            page=query_args["page"], per_page=query_args["per_page"], error_out=False)
        result = suiteresult_schema.dump(suiteresults.items, many=True)
        for suite in result:
            suite['is_app'] = True
            extra = suite.pop('extra')
            if extra and extra.get('cases'):
                cases = [int(case_id) for case_id in extra['cases'].keys()]
                query = Case.query.filter(Case.id.in_(cases)).all()
                for case in query:
                    if case.type not in current_app.config['TOPO_MAP'] or \
                            current_app.config['TOPO_MAP'][case.type] != 'app':
                        suite['is_app'] = False
                        break

        if reverse:
            result.reverse()

        return resp_return('QUERY_SUCCESS', result, suiteresults.total)

    def post(self):
        try:
            json_data = request.get_json()
        except Exception as err:
            return resp_return('PARAM_INVALID', new_msg=f'{str(err.args)}')

        if not json_data:
            return resp_return('JSON_ERROR')

        try:
            SuiteResult.post_check(json_data)
            suiteresult = suiteresult_schema.load(utils.del_id_none(json_data))
            suiteresult.save()

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
        else:
            return resp_return('CREATE_SUCCESS')


class SuiteResultRequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    author = ma.String()
    group = ma.String()
    status = ma.String()
    case_name = ma.String()
    reason = ma.String()


class SuiteResultView(BaseResource):
    def get(self, id):
        try:
            query_args = SuiteResultRequestArgs().dump(request.args)
            page, per_page = query_args["page"], query_args["per_page"]
            suiteresult = SuiteResult.query.get(id)
            if suiteresult:
                result = suiteresult_schema.dump(suiteresult)
                result.pop('extra')
                return resp_return('QUERY_SUCCESS', result)

            else:
                return resp_return('NOFOUND_ERROR', new_msg='No corresponding suiteresult found!')

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))

    def put(self, id):
        json_data = request.get_json()
        # carrier = request.headers
        # tracer = config.init_tracer_for_webserver("")
        # span_context = tracer.extract(opentracing.Format.HTTP_HEADERS, carrier)
        # span = tracer.start_span("report_server", child_of=span_context)
        # span.log_kv({'event': 'update report result ', 'value': "success"})
        if not json_data:
            return resp_return('JSON_ERROR')

        suiteresult = SuiteResult.query.filter_by(id=id).first()
        # span.finish()
        if suiteresult:
            try:
                self.common_put(suiteresult, json_data)

            except Exception as err:
                current_app.logger.error(traceback.format_exc())
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('UPDATE_SUCCESS')
        else:
            # span.finish()
            return resp_return('NOFOUND_ERROR', new_msg='No corresponding suiteresult found!')

    def delete(self, id):
        suiteresult = SuiteResult.query.filter_by(id=id).first()
        if suiteresult:
            try:
                suiteresult.rdelete()
            except Exception as err:
                return resp_return('DB_ERROR', new_msg=str(err))
            else:
                return resp_return('DELETE_SUCCESS')
        else:
            return resp_return('NOFOUND_ERROR', new_msg='No corresponding suiteresult found!')


class AppReportResultRequestArgs(ma.Schema):
    page = ma.Integer(default=1)
    per_page = ma.Integer(default=20)
    device_result = ma.String()
    brand = ma.String()
    os_version = ma.String()
    screen = ma.String()
    name = ma.String()


class AppSuiteResultView(BaseResource):
    def get(self, id):
        try:
            query_args = AppReportResultRequestArgs().dump(request.args)
            page = query_args.get('page', 1)
            per_page = query_args.get('per_page', 20)
            device_result_filter = query_args.get('device_result', None)
            brand_filter = query_args.get('brand', None)
            os_version_filter = query_args.get('os_version', None)
            screen_filter = query_args.get('screen', None)
            name_filter = query_args.get('name', None)

            suite_result = SuiteResult.query.filter(
                SuiteResult.id == id).first()
            device_info = suite_result.device_info if suite_result.device_info else {}
            device_quantity, passed_num, failed_num, not_tested_num = 0, 0, 0, 0
            app_name = ''
            app_size = ''
            app_version = ''
            failed_device_details = {}
            devices_info_list = []
            failed_branches, failed_rams, failed_os_versions = {}, {}, {}
            for k, v in device_info.items():
                case_results = CaseResult.query.filter(
                    CaseResult.id.in_(v)).all()
                if not case_results:
                    current_app.logger.info(
                        f'Device_id: {k} has no case result!')
                    continue
                device_failed_case = 0
                the_device_info = case_results[0].device_info
                if not the_device_info:
                    current_app.logger.info(
                        f'Device_id: {k} missed information in case result!')
                    continue
                if not app_name and case_results[0].app_info:
                    app_name = case_results[0].app_info.get('app_name', '')
                    app_size = case_results[0].app_info.get('app_size', '')
                    app_version = case_results[0].app_info.get('version', '')

                device_result = 'Passed'
                failed_device = False
                not_tested_flag = True
                has_pending_case = False
                for case_result in case_results:
                    if case_result.status == 'pending':
                        has_pending_case = True
                        continue
                    not_tested_flag = False
                    if case_result.status != 'pass':
                        device_failed_case += 1
                        failed_device = True

                if not_tested_flag:
                    not_tested_num += 1
                elif failed_device:
                    failed_num += 1
                    failed_brand = the_device_info['brand']
                    failed_ram = the_device_info['ram']
                    failed_os_version = the_device_info['os_version']

                    failed_branches.setdefault(failed_brand, 0)
                    failed_branches[failed_brand] += 1
                    failed_rams.setdefault(failed_ram, 0)
                    failed_rams[failed_ram] += 1
                    failed_os_versions.setdefault(failed_os_version, 0)
                    failed_os_versions[failed_os_version] += 1

                else:
                    passed_num += 1
                device_quantity += 1

                if failed_device:
                    device_result = 'Failed'
                elif has_pending_case:
                    device_result = 'Pending'

                if (device_result_filter and device_result not in device_result_filter) or \
                        (brand_filter and the_device_info['brand'] not in brand_filter) or \
                        (os_version_filter and the_device_info['os_version'] not in os_version_filter) or \
                        (screen_filter and the_device_info['screen'] not in screen_filter) or \
                        (name_filter and the_device_info['name'] not in name_filter):
                    continue

                device_show_name = the_device_info.get(
                    'show_name', the_device_info['name'])
                device = {
                    "device_show_name": device_show_name,
                    "device_id": k,
                    "device_status": 'Complete' if not has_pending_case else 'Running',
                    "device_result": device_result,
                    "brand": the_device_info['brand'],
                    "name": the_device_info['name'],
                    "model": the_device_info['model'],
                    "os": the_device_info['os'],
                    "os_version": the_device_info['os_version'],
                    "screen": the_device_info['screen'],
                    "failed_total_cases": f'{device_failed_case}/{len(case_results)}'
                }
                devices_info_list.append(device)

            sorted_branches = sorted(
                failed_branches.items(), key=lambda x: x[1], reverse=True)
            sorted_rams = sorted(failed_rams.items(),
                                 key=lambda x: x[1], reverse=True)
            sorted_os = sorted(failed_os_versions.items(),
                               key=lambda x: x[1], reverse=True)
            temp = [(sorted_branches, 'brands'),
                    (sorted_rams, 'rams'), (sorted_os, 'os_version')]
            for item in temp:
                failed_device_details.setdefault(item[1], [])
                for info in item[0]:
                    failed_device_details[item[1]].append({
                        "name": info[0],
                        "number": info[1],
                        "value": '{:.1%}'.format(info[1] / failed_num)
                    })

            res_result = {
                "suite_result_info": {
                    "app_name": app_name,
                    "app_size": app_size,
                    "app_version": app_version,
                    "suite_result_id": suite_result.id,
                    "user": suite_result.runner,
                    "status": suite_result.status,
                    "start_time": suite_result.created_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": suite_result.updated_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "device_quantity": device_quantity,
                    "passed_num": passed_num,
                    "failed_num": failed_num,
                    "not_tested_num": not_tested_num,
                    "failed_device_details": failed_device_details
                },
                "device_tab": {
                    "devices_info_list": devices_info_list[(int(page) - 1) * int(per_page): int(page) * int(per_page)]
                }
            }
            return resp_return('QUERY_SUCCESS', res_result, len(devices_info_list))

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))


class AppSuiteResultDeviceDetail(BaseResource):
    def get(self, suite_result_id, device_id):
        try:
            args = request.args.to_dict()
            page = args.get('page', 1)
            per_page = args.get('per_page', 10)
            suite_result = SuiteResult.query.filter(
                SuiteResult.id == suite_result_id).first()
            device_info = suite_result.device_info
            case_result_list = device_info[device_id]
            case_results = CaseResult.query.filter(CaseResult.id.in_(case_result_list)).order_by(
                CaseResult.updated_time.desc()).paginate(page=int(page), per_page=int(per_page), error_out=False)

            app_info = case_results.items[0].app_info
            device_info = case_results.items[0].device_info
            app_detail = {
                "file_name": app_info.get('file_name', ''),
                "version": app_info.get('version', ''),
                "app_size": app_info.get('app_size', ''),
                "min_sdk_level": app_info.get('min_sdk_level', ''),
                "target_sdk_level": app_info.get('target_sdk_level', ''),
                "download_address": app_info.get('download_address', ''),
                "package_name": app_info.get('package_name', '')
            }
            device_detail = {
                "name": device_info.get('name', ''),
                "id": device_info.get('id', ''),
                "model": device_info.get('model', ''),
                "os_version": device_info.get('os_version', ''),
                "cpu": device_info.get('cpu', ''),
                "gpu": device_info.get('gpu', ''),
                "ram": device_info.get('ram', ''),
                "rom": device_info.get('rom', ''),
                "api_level": device_info.get('api_level', ''),
                "rooted": device_info.get('rooted', ''),
                "screen": device_info.get('screen', '')
            }
            case_results_info = []
            for case_result in case_results.items:
                temp = {
                    "case_result_id": case_result.id,
                    "case_name": case_result.case_name,
                    "case_result": case_result.status,
                    "start_time": case_result.created_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": (case_result.created_time + datetime.timedelta(seconds=case_result.duration)).strftime(
                        '%Y-%m-%d %H:%M:%S'),
                    "duration": f'{round(case_result.duration, 1)}s',
                }
                case_results_info.append(temp)

            res_result = {
                "app_detail": app_detail,
                "device_detail": device_detail,
                "case_result_list": case_results_info
            }
            return resp_return('QUERY_SUCCESS', res_result, case_results.total)

        except Exception as err:
            current_app.logger.error(traceback.format_exc())
            return resp_return('COMMON_ERROR', new_msg=str(err))
