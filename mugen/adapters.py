# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import logging
import asyncio

from mugen.utils import is_ip, parse_proxy
from mugen.exceptions import UnknownProxyScheme
from mugen.proxy import (
    _make_https_proxy_connection,
    Socks5Proxy
)
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
        self.connection_pool = connection_pool


    @asyncio.coroutine
    def generate_direct_connect(self, host, port, ssl, dns_cache, recycle=True):
        key = None
        if is_ip(host):
            ip = host.split(':')[0]
            key = (ip, port, ssl)

        if not key and not ssl:
            ip, port = yield from dns_cache.get(host, port)
            key = (ip, port, ssl)

        if not key and ssl:
            key = (host, port, ssl)

        conn = yield from self.get_connection(key, recycle=recycle)
        return conn


    @asyncio.coroutine
    def generate_proxy_connect(self, host, port, ssl, proxy, dns_cache, recycle=True):
        proxy_scheme, proxy_host, proxy_port, username, password = parse_proxy(proxy)

        proxy_ip, proxy_port = yield from dns_cache.get(proxy_host, proxy_port)
        if ssl:
            key = (proxy_ip, proxy_port, False, host)
        else:
            key = (proxy_ip, proxy_port, False)

        if proxy_scheme.lower() == 'http':
            conn = yield from self.generate_http_proxy_connect(
                key, host, port, ssl, username, password, recycle=recycle)
        elif proxy_scheme.lower() == 'socks5':
            conn = yield from self.generate_socks5_proxy_connect(
                key, host, port, ssl, username, password, recycle=recycle)
        else:
            raise UnknownProxyScheme(proxy_scheme)
        return conn


    @asyncio.coroutine
    def generate_http_proxy_connect(
        self, key, host, port, ssl, username, password, recycle=True):

        conn = yield from self.get_connection(key, recycle=recycle)

        if ssl and not conn.ssl_on:
            logging.debug('[ssl_handshake]: {}'.format(key))
            yield from _make_https_proxy_connection(
                conn, host, port, recycle=recycle)
            conn.ssl_on = True
        return conn


    def generate_socks5_proxy_connect(
        self, key, host, port, ssl, username, password, recycle=True):

        conn = yield from self.get_connection(key, recycle=recycle)
        if conn.socks_on:
            return conn

        socks5_proxy = Socks5Proxy(conn, host, port, ssl, username, password)
        yield from socks5_proxy.init()
        conn.socks_on = True
        return conn


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
