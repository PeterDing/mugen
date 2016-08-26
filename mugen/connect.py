# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import logging
import asyncio


class Connection(object):

    def __init__(self, ip, port, ssl=False, pool=None, recycle=True, loop=None):
        self.ip = ip
        self.port = port
        self.ssl = ssl
        self.key = (ip, port, ssl)
        self.connection_pool = pool
        self.recycle = False if pool is None else recycle
        self.loop = loop or asyncio.get_event_loop()
        self.reader = None
        self.writer = None


    def __repr__(self):
        return repr(self.key)


    @asyncio.coroutine
    def connect(self):
        logging.debug('[Connection.connect]: {}'.format(self.key))

        reader, writer = yield from asyncio.open_connection(self.ip,
                                                            self.port,
                                                            ssl=self.ssl,
                                                            loop=self.loop)
        self.reader = reader
        self.writer = writer


    def send(self, data):
        logging.debug('[Connection.send]: {!r}'.format(data))

        self.writer.write(data)


    @asyncio.coroutine
    def read(self, size=-1):
        logging.debug('[Connection.read]: {}: size = {}'.format(self.key, size))
        # assert self.closed() is not True, 'connection is closed'
        # assert self.stale() is not True, 'connection is stale'

        if size < 0:
            chuck = yield from self.reader.read(size)
            return chuck
        else:
            chucks = b''
            while size:
                chuck = yield from self.reader.read(size)
                size -= len(chuck)
                chucks += chuck
            return chucks


    @asyncio.coroutine
    def readline(self):
        # assert self.closed() is False, 'connection is closed'
        # assert self.stale() is not True, 'connection is stale'

        chuck = yield from self.reader.readline()

        logging.debug('[Connection.readline]: {}: size = {}'.format(self.key,
                                                                    len(chuck)))

        return chuck


    def close(self):
        logging.debug('[Connection.close]: {}, '
                      'recycle: {}'.format(self.key, self.recycle))

        if self.recycle:
            if not self.stale():
                self.connection_pool.recycle_connection(self)
                return None

        self.writer.close()
        self.connection_pool = self.reader = self.writer = None
        logging.debug('[Connection.close]: DONE. {}, '
                      'recycle: {}'.format(self.key, self.recycle))


    def closed(self):
        return self.reader is None or self.writer is None


    def stale(self):
        return self.reader is None or self.reader.at_eof()
