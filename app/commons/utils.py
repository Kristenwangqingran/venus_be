# -*- coding: utf-8 -*-
# @Time    : 2020-08-04
# @Author  : GongXun


import re
import time
import subprocess
import datetime
import os
import traceback
from func_timeout import func_set_timeout
from flask import current_app
import json
from urllib.parse import unquote
import calendar


def get_files_br_re(apath, restr):
    file_list = []
    if os.path.exists(apath):
        pass
    else:
        return file_list

    all_things = os.listdir(apath)
    for item in all_things:
        if not item.startswith('.') and os.path.isfile(os.path.join(apath, item)):
            if re.match(restr, item):
                file_list.append(os.path.join(apath, item))
        elif not item.startswith('.') and os.path.isdir(os.path.join(apath, item)):
            file_list += get_files_br_re(os.path.join(apath, item), restr)

        else:
            continue
    return file_list


def get_current_timestr():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


def del_id_none(adict):
    if not isinstance(adict, (dict,)):
        return adict

    dst_dict = {}
    for k, v in adict.items():
        if v is None:
            continue
        elif isinstance(v, (dict,)):
            dst_dict[k] = del_id_none(v)
        else:
            dst_dict[k] = v

    return dst_dict


def del_empty(adict):
    if not isinstance(adict, (dict,)):
        return adict

    dst_dict = {}
    for k, v in adict.items():
        if not v:
            continue
        elif isinstance(v, (dict,)):
            dst_dict[k] = del_empty(v)
        else:
            dst_dict[k] = v

    return dst_dict


def send_cmd(CMD, init_done=True):
    if init_done:
        current_app.logger.info(f"To run: {CMD}")
    child = subprocess.Popen(
        f"{CMD}",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    outputs, _ = child.communicate()
    retcode = child.poll()
    outputs = outputs.decode(
        'utf-8') if isinstance(outputs, (bytes,)) else outputs
    if not retcode:
        return True, outputs
    else:
        return False, outputs


def run_cmd_record_log(cmd, dir, log_stream=subprocess.PIPE, env=None, timeout=1800, prefix=""):
    errmsg = ''
    returncode = 0
    if not prefix:
        prefix = ""

    t0 = time.time()
    current_app.logger.info(
        f'{prefix}Call linux cmd: {cmd} in dir: {dir}')
    kwargs = {
        "shell": True,
        "stdout": log_stream,
        "stderr": log_stream,
        "cwd": dir,
    }
    if env:
        kwargs['env'] = env

    try:
        new_f = func_set_timeout(timeout)(subprocess.Popen)
        proc = new_f(cmd, **kwargs)
        returncode = proc.wait()

    except Exception as err:
        current_app.logger.error(f"{prefix}{traceback.extract_tb()}")
        errmsg = str(err)
        print(errmsg, file=log_stream)

    t1 = time.time()
    return returncode, errmsg, t1 - t0


def convert_list_to_dict(origin_list):
    return {
        item['name']: item.get('value')
        for item in origin_list
    }


def convert_x_www_form_urlencoded_to_dict(post_data):
    if isinstance(post_data, str):
        converted_dict = {}
        for k_v in post_data.split("&"):
            try:
                key, value = k_v.split("=")
            except ValueError:
                raise Exception(
                    "Invalid x_www_form_urlencoded data format: {}".format(
                        post_data)
                )
            converted_dict[key] = unquote(value)
        return converted_dict
    else:
        return post_data


def getFirstAndLastDay(year, month):
    # 获取当前月的第一天的星期和当月总天数
    _, monthCountDay = calendar.monthrange(year, month)
    # 获取当前月份第一天
    firstDay = datetime.date(year, month, day=1)
    # 获取当前月份最后一天
    lastDay = datetime.date(year, month, day=monthCountDay)
    # 返回第一天和最后一天
    return firstDay, lastDay


def ensure_dirname(astr):
    return re.sub(r'[^\w]+', '_', str(astr))


def rmdirs(top):
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))

        for name in dirs:
            os.rmdir(os.path.join(root, name))

    os.rmdir(top)


def json_merge(key, j1, j2):
    j1k = j1.get(key, None)
    j2k = j2.get(key, None)

    if not j1k:
        return j2k
    elif not j2k:
        return j1k
    else:
        if type(j1k) == type(j2k) and type(j1k) in (list, tuple, dict):

            if isinstance(j1k, (dict,)):
                tmp_ret = dict(j2k, **j1k)
                ret = {}
                for k, v in tmp_ret.items():
                    if isinstance(v, (str, bytes)) and v == '0XMissing':
                        continue
                    else:
                        ret[k] = v

                return ret
            else:
                return j1k + j2k
        else:
            raise ValueError(f"key: {key} type wrong or mismatch!")


def make_serializable(obj):
    if isinstance(obj, (bytes,)):
        return 'bytes data...'
    elif isinstance(obj, (list, tuple)):
        ret = []
        for item in obj:
            ret.append(make_serializable(item))
        return ret

    elif isinstance(obj, (dict,)):
        ret = {}
        for k, v in obj.items():
            ret[k] = make_serializable(v)
        return ret

    elif isinstance(obj, (datetime.datetime, datetime.timedelta)):
        return repr(obj)
    else:
        return str(obj)


def convert_to_dictstr(src):
    src = make_serializable(src)
    try:
        if isinstance(src, dict):
            return json.dumps(
                src,
                sort_keys=False,
                indent=4,
                separators=(',', ': '),
                ensure_ascii=False)

        elif isinstance(src, (list, tuple)):
            return json.dumps(
                src,
                sort_keys=True,
                indent=4,
                separators=(',', ': '),
                ensure_ascii=False)

        elif isinstance(src, str):
            return json.dumps(
                json.loads(src),
                sort_keys=True,
                indent=4,
                separators=(',', ': '),
                ensure_ascii=False)

        elif isinstance(src, bytes):
            return json.dumps(
                json.loads(src.decode('utf-8')),
                sort_keys=True,
                indent=4,
                separators=(',', ': '),
                ensure_ascii=False)

        else:
            return src
    except Exception as err:
        return src


def get_result_id(hd, record_id, timeout):
    ret = {}
    timeout *= 10
    while timeout:
        if hd.exists(record_id):
            result_byte = hd.get(record_id)
            ret = json.loads(result_byte) if result_byte else {}
            break

        timeout -= 1
        time.sleep(0.1)
    return ret


class Pager:
    def __init__(self, page, per_page, total):
        try:
            page = int(page)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        self.page = page
        self.per_page = per_page
        total_page, tmp = divmod(total, self.per_page)
        if tmp:
            total_page += 1
        self._total_page = total_page

    @property
    def start(self):
        return (self.page-1)*self.per_page

    @property
    def end(self):
        return self.page*self.per_page

    @property
    def total_page(self):
        return self._total_page


def every_to_string(**kwargs):
    r = {}
    for k, v in kwargs.items():
        r[k] = str(convert_to_dictstr(v))

    return r
