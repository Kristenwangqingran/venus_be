# -*- coding: utf-8 -*-
# @Time    : 2021-10-20
# @Author  : GongXun

import os
import time
import pika
import pika.exceptions
import traceback
from app.commons.config import get_config
from app.commons.mylogger import MyLogger


current_env = get_config()
MG = MyLogger('rabbitmq', path=os.path.join(
    'instance', current_env.LOG_FOLDER, 'rabbitMQ.log'))


class MyMq:

    def __init__(self, username, password, host, port, virtual_host='/'):
        self.credentials = pika.PlainCredentials(username, password)
        self.host = host
        self.port = port
        self.virtual_host = virtual_host
        self.connection = None
        self.channel = None
        self.connect()
        self._resend_delay = 0

    def creat_exchange(self, exchange_name, exchange_type):
        self.channel.exchange_declare(
            exchange=exchange_name, exchange_type=exchange_type)

    def connect(self):
        try:
            MG.logger.info(f"To connect MQ {self.host} {self.port} ...")
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host,
                                                                                port=self.port,
                                                                                virtual_host=self.virtual_host,
                                                                                credentials=self.credentials,
                                                                                heartbeat=0))
            self.channel = self.connection.channel()
            # Turn on delivery confirmations
            self.channel.confirm_delivery()
        except Exception:
            MG.logger.error(
                f"There are some problems with RabbitMQ connection: {traceback.format_exc()}")

    def get_resend_delay(self):
        self._resend_delay += 10
        if self._resend_delay > 300:
            self._resend_delay = 300
        return self._resend_delay

    def send(self, exchange_name, routing_key, message, retry=False):
        success = False
        try:
            if retry:
                delay = self.get_resend_delay()
                MG.logger.info(
                    f"Rabbit mq fails to send message, wait {delay}s and resend")
                time.sleep(delay)

            self.channel.basic_publish(
                exchange=exchange_name, routing_key=routing_key, body=message,
                mandatory=True,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                ))
            success = True
        except pika.exceptions.UnroutableError as err:
            MG.logger.error(
                f"Message was returned: {err}, details: {[e.method for e in err.messages]}")
        except pika.exceptions.NackError:
            MG.logger.error('Message was NackError')
        except pika.exceptions.ConnectionClosedByBroker:
            MG.logger.error('Suddenly broken link!')
            self.connect()
        except Exception:
            MG.logger.error(
                f'An unknown error occurred while sending a message: {traceback.format_exc()}')

        return self.send(exchange_name, routing_key, message, not success) if not success else success

    def close(self):
        self.connection.close()


def init_mymq():
    try:
        mymq = None
        username, password, host, port, vhost = current_env.MQ_INFO['MQ_USER'], current_env.MQ_INFO[
            'MQ_PASSWORD'], current_env.MQ_INFO['MQ_HOST'], current_env.MQ_INFO['MQ_PORT'], current_env.MQ_INFO['MQ_VHOST']
        mymq = MyMq(username, password, host, port, vhost)
        mymq.creat_exchange('allworkers', exchange_type='fanout')
        mymq.creat_exchange('thoseworkers', exchange_type='topic')
        mymq.creat_exchange('oneworker', exchange_type='direct')
        mymq.creat_exchange('thatworker', exchange_type='direct')

    except Exception:
        MG.logger.error(traceback.format_exc())
        mymq = None

    return mymq
