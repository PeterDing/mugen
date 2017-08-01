# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import time
import logging
import asyncio

from functools import wraps

from mugen.exceptions import ConnectionIsStale
from mugen.models import MAX_CONNECTION_TIMEOUT, MAX_KEEP_ALIVE_TIME

log = logging.getLogger(__name__)


def async_error_proof(gen):
    @wraps(gen)
    @asyncio.coroutine
    def wrap(self, *args, **kwargs):
        try:
            rs = yield from gen(self, *args, **kwargs)
            return rs
        except Exception as err:
            log.error('[{}]: {}'.format(gen, repr(err)))
            self.close()
            raise err
    return wrap


def error_proof(func):
    @wraps(func)
    def wrap(self, *args, **kwargs):
        try:
            rs = func(self, *args, **kwargs)
            return rs
        except Exception as err:
            log.error('[{}]: {}'.format(func, repr(err)))
            self.close()
            raise err
    return wrap


class Connection(object):

    def __init__(self, ip, port,
                 ssl=False,
                 key=None,
                 recycle=True,
                 timeout=None,
                 loop=None):

        self.ip = ip
        self.port = port
        self.ssl = ssl
        self.key = key or (ip, port, ssl)
        self.recycle = recycle
        self.loop = loop or asyncio.get_event_loop()
        self.reader = None
        self.writer = None
        self.ssl_on = False  # For http/socks proxy which need ssl connection
        self.socks_on = False  # socks proxy which needs to be initiated
        self.timeout = timeout or MAX_KEEP_ALIVE_TIME
        self.__last_action = time.time()


    def __repr__(self):
        return '<Connection: {!r}>'.format(self.key)


    def _watch(self):
        self.__last_action = time.time()
        return self.__last_action


    def is_timeout(self):
        return time.time() - self.__last_action > self.timeout


    @async_error_proof
    @asyncio.coroutine
    def connect(self):
        log.debug('[Connection.connect]: {}'.format(self.key))

        reader, writer = yield from asyncio.open_connection(self.ip,
                                                            self.port,
                                                            ssl=self.ssl,
                                                            loop=self.loop)

        self.reader = reader
        self.writer = writer


    @async_error_proof
    @asyncio.coroutine
    def ssl_handshake(self, host):
        log.debug('[Connection.ssl_handshake]: {}, {}'.format(self.key, host))
        transport = self.reader._transport
        raw_socket = transport.get_extra_info('socket', default=None)
        # transport.pause_reading()
        self.reader, self.writer = yield from asyncio.open_connection(
            ssl=True, sock=raw_socket, server_hostname=host)


    @error_proof
    def send(self, data):
        log.debug('[Connection.send]: {!r}'.format(data))
        self._watch()

        self.writer.write(data)


    @async_error_proof
    @asyncio.coroutine
    def read(self, size=-1):
        log.debug('[Connection.read]: {}: size = {}'.format(self.key, size))
        self._watch()
        # assert self.closed() is not True, 'connection is closed'
        # assert self.stale() is not True, 'connection is stale'

        if self.stale():
            log.debug('[Connection.read] [Error] '
                      '[ConnectionIsStale]: {}'.format(self.key))
            raise ConnectionIsStale('{}'.format(self.key))

        if size < 0:
            chuck = yield from asyncio.wait_for(self.reader.read(size),
                                                timeout=MAX_CONNECTION_TIMEOUT)
            return chuck
        else:
            chucks = b''
            while size:
                chuck = yield from asyncio.wait_for(self.reader.read(size),
                                                    timeout=MAX_CONNECTION_TIMEOUT)
                size -= len(chuck)
                chucks += chuck
            return chucks


    @async_error_proof
    @asyncio.coroutine
    def readline(self):
        # assert self.closed() is False, 'connection is closed'
        # assert self.stale() is not True, 'connection is stale'

        if self.stale():
            log.debug('[Connection.readline] [Error] '
                      '[ConnectionIsStale]: {}'.format(self.key))
            raise ConnectionIsStale('{}'.format(self.key))

        chuck = yield from asyncio.wait_for(self.reader.readline(),
                                            timeout=MAX_CONNECTION_TIMEOUT)

        log.debug('[Connection.readline]: '
                  '{}: size = {}'.format(self.key, len(chuck)))

        return chuck


    def close(self):
        log.debug('[Connection.close]: {}, '
                  'recycle: {}'.format(self.key, self.recycle))

        if not self.closed():
            self.reader.feed_eof()
            self.writer.close()
            self.reader = self.writer = None
            log.debug('[Connection.close]: DONE. {}, '
                      'recycle: {}'.format(self.key, self.recycle))


    def closed(self):
        return self.reader is None or self.writer is None


    def stale(self):
        is_stale = self.reader is None or self.reader.at_eof()
        if is_stale:
            log.debug('[Connection.stale]: {} is stale'.format(self.key))
        return is_stale
