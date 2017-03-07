# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import logging
import asyncio
import socket
import struct

from urllib.parse import urlparse

import mugen
from mugen.utils import is_ip


class GeneralProxyError(Exception): pass

class SOCKS5AuthError(Exception): pass

class SOCKS5Error(Exception): pass

class ProxyNotPort(Exception): pass


SOCKS4_ERRORS = {
    0x5B: 'Request rejected or failed',
    0x5C: 'Request rejected because SOCKS server cannot connect to identd on the client',
    0x5D: 'Request rejected because the client program and identd report different user-ids'
}

SOCKS5_ERRORS = {
    0x01: 'General SOCKS server failure',
    0x02: 'Connection not allowed by ruleset',
    0x03: 'Network unreachable',
    0x04: 'Host unreachable',
    0x05: 'Connection refused',
    0x06: 'TTL expired',
    0x07: 'Command not supported, or protocol error',
    0x08: 'Address type not supported'
}


@asyncio.coroutine
def get_http_proxy_key(proxy_url, dns_cache):
    urlparser = urlparse(proxy_url)
    # ssl = urlparser.scheme == 'https'
    ssl = False
    host = urlparser.netloc.split(':')[0]
    port = urlparser.port

    if is_ip(host):
        if not port:
            raise ProxyNotPort('proxy: {} has not port'.format(proxy_url))
        key = (host, port, ssl)
    else:
        if not port:
            port = 80
        ip, port = yield from dns_cache.get(host, port)
        key = (ip, port, ssl)
    return key


@asyncio.coroutine
def _make_https_proxy_connection(conn, host, port, recycle=None):

    yield from mugen.request('CONNECT', 'http://{}'.format(host),
                             recycle=recycle, connection=conn)
    conn = yield from ssl_handshake(conn, host)
    return conn


@asyncio.coroutine
def ssl_handshake(conn, host):
    transport = conn.reader._transport
    raw_socket = transport.get_extra_info('socket', default=None)
    # transport.pause_reading()
    conn.reader, conn.writer = yield from asyncio.open_connection(
        ssl=True, sock=raw_socket, server_hostname=host)
    return conn


class Socks5Proxy:

    def __init__(self, conn, dest_host, dest_port, ssl, username, password):
        self.conn = conn
        self.dest_host = dest_host
        self.dest_port = dest_port
        self.ssl = ssl
        self.username = username
        self.password = password


    @asyncio.coroutine
    def init(self):
        # 1. connect to socks server and to authorize
        yield from self.auth()

        # 2. let socks server to connect dest_host
        yield from self.connect()

        # 3. SSL/TLS handshake
        if self.ssl:
            yield from self.connect_ssl()


    @asyncio.coroutine
    def auth(self):
        logging.debug('[Socks5Proxy.init.auth]: {}'.format(self.conn))

        # sending the authentication packages we support.
        if self.username and self.password:
            self.conn.send(b'\x05\x02\x00\x02')
        else:
            self.conn.send(b'\x05\x01\x00')

        chosen_auth = yield from self.conn.read(2)

        if chosen_auth[0:1] != b'\x05':
            raise GeneralProxyError('SOCKS5 proxy server sent invalid data')

        if chosen_auth[1:2] == b'\x02':
            # Okay, we need to perform a basic username/password
            # authentication.
            self.conn.send(b'\x01'
                            + chr(len(self.username)).encode()
                            + self.username
                            + chr(len(self.password)).encode()
                            + self.password)

            auth_status = yield from self.conn.reader.read()
            if auth_status[0:1] != b'\x01':
                # Bad response
                raise GeneralProxyError('SOCKS5 proxy server sent invalid data')
            if auth_status[1:2] != b'\x00':
                # Authentication failed
                raise SOCKS5AuthError('SOCKS5 authentication failed')

        # No authentication is required if 0x00
        elif chosen_auth[1:2] != b'\x00':
            # Reaching here is always bad
            if chosen_auth[1:2] == b'\xFF':
                raise SOCKS5AuthError('All offered SOCKS5 authentication methods were rejected')
            else:
                raise GeneralProxyError('SOCKS5 proxy server sent invalid data')
        # Otherwise, authentication succeeded


    @asyncio.coroutine
    def connect(self):
        logging.debug('[Socks5Proxy.init.connect]: {}'.format(self.conn))

        cmd = b'\x01' # CONNECT
        # Now we can request the actual connection
        header = b'\x05' + cmd + b'\x00'

        family_to_byte = {socket.AF_INET: b'\x01', socket.AF_INET6: b'\x04'}
        for family in (socket.AF_INET, socket.AF_INET6, None):
            if not family:
                self.conn.send(header
                               + b'\x03' + bytes([len(self.dest_host)])
                               + self.dest_host.encode('utf-8')
                               + struct.pack('>H', self.dest_port))
                break

            try:
                addr_bytes = socket.inet_pton(family, self.dest_host)
                self.conn.send(header
                               + family_to_byte[family]
                               + addr_bytes
                               + struct.pack('>H', self.dest_port))
                break
            except socket.error:
                continue

        # Get the response
        resp = yield from self.conn.read(3)
        if resp[0:1] != b'\x05':
            raise GeneralProxyError('SOCKS5 proxy server sent invalid data')

        status = ord(resp[1:2])
        if status != 0x00:
            # Connection failed: server returned an error
            error = SOCKS5_ERRORS.get(status, 'Unknown error')
            raise SOCKS5Error('{0:#04x}: {1}'.format(status, error))

        # Get the bound address/port
        tp = yield from self.conn.read(1)
        if tp == b'\x01':
            chk = yield from self.conn.read(4)
            addr = socket.inet_ntoa(chk)
        elif tp == b'\x03':
            length = yield from self.conn.read(1)
            addr = yield from self.conn.read(ord(length))
        elif tp == b'\x04':
            chk = yield from self.conn.read(16)
            addr = socket.inet_ntop(socket.AF_INET6, chk)
        else:
            raise GeneralProxyError('SOCKS5 proxy server sent invalid data')

        pt = yield from self.conn.read(2)
        port = struct.unpack('>H', pt)[0]
        return addr, port


    @asyncio.coroutine
    def connect_ssl(self):
        logging.debug('[Socks5Proxy.connect_ssl]: {}'.format(self.conn))
        yield from ssl_handshake(self.conn, self.dest_host)
        self.conn.ssl_on = True
