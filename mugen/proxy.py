# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import asyncio

from urllib.parse import urlparse

import mugen
from mugen.utils import is_ip


class ProxyNotPort(Exception): pass



@asyncio.coroutine
def get_proxy_key(url, dns_cache):
    urlparser = urlparse(url)
    ssl = urlparser.scheme == 'https'
    host = urlparser.netloc.split(':')[0]
    port = urlparser.port

    if is_ip(host):
        if not port:
            raise ProxyNotPort('proxy: {} has not port'.format(url))
        key = (host, port, ssl)
    else:
        if not port:
            port = 443 if ssl else 80
        ip, port = yield from dns_cache.get(host, port)
        key = (ip, port, ssl)
    return key


@asyncio.coroutine
def _make_https_proxy_connection(key, recycle=None):
    hostname = key[-1]

    response = yield from mugen.request('CONNECT', 'http://' + hostname,
                                        proxy='http://{}:{}'.format(key[0], key[1]),
                                        recycle=recycle)
    conn = response.connection
    transport = conn.reader._transport
    raw_socket = transport.get_extra_info('socket', default=None)
    # transport.pause_reading()
    conn.reader, conn.writer = yield from asyncio.open_connection(
        ssl=True, sock=raw_socket, server_hostname=hostname)
    conn.key = key
    return conn
