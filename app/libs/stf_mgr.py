# -*- coding: utf-8 -*-
# @Time    : 2022-03-08
# @Author  : GongXun

import time
import os
import random
import json
import requests
import traceback
from threading import Lock
from urllib import parse
from flask import current_app
from app.commons import MyRedis, MyLogger
from app.commons.config import get_config


current_env = get_config()


class STFMgr:

    _devices_url = parse.urljoin(
        current_env.STF_HOST, current_env.STF_DEVICES)
    _device_lock_url = parse.urljoin(
        current_env.STF_HOST, current_env.STF_USER_DEVICE)
    MG = MyLogger('stfmgr', path=os.path.join(
        'instance', current_env.LOG_FOLDER, 'stfmgr.log'))

    def __init__(self, ):
        '''
        _device_info: {
            "node_1": {
                "Android": {
                    "type1": [{}, {}],
                    "type2": [{}, {}]
                }
            }
        }
        '''
        self._lock = Lock()
        if os.environ.get("APS_CONFIG") == 'true':
            self.update()

    @property
    def _device_info(self):
        info = {}
        result_hd = MyRedis(
            current_env.REDIS['URL_FOR_UE'])
        bytesinfo = result_hd.get('_device_info')
        if bytesinfo:
            info = json.loads(bytesinfo)

        result_hd.disconnect()
        return info

    def update(self):

        def _get_devices_info():
            devices = []
            errmsg = ''
            try:
                resp = requests.get(
                    self._devices_url, headers=current_env.STF_HEADERS, timeout=5)
                if resp.status_code != 200:
                    errmsg = f"STF server status_code: {resp.status_code}"
                else:
                    datas = resp.json()
                    if datas.get('code') == 0:
                        devices = datas.get("data", {}).get("items", [])
                        self.MG.info(f"get devices from STF: {devices}")
                    else:
                        errmsg = f"STF data error: code={datas.get('code')}, description={datas.get('description')}"

            except Exception as err:
                self.MG.error(traceback.format_exc())
                errmsg = str(err)

            if errmsg:
                self.MG.error(errmsg)

            return devices

        def _classify_devices(devices):
            temp_device_info = {}
            for device in devices:
                device_node = device.get('node', 'super-node')
                device_platform = device.get('platform', 'Android')
                device_type = f"{device.get('marketName')} <-> {device.get('model')} <-> {device.get('version')}"

                if device_node not in temp_device_info:
                    temp_device_info[device_node] = {}
                if device_platform not in temp_device_info[device_node]:
                    temp_device_info[device_node][device_platform] = {}
                if device_type not in temp_device_info[device_node][device_platform]:
                    temp_device_info[device_node][device_platform][device_type] = [
                    ]
                temp_device_info[device_node][device_platform][device_type].append(
                    device)
            return temp_device_info

        self._lock.acquire()
        try:
            _device_list = _get_devices_info()
            device_info = _classify_devices(_device_list)
            result_hd = MyRedis(
                current_env.REDIS['URL_FOR_UE'])
            result_hd.set('_device_info', json.dumps(device_info))
            self.MG.info(f"update device info to: {device_info}")
            result_hd.disconnect()
        except Exception:
            self.MG.error(traceback.format_exc())
        self._lock.release()

    def get_device_types(self, platform):
        self._lock.acquire()
        devices_types = [item for node in self._device_info for k,
                         v in self._device_info[node].items() if k == platform for item in v]
        self._lock.release()

        result = []
        for device_type in devices_types:
            result.append({
                "value": device_type,
                "description": device_type
            })
        return result

    def has_devices(self, node, device_types):
        ok = True
        self._lock.acquire()
        for platform, device_type in device_types:
            _tmp_infos = self._device_info.get(node, {}).get(platform, {})
            if _tmp_infos.get(device_type):
                continue
            else:
                ok = False
                current_app.logger.warn(
                    f"node: {node}, canot match: {platform, device_type}")
                current_app.logger.warn(
                    f"_device_info: {self._device_info}, _device_info[{node}]: {self._device_info.get(node, {})}, _device_info[{node}][{platform}]: {self._device_info.get(node, {}).get(platform, {})}")
                break
        self._lock.release()
        return ok

    @classmethod
    def _lock_device(cls, serial, timeout=1):
        device_url = ''
        errmsg = ''
        cls.MG.info(f"to lock device: {serial}...")
        while timeout:
            resp = requests.post(
                cls._device_lock_url, json={"udid": serial}, headers=current_env.STF_HEADERS, timeout=5)
            if resp.status_code != 200:
                errmsg = f"lock device {serial} failed: STF server status code error {resp.status_code}"
            else:
                errmsg = None
                datas = resp.json()
                if datas.get('code') == 0 and datas.get('data', {}).get('url'):
                    cls.MG.info(
                        f"lock device {serial} success!")

                    device_url = datas['data']['url']
                    break
                else:
                    errmsg = f"lock device {serial} failed: {datas}"

            timeout -= 1
            time.sleep(1)

        if errmsg:
            cls.MG.error(errmsg)
        return device_url

    @classmethod
    def release_device(cls, serial):
        errmsg = None
        resp = requests.delete(
            cls._device_lock_url, json={"udid": serial}, headers=current_env.STF_HEADERS, timeout=5)
        if resp.status_code != 200:
            errmsg = f"release device {serial} failed: STF server status code error {resp.status_code}"

        else:
            datas = resp.json()
            if datas.get('code') == 0:
                cls.MG.info(
                    f"release device {serial} success!")
            else:
                errmsg = f"release device {serial} failed: {datas}"
        if errmsg:
            cls.MG.error(errmsg)

    def acquire_devices(self, node, device_types):
        ok = True
        locked_devices = []
        self._lock.acquire()
        current_app.logger.warn(
            f"To acquire device from Node: {node} for: {device_types}")
        for platform, device_type in device_types:
            current_app.logger.warn(
                f"To acquire device from {node} for {platform} {device_type}")
            _tmp_infos = self._device_info.get(node, {}).get(platform, {})
            _devices = _tmp_infos.get(device_type)
            if _devices:
                random.shuffle(_devices)
                for device in _devices:
                    current_app.logger.warn(
                        f"To lock device: {device}")
                    device_url = self._lock_device(device['udid'])
                    if device_url:
                        current_app.logger.warn(
                            f"lock device success: {device}")
                        locked_devices.append({
                            "type": device_type,
                            "udid": device['udid'],
                            "url": device_url,
                            "info": device
                        })
                        break
                    else:
                        current_app.logger.error(
                            f"lock device fail: {device}, result is: {device_url}")
                        ok = False
                        break
            else:
                current_app.logger.warn(
                    f"Node: {node} has no device for platform: {platform}, device_type: {device_type}")
                ok = False
                break

        if not ok:
            self.release_devices([item['udid'] for item in locked_devices])
            locked_devices = []

        self._lock.release()
        return locked_devices

    def release_devices(self, locked_devices):
        for device_udid in locked_devices:
            self.release_device(device_udid)

    def all_infos(self):
        return self._device_info
