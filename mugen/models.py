# -*- coding: utf-8 -*-

import logging
import asyncio
import json
from urllib.parse import urlparse, ParseResult

from http.cookies import SimpleCookie, Morsel
from collections import OrderedDict, deque

from mugen.cookies import DictCookie
from mugen.exceptions import NotFindIP
from mugen.structures import CaseInsensitiveDict
from mugen.utils import (
    default_headers,
    url_params_encode,
    form_encode,
    decode_gzip,
    decode_deflate,
    find_encoding,
    is_ip
)

from httptools import HttpResponseParser


MAX_CONNECTION_POOL = 100
MAX_POOL_TASKS = 100
MAX_REDIRECTIONS = 1000
MAX_CONNECTION_TIMEOUT = 1 * 60
DEFAULT_DNS_CACHE_SIZE = 100
DEFAULT_REDIRECT_LIMIT = 100
DEFAULT_RECHECK_INTERNAL = 100
HTTP_VERSION = 'HTTP/1.1'
DEFAULT_ENCODING = 'utf-8'


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
                 encoding=None):

        self.method = method.upper()
        self.url = url
        self.params = params or {}
        if headers is None:
            headers = {}
        self.headers = CaseInsensitiveDict(headers or default_headers())
        self.data = data
        self.proxy = proxy
        self.encoding = encoding
        if cookies is None:
            self.cookies = DictCookie()
        else:
            self.cookies = cookies

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
        headers = self.make_request_headers(self.method, host, self.headers, self.cookies)
        data = self.make_request_data(self.data)

        # TODO: encoding file

        return request_line, headers, data


    def make_request_line(self):
        method = self.method
        host = self.url_parse_result.netloc
        port = self.url_parse_result.port or 443
        path = self.url_parse_result.path or '/'
        query = self.url_parse_result.query

        if method.lower() == 'connect':
            request_line = '{} {} {}'.format(method,
                                             '{}:{}'.format(host, port),
                                             HTTP_VERSION)
        else:
            uri = path
            if query:
                uri += '?' + query
            request_line = '{} {} {}'.format(method, uri, HTTP_VERSION)
        return request_line


    def make_request_headers(self, method, host, headers, cookies):
        _headers = []

        if not headers.get('host'):
            _headers.append('Host: ' + host + (':443' if method.lower() == 'connect' else ''))

        if method.lower() == 'post' and not self.data:
            _headers.append('Content-Length: 0')

        if self.data:
            data = self.make_request_data(self.data)
            _headers.append('Content-Length: {}'.format(len(data.encode('utf-8'))))
            if isinstance(self.data, dict) and not headers.get('Content-Type'):
                _headers.append('Content-Type: application/x-www-form-urlencoded')

        # add cookies
        if cookies:
            if isinstance(cookies, (DictCookie, SimpleCookie)):
                _cookies = []
                for k in cookies:
                    # TODO, path ?
                    if isinstance(cookies[k], Morsel):
                        v = cookies[k].value
                    else:
                        v = cookies[k]
                    _cookies.append('{}={};'.format(k, v))

                cookie = 'Cookie: ' + ' '.join(_cookies)
                _headers.append(cookie)
            elif isinstance(cookies, dict):
                _cookies = []
                for k, v in cookies.items():
                    _cookies.append('{}={};'.format(k, v))

                cookie = 'Cookie: ' + ' '.join(_cookies)
                _headers.append(cookie)

        # make headers
        for k, v in headers.items():
            _headers.append(k + ': ' + v)
        return '\r\n'.join(_headers)


    def make_request_data(self, data):
        if data is None:
            return data

        enc_data = None
        if isinstance(data, dict):
            enc_data = form_encode(data)
        elif isinstance(data, str):
            enc_data = data
        elif isinstance(data, bytes):
            enc_data = data
        else:
            TypeError('request data must be str or dict, NOT {!r}'.format(data))

        return enc_data


class HttpResonse(object):

    def __init__(self, cookies=None, encoding=None):
        self.headers = CaseInsensitiveDict()
        self.content = b''
        self.encoding = encoding or DEFAULT_ENCODING
        if cookies is None:
            self.cookies = DictCookie()
        else:
            self.cookies = cookies


    # def on_message_begin(self):
        # print('on_message_begin')


    def on_header(self, name, value):
        name = name.decode(self.encoding)
        value = value.decode(self.encoding)
        if name.lower() == 'set-cookie':
            self.cookies.load(value)
            if self.headers.get(name):
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

    def __init__(self, method, connection, encoding=None):
        self.method = method
        self.connection = connection
        self.headers = None
        self.content = None
        self.cookies = DictCookie()
        self.encoding = encoding
        self.status_code = None
        self.history = []


    def __repr__(self):
        return '<Response [{}]>'.format(self.status_code)


    @asyncio.coroutine
    def receive(self):
        http_response = HttpResonse(cookies=self.cookies, encoding=self.encoding)
        http_response_parser = HttpResponseParser(http_response)

        conn = self.connection

        # TODO, handle Maximum amount of incoming data to buffer
        chucks = b''
        while True:
            chuck = yield from conn.readline()
            chucks += chuck
            if chuck == b'\r\n':
                break

        http_response_parser.feed_data(chucks)

        self.status_code = http_response_parser.get_status_code()
        headers = http_response.headers
        self.headers = headers

        # (protocol, status_code, ok), headers, cookies = parse_headers(chucks)
        # self.headers = headers
        # self.status_code = status_code
        # self.cookies = cookies

        # TODO, handle redirect

        body = b''
        if self.method.lower() == 'head':    # HEAD
            self.content = body
            return None

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
                pass
                # body += yield from conn.read(-1)

        if body and self.headers.get('Content-Encoding', '').lower() == 'gzip':
            self.content = decode_gzip(body)
        elif body and self.headers.get('Content-Encoding', '').lower() == 'deflate':
            self.content = decode_deflate(body)
        else:
            self.content = body

        if not self.encoding:
            # find charset from content-type
            encoding = find_encoding(self.headers.get('Content-Type', ''))
            if encoding:
                self.encoding = encoding


    @property
    def text(self):
        # TODO, use chardet to detect charset
        encoding = self.encoding or DEFAULT_ENCODING

        return str(self.content, encoding, errors='replace')


    def json(self):
        return json.loads(self.text)


class DNSCache(Singleton):
    """
    DNS Cache
    """

    def __init__(self, size=DEFAULT_DNS_CACHE_SIZE, loop=None):
        if hasattr(self, '_initiated'):
            return None

        logging.debug('instantiate DNSCache: size: {}'.format(size))

        self._initiated = True
        self.__size = size
        self.__hosts = OrderedDict()
        self.loop = loop or asyncio.get_event_loop()


    def __repr__(self):
        return repr(dict(self.__hosts))


    @asyncio.coroutine
    def get(self, host, port, uncache=False):
        if is_ip(host):
            return host, port

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


    def clear(self):
        self.__hosts.clear()
