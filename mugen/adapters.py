# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import logging
import asyncio

from mugen.models import (
    Singleton,
    Response,
    DEFAULT_ENCODING
)
# from mugen.connection_pool import ConnectionPool


class HTTPAdapter(Singleton):

    def __init__(self, connection_pool, recycle=True, loop=None):
        if hasattr(self, '_initiated'):
            return None

        logging.debug('instantiate HTTPAdapter: '
                      'recycle: {}, '.format(recycle))

        self._initiated = True
        self.recycle = recycle
        self.loop = loop or asyncio.get_event_loop()
        # self.connection_pool = ConnectionPool(recycle=recycle, loop=self.loop)
        self.connection_pool = connection_pool


    @asyncio.coroutine
    def get_connection(self, key, recycle=True):
        conn = yield from self.connection_pool.get_connection(key, recycle=recycle)
        if not conn.reader:
            yield from conn.connect()
        return conn


    @asyncio.coroutine
    def send_request(self, conn, request):
        request_line, headers, data = request.make_request()
        request_line = request_line.encode('utf-8')
        headers = headers.encode('utf-8')
        if isinstance(data, str):
            data = data.encode('utf-8')

        conn.send(request_line + b'\r\n')
        conn.send(headers + b'\r\n')
        conn.send(b'\r\n')
        if data:
            conn.send(data)


    @asyncio.coroutine
    def get_response(self, method, conn, encoding=DEFAULT_ENCODING):
        response = Response(method, conn, encoding=encoding)
        yield from response.receive()

        if response.headers.get('connection') == 'close':
            conn.recycle = False
            conn.close()
        return response


    def closed(self):
        return self._initiated is None and self.connection_pool is None


    def close(self):
        self._initiated = self.connection_pool = self.loop = None
