# -*- coding: utf-8 -*-
# @Time    : 2020-08-04
# @Author  : GongXun


RETURN = {
    # success
    'COMMON_OK':               {"code": 0, "message": "success."},
    'QUERY_SUCCESS':           {"code": 0, "message": "query success."},
    'CREATE_SUCCESS':          {"code": 0, "message": "create data success."},
    'UPDATE_SUCCESS':          {"code": 0, "message": "update data success."},
    'DELETE_SUCCESS':          {"code": 0, "message": "delete data success."},
    'EXECUTE_OK':              {"code": 0, "message": "execute success."},
    'CANCELED_OK':             {"code": 0, "message": "cancel success."},
    'GITPULL_OK':              {"code": 0, "message": "git pull success."},
    'UPDATE_STEP_SUCCESS':     {"code": 0, "message": "update step success."},
    'CLONE_SUCCESS':           {"code": 0, "message": "clone API success."},
    'SKIP':                    {"code": 0, "message": "skipped"},

    # param error
    'COMMON_ERROR':            {"code": 400, "message": "request err!"},
    'JSON_ERROR':              {"code": 400, "message": "JSON data err!"},
    'PARAM_INVALID':           {"code": 422, "message": "invalid arg!"},
    'NOFOUND_ERROR':           {"code": 404, "message": "resource not exists!"},
    'UNIQUE_ERROR':            {"code": 409, "message": "resource already exists!"},
    'TASK_ERROR':              {"code": 400, "message": "task status err!"},
    'RUN_ERROR':               {"code": 400, "message": "task execute failed!"},
    'SUITE_EMPTY':             {"code": 400, "message": "test suite empty!"},
    'SCRIPT_ERR':              {"code": 400, "message": "script import failed!"},
    'PARAMS_ERR':              {"code": 400, "message": "get params failed!"},
    'GITPULL_ERR':             {"code": 400, "message": "executor update failed!"},
    'GITPULL_ONGOING':         {"code": 400, "message": "executor update is ongoing!"},

    # task in the queue
    'TASK_IN_QUEUE':            {"code": 430, "message": "Tasks are queued and awaiting execution, please be patient."},

    # add for vode
    'ALREADY_VOTED':           {"code": 10001, "message": "You already voted!"},
    'VOTING':                  {"code": 10002, "message": "There is a bug under voting now, need stop it first!"},
    'VOTE_END':                {"code": 10003, "message": "Vote already ended!"},
    'VOTE_NOFOUND':            {"code": 10004, "message": "Vote no found!"},

    # file error
    'FILE_MISSING':            {"code": 400, "message": "file missing!"},
    'FILE_EMPTY':              {"code": 400, "message": "file empty!"},
    'FILE_NOT_ALLOWED':        {"code": 400, "message": "file format not allowed!"},
    'FILE_HANDLE_ERROR':       {"code": 400, "message": "file handle error"},

    # internal error
    'SERVER_ERROR':            {"code": 500, "message": "internal err!"},
    'DB_ERROR':                {"code": 500, "message": "DB err!"},
    'SERVER_AVALIABLE':        {"code": 503, "mseeage": "server avaliable!"},

    # auth failed
    'AUTH_FAILED':             {"code": 401, "message": "auth failed!"},
    'NO_LOGIN':                {"code": 401, "message": "please login!"},
    'UPDATE_NOT_ALLOW':        {"code": 401, "message": "you can't modify case result status after it has finish!"},
    'DISABLE_NOT_ALLOW':       {"code": 401, "message": "you can't disable someone else's project"},

    # worker error
    'NO_MATCH_WORKER':         {"code": 401, "message": "can't find match worker!"},

    # limiter error
    'REACHED_LIMIT':           {"code": 429, "message": "ratelimit exceeded error!"},
}


def resp_return(code_key, append=None, append_field_num=None, new_msg=None):
    r = RETURN[code_key].copy()
    if append is not None:
        if append_field_num is not None:
            r["data"] = dict()
            r["data"]["total"] = append_field_num
            r["data"]["items"] = append
        else:
            r["data"] = append

    if new_msg:
        r["message"] = new_msg

    from flask import current_app
    # current_app.logger.info(r)
    return r, 200
