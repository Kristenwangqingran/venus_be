import requests
import re
import traceback
from flask import current_app
from urllib.parse import ParseResult, quote


class SCPMgr:

    @classmethod
    def __get_SCP_typ(cls, gitproject):
        r = re.compile(r'/[A-Za-z]+-\d+/|[A-Z]+-\d+')
        if r.search(gitproject):
            typ = "Feature"
        else:
            typ = "Normal"
        return typ

    @classmethod
    def __get_coverage(cls, data):
        Total = "unknow"
        ST_Total = "unknow"
        UT_Total = "unknow"
        CInc = "unknow"
        ST_CInc = "unknow"
        UT_CInc = "unknow"

        try:
            Total = f"{round(data['fullCover']['rate'] * 100, 2)}%"
            ST_Total = f"{round(data['stFullCover']['rate'] * 100, 2)}%"
            UT_Total = f"{round(data['utFullCover']['rate'] * 100, 2)}%"

            if data['customizedIncCover']["srcCommitId"]:
                CInc = f"{round(data['customizedIncCover']['rate'] * 100, 2)}%"
                ST_CInc = f"{round(data['stCustomizedIncCover']['rate'] * 100, 2)}%"
                UT_CInc = f"{round(data['utCustomizedIncCover']['rate'] * 100, 2)}%"
            else:
                CInc = f"{round(data['incCover']['rate'] * 100, 2)}%"
                ST_CInc = f"{round(data['stIncCover']['rate'] * 100, 2)}%"
                UT_CInc = f"{round(data['utIncCover']['rate'] * 100, 2)}%"

        except Exception:
            current_app.logger.error(traceback.format_exc())

        return Total, ST_Total, UT_Total, CInc, ST_CInc, UT_CInc

    @classmethod
    def get_coverage_by_projectID(cls, gitproject_id, gitbranch):
        scp_openapi_info = ParseResult(
            scheme='https',
            netloc=current_app.config['SCP_PROXY'],
            path='/scp/api/v2/covers',
            params="",
            query=f'pageIndex=1&pageSize=1&language=go&typ={cls.__get_SCP_typ(gitbranch)}&ProjectIds={gitproject_id}&branchName={quote(gitbranch)}',
            fragment=''
        )
        scp_url = scp_openapi_info.geturl()
        current_app.logger.info(f"scp_url: {scp_url}")
        resp = requests.get(scp_url, headers={
                            "Accept": "application/json"}, timeout=5)
        try:
            data = resp.json()['data'][0]
        except Exception:
            current_app.logger.error(traceback.format_exc())
            data = None

        return cls.__get_coverage(data)

    @classmethod
    def get_coverage_by_projectName(cls, gitproject, gitbranch):
        scp_openapi_info = ParseResult(
            scheme='https',
            netloc=current_app.config['SCP_PROXY'],
            path='/scp/api/v2/covers',
            params="",
            query=f'pageIndex=1&pageSize=1&language=go&typ={cls.__get_SCP_typ(gitbranch)}&projectName={gitproject}&branchName={quote(gitbranch)}',
            fragment=''
        )
        scp_url = scp_openapi_info.geturl()
        current_app.logger.info(f"scp_url: {scp_url}")
        resp = requests.get(scp_url, headers={
                            "Accept": "application/json"}, timeout=5)
        try:
            data = resp.json()['data'][0]
        except Exception:
            current_app.logger.error(traceback.format_exc())
            data = None

        return cls.__get_coverage(data)

    @classmethod
    def get_coverage_by_fullProjectName(cls, full_project_name, gitbranch):
        scp_openapi_info = ParseResult(
            scheme='https',
            netloc=current_app.config['SCP_PROXY'],
            path='/scp/api/v2/covers',
            params="",
            query=f'pageIndex=1&pageSize=1&language=go&typ={cls.__get_SCP_typ(gitbranch)}&projectFullName={quote(full_project_name)}&branchName={quote(gitbranch)}',
            fragment=''
        )
        scp_url = scp_openapi_info.geturl()
        current_app.logger.info(f"scp_url: {scp_url}")
        resp = requests.get(scp_url, headers={
                            "Accept": "application/json"}, timeout=5)
        try:
            data = resp.json()['data'][0]
        except Exception:
            current_app.logger.error(traceback.format_exc())
            data = None

        return cls.__get_coverage(data)

    @classmethod
    def get_mergeddata_link(cls, git_project_name, git_project_fullname, git_branch_name):

        if git_project_fullname:
            query = f'projectFullName={quote(git_project_fullname)}&branch={quote(git_branch_name)}&activeName={cls.__get_SCP_typ(git_branch_name)}'
        else:
            query = f'gitProjectName={git_project_name}&branch={quote(git_branch_name)}&activeName={cls.__get_SCP_typ(git_branch_name)}'

        scp_url_info = ParseResult(
            scheme='https',
            netloc=current_app.config['SCP_HOST'],
            path='/mergeddata/go',
            params="",
            query=query,
            fragment=''
        )
        return scp_url_info.geturl()
