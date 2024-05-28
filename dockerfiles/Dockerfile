##############################################
# 基于centos7构建python3.7运行环境
# 构建命令: 在Dockerfile文件目录下执行 docker build -t webserver:v1 .
# 容器启动命令: docker run -it -d -v `pwd`:/home/admin --name=webserver webserver:v1
# 进入容器:docker exec -it webserver /bin/bash
# @Time    : 2020-08-04
# @Author  : gongxun
##############################################
FROM python:3.11
LABEL author="Kobe" 

WORKDIR /home/admin

RUN apt update && apt -y install libpq-dev

COPY pip.conf /root/.pip/pip.conf
COPY requirements.txt .
RUN pip install pip --upgrade && pip install -i https://pypi.garenanow.com -r requirements.txt \
    && rm -f requirements.txt

RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo 'Asia/Shanghai' >/etc/timezone


COPY .git-credentials \
    .gitconfig \
    /root/
RUN git config --global credential.helper store --file=/root/.git-credentials

EXPOSE 5001
