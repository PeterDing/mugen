# -*- coding: utf-8 -*-

import asyncio
import json
import gzip
from urllib.parse import urlparse, ParseResult

from http.cookies import SimpleCookie
from collections import OrderedDict, deque

from mugen.exceptions import NotFindIP
from mugen.structures import CaseInsensitiveDict
from mugen.utils import (
    default_headers,
    url_params_encode,
)

from httptools import HttpResponseParser


MAX_CONNECTION_POOL = 100
MAX_POOL_TASKS = 100
DEFAULT_DNS_CACHE_SIZE = 100
DEFAULT_REDIRECT_LIMIT = 100
HTTP_VERSION = 'HTTP/1.1'


#
# https://magic.io/blog/uvloop-blazing-fast-python-networking/
#
DEFAULT_READ_SIZE = 1024


class Singleton(object):

    def __new__(cls, *args, **kwargs):

        if not hasattr(cls, '_instance'):
            instance = object.__new__(cls)
            cls._instance = instance
        return cls._instance


class Request(object):

    def __init__(self, method, url,
                 params=None,
                 headers=None,
                 data=None,
                 cookies=None,
                 proxy=None,
                 encoding='utf-8'):

        self.method = method.upper()
        self.url = url
        self.params = params or {}
        self.headers = CaseInsensitiveDict(headers or default_headers())
        self.data = data
        self.cookies = SimpleCookie(cookies)
        self.proxy = proxy
        self.encoding = encoding

        self.prepare()


    def prepare(self):
        parser = urlparse(self.url)

        scheme = parser.scheme
        host = parser.netloc
        path = parser.path
        _params = parser.params
        query = parser.query
        fragment = parser.fragment

        if self.params:
            enc_params = url_params_encode(self.params)
            query = '{}&{}'.format(query, enc_params)

        self.url_parse_result = ParseResult(
            scheme = scheme or 'http',
            netloc = host,
            path = path,
            params = _params,
            query = query,
            fragment = fragment)

        self.ssl = scheme.lower() == 'https'


    def make_request(self):
        host = self.url_parse_result.netloc
        request_line = self.make_request_line()
        headers = self.make_request_headers(host, self.headers, self.cookies)
        data = self.make_request_data(self.data)

        return request_line, headers, data


    def make_request_line(self):
        method = self.method
        path = self.url_parse_result.path or '/'
        request_line = '{} {} {}'.format(method, path, HTTP_VERSION)
        return request_line


    def make_request_headers(self, host, headers, cookies):
        _headers = []

        if not headers.get('host'):
            _headers.append('Host: ' + host)

        if self.data:
            data = self.make_request_data(self.data)
            _headers.append('Content-Length: {}'.format(len(data.encode('utf-8'))))
            _headers.append('Content-Type: application/x-www-form-urlencoded')

        # add cookies
        if cookies:
            if isinstance(cookies, SimpleCookie):
                _cookies = []
                for k in cookies:
                    # TODO, path ?
                    v = cookies[k].value
                    _cookies.append('{}={};'.format(k, v))

                cookie = 'Cookie: ' + ' '.join(_cookies)
                _headers.append(cookie)
            elif isinstance(cookies, dict):
                _cookies = []
                for k, v in cookies.items():
                    _cookies.append('{}={};'.format(k, v))

                cookie = 'Cookie: ' + ' '.join(_cookies)
                _headers.append(cookie)

        if self.proxy:
            _headers.append('Proxy-Connection: Keep-Alive')

        # make headers
        for k, v in headers.items():
            _headers.append(k + ': ' + v)
        return '\r\n'.join(_headers)


    def make_request_data(self, data):
        if data is None:
            return data

        enc_data = None
        if isinstance(data, dict):
            enc_data = json.dumps(data, ensure_ascii=False)
        elif isinstance(data, str):
            enc_data = data
        else:
            TypeError('request data must be str or dict, NOT {!r}'.format(data))

        return enc_data


