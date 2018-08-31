import logging
import asyncio
import yaml
from aiokafka import AIOKafkaConsumer
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from osm_common.msgbase import MsgBase, MsgException
# import json

__author__ = "Alfonso Tierno <alfonso.tiernosepulveda@telefonica.com>, " \
             "Guillermo Calvino <guillermo.calvinosanchez@altran.com>"


class MsgKafka(MsgBase):
    def __init__(self, logger_name='msg'):
        self.logger = logging.getLogger(logger_name)
        self.host = None
        self.port = None
        self.consumer = None
        self.producer = None
        self.loop = None
        self.broker = None
        self.group_id = None

    def connect(self, config):
        try:
            if "logger_name" in config:
                self.logger = logging.getLogger(config["logger_name"])
            self.host = config["host"]
            self.port = config["port"]
            self.loop = asyncio.get_event_loop()
            self.broker = str(self.host) + ":" + str(self.port)
            self.group_id = config.get("group_id")

        except Exception as e:  # TODO refine
            raise MsgException(str(e))

    def disconnect(self):
        try:
            pass
            # self.loop.close()
        except Exception as e:  # TODO refine
            raise MsgException(str(e))

    def write(self, topic, key, msg):
        """
        Write a message at kafka bus
        :param topic: message topic, must be string
        :param key: message key, must be string
        :param msg: message content, can be string or dictionary
        :return: None or raises MsgException on failing
        """
        try:
            self.loop.run_until_complete(self.aiowrite(topic=topic, key=key, msg=msg))

        except Exception as e:
            raise MsgException("Error writing {} topic: {}".format(topic, str(e)))

    def read(self, topic):
        """
        Read from one or several topics.
        :param topic: can be str: single topic; or str list: several topics
        :return: topic, key, message; or None
        """
        try:
            return self.loop.run_until_complete(self.aioread(topic, self.loop))
        except MsgException:
            raise
        except Exception as e:
            raise MsgException("Error reading {} topic: {}".format(topic, str(e)))

    async def aiowrite(self, topic, key, msg, loop=None):

        if not loop:
            loop = self.loop
        try:
            self.producer = AIOKafkaProducer(loop=loop, key_serializer=str.encode, value_serializer=str.encode,
                                             bootstrap_servers=self.broker)
            await self.producer.start()
            await self.producer.send(topic=topic, key=key, value=yaml.safe_dump(msg, default_flow_style=True))
        except Exception as e:
            raise MsgException("Error publishing topic '{}', key '{}': {}".format(topic, key, e))
        finally:
            await self.producer.stop()

    async def aioread(self, topic, loop=None, callback=None, *args):
        """
        Asyncio read from one or several topics. It blocks
        :param topic: can be str: single topic; or str list: several topics
        :param loop: asyncio loop
        :callback: callback function that will handle the message in kafka bus
        :*args: optional arguments for callback function
        :return: topic, key, message
        """

        if not loop:
            loop = self.loop
        try:
            if isinstance(topic, (list, tuple)):
                topic_list = topic
            else:
                topic_list = (topic,)

            self.consumer = AIOKafkaConsumer(loop=loop, bootstrap_servers=self.broker, group_id=self.group_id)
            await self.consumer.start()
            self.consumer.subscribe(topic_list)

            async for message in self.consumer:
                if callback:
                    callback(message.topic, yaml.load(message.key), yaml.load(message.value), *args)
                else:
                    return message.topic, yaml.load(message.key), yaml.load(message.value)
        except KafkaError as e:
            raise MsgException(str(e))
        finally:
            await self.consumer.stop()