class HttpResonse(object):

    def __init__(self, cookies=None, encoding='utf-8'):
        self.headers = CaseInsensitiveDict()
        self.content = b''
        self.encoding = encoding
        self.cookies = cookies or SimpleCookie()


    # def on_message_begin(self):
        # print('on_message_begin')


    def on_header(self, name, value):
        name = name.decode(self.encoding)
        value = value.decode(self.encoding)
        if name.lower == 'set-cookie':
            self.cookies.load(value)
            if self.headers[name]:
                self.headers[name] += ', ' + value
                return None
        self.headers[name] = value


    # def on_headers_complete(self):
        # print(self.headers)


    def on_body(self, value):
        self.content += value


    # def on_message_complete(self):
        # print('on_message_complete')


    # def on_chunk_header(self, headers):
        # print('on_chunk_header')
        # return True


    # def on_chunk_complete(self):
        # print('on_chunk_complete')


class Response(object):

    def __init__(self, connection, encoding='utf-8'):
        self.connection = connection
        self.headers = None
        self.content = None
        self.cookies = SimpleCookie()
        self.encoding = encoding


    @asyncio.coroutine
    def receive(self):
        http_response = HttpResonse(cookies=self.cookies, encoding=self.encoding)
        http_response_parser = HttpResponseParser(http_response)

        conn = self.connection

        content = b''
        while True:
            chuck = yield from conn.readline()
            content += chuck
            if not chuck.strip():
                break

        http_response_parser.feed_data(content)

        headers = http_response.headers
        self.headers = headers

        # TODO, handle redirect

        body = b''
        nbytes = headers.get('Content-Length')
        if nbytes:
            nbytes = int(nbytes)
        if nbytes:
            body += yield from conn.read(nbytes)
        else:
            if headers.get('Transfer-Encoding') == 'chunked':
                blocks = []
                while True:
                    size_header = yield from conn.readline()
                    if not size_header:
                        # logging
                        break

                    parts = size_header.split(b';')
                    size = int(parts[0], 16)
                    if size:
                        block = yield from conn.read(size)
                        assert len(block) == size, ('[Response.receive] [Transfer-Encoding]',
                                                    len(block), size)
                        blocks.append(block)

                    crlf = yield from conn.readline()
                    assert crlf == b'\r\n', repr(crlf)
                    if not size:
                        break

                body += b''.join(blocks)
            else:
                # reading until EOF
                body += yield from conn.read(-1)

        self.status_code = http_response_parser.get_status_code()
        self.headers = http_response.headers
        self.cookies = http_response.cookies

        if self.headers.get('Content-Encoding', '').lower() == 'gzip':
            self.content = gzip.decompress(body)
        else:
            self.content = body


    @property
    def text(self):
        return self.content.decode(self.encoding)


class DNSCache(Singleton):
    '''
    unless lost dict
    '''

    def __init__(self, size=None, loop=None):
        if hasattr(self, '__initiated'):
            return None

        self.__initiated = True
        self.__size = DEFAULT_DNS_CACHE_SIZE
        self.__hosts = OrderedDict()
        self.loop = loop or asyncio.get_event_loop()


    def __repr__(self):
        return repr(dict(self.__hosts))


    @asyncio.coroutine
    def get(self, host, port, uncache=False):
        key = (host, port)
        ipaddrs = None
        if uncache:
            ipaddrs = yield from self.get_ipaddrs(host, port)
            ipaddrs = deque(ipaddrs)
        else:
            ipaddrs = self.__hosts.get(key)
            if not ipaddrs:
                ipaddrs = yield from self.get_ipaddrs(host, port)
                ipaddrs = deque(ipaddrs)

        assert ipaddrs, NotFindIP(str(key))

        self.add_host(key, ipaddrs)
        self.limit_cache()

        info = ipaddrs.popleft()
        ipaddrs.append(info)
        _, _, _, _, (ip, port, *_) = info

        return ip, port


    @asyncio.coroutine
    def get_ipaddrs(self, host, port):
        ipaddrs = yield from self.loop.getaddrinfo(host, port)
        return ipaddrs


    def add_host(self, key, ipaddrs):
        self.__hosts[key] = ipaddrs
        self.__hosts.move_to_end(key, last=False)  # FIFO


    def limit_cache(self):
        while len(self.__hosts) > self.__size:
            self.__hosts.popitem()
