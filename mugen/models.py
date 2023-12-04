import json
import logging
import asyncio
import socket
import base64
from urllib.parse import urlparse, ParseResult

from http.cookies import SimpleCookie, Morsel
from collections import OrderedDict

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
    is_ip,
    parse_proxy,
    base64encode,
)

from httptools import HttpResponseParser


MAX_CONNECTION_POOL = 100
MAX_POOL_TASKS = 100
MAX_REDIRECTIONS = 1000
MAX_CONNECTION_TIMEOUT = 1 * 60
MAX_KEEP_ALIVE_TIME = 10 * 60
DEFAULT_DNS_CACHE_SIZE = 5000
DEFAULT_REDIRECT_LIMIT = 100
DEFAULT_RECHECK_INTERNAL = 100
HTTP_VERSION = "HTTP/1.1"
DEFAULT_ENCODING = "utf-8"


# https://magic.io/blog/uvloop-blazing-fast-python-networking/
DEFAULT_READ_SIZE = 1024

logger = logging.getLogger(__name__)


class Singleton(object):
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            instance = object.__new__(cls)
            cls._instance = instance
        return cls._instance


class Request(object):
    def __init__(
        self,
        method,
        url,
        params=None,
        headers=None,
        data=None,
        cookies=None,
        proxy=None,
        proxy_auth=None,
        encoding=None,
    ):
        self.method = method.upper()
        self.url = url
        self.params = params or {}
        if headers is None:
            headers = {}
        self.headers = CaseInsensitiveDict(headers or default_headers())
        self.data = data
        self.encoding = encoding
        if cookies is None:
            self.cookies = DictCookie()
        else:
            self.cookies = cookies

        self.proxy = proxy

        self.proxy_auth = proxy_auth
        if not proxy_auth and proxy:
            _, _, _, username, password = parse_proxy(proxy)
            if username and password:
                basic = f"{username}:{password}"
                self.proxy_auth = basic

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
            query = "{}&{}".format(query, enc_params)

        self.url_parse_result = ParseResult(
            scheme=scheme or "http",
            netloc=host,
            path=path,
            params=_params,
            query=query,
            fragment=fragment,
        )

        self.ssl = scheme.lower() == "https"

    def make_request(self):
        host = self.url_parse_result.netloc
        request_line = self.make_request_line()
        headers = self.make_request_headers(
            self.method, host, self.headers, self.cookies
        )
        data = self.make_request_data(self.data)

        # TODO: encoding file

        return request_line, headers, data

    def make_request_line(self):
        method = self.method
        scheme = self.url_parse_result.scheme
        host = self.url_parse_result.netloc
        port = self.url_parse_result.port
        if not port:
            if self.ssl:
                port = 443
            else:
                port = 80

        path = self.url_parse_result.path or "/"
        query = self.url_parse_result.query

        if method.lower() == "connect":
            request_line = "{} {} {}".format(method, host, HTTP_VERSION)
        else:
            if self.proxy:
                uri = f"{scheme}://{host}{path}"
            else:
                uri = path

            if query:
                uri += "?" + query
            request_line = "{} {} {}".format(method, uri, HTTP_VERSION)
        return request_line

    def make_request_headers(self, method, host, headers, cookies):
        _headers = []

        if not headers.get("host"):
            _headers.append("Host: " + host)

        if method.lower() == "post" and not self.data:
            _headers.append("Content-Length: 0")

        if self.data:
            data = self.make_request_data(self.data)
            _headers.append("Content-Length: {}".format(len(data)))
            if isinstance(self.data, dict) and not headers.get("Content-Type"):
                _headers.append("Content-Type: application/x-www-form-urlencoded")

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
                    _cookies.append("{}={};".format(k, v))

                cookie = "Cookie: " + " ".join(_cookies)
                _headers.append(cookie)
            elif isinstance(cookies, dict):
                _cookies = []
                for k, v in cookies.items():
                    _cookies.append("{}={};".format(k, v))

                cookie = "Cookie: " + " ".join(_cookies)
                _headers.append(cookie)

        # Add Proxy-Authorization header
        if self.proxy_auth:
            basic = base64encode(self.proxy_auth)
            proxy_auth = f"Proxy-Authorization: Basic {basic}"
            _headers.append(proxy_auth)
            _headers.append("Proxy-Connection: Keep-Alive")

        # make headers
        for k, v in headers.items():
            _headers.append(k + ": " + v)
        return "\r\n".join(_headers)

    def make_request_data(self, data):
        if data is None:
            return data

        enc_data = None
        if isinstance(data, dict):
            enc_data = form_encode(data)
        elif isinstance(data, str):
            enc_data = bytes(data, "utf-8")
        elif isinstance(data, bytes):
            enc_data = data
        else:
            TypeError("request data must be str or dict, NOT {!r}".format(data))

        return enc_data


class HttpResonse(object):
    def __init__(self, cookies=None, encoding=None):
        self.headers = CaseInsensitiveDict()
        self.content = b""
        self.encoding = encoding or DEFAULT_ENCODING
        if cookies is None:
            self.cookies = DictCookie()
        else:
            self.cookies = cookies

    def on_header(self, name, value):
        name = name.decode(self.encoding)
        value = value.decode(self.encoding)
        if name.lower() == "set-cookie":
            self.cookies.load(value)
            if self.headers.get(name):
                self.headers[name] += ", " + value
                return None
        self.headers[name] = value

    def on_body(self, value):
        self.content += value


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
        self.request = None

    def __repr__(self):
        return "<Response [{}]>".format(self.status_code)

    async def receive(self):
        http_response = HttpResonse(cookies=self.cookies, encoding=self.encoding)
        http_response_parser = HttpResponseParser(http_response)

        conn = self.connection

        # TODO, handle Maximum amount of incoming data to buffer
        chucks = b""
        while True:
            chuck = await conn.readline()
            chucks += chuck
            if chuck == b"\r\n":
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

        body = b""
        if self.method.lower() == "head":  # HEAD
            self.content = body
            return None

        nbytes = headers.get("Content-Length")
        if nbytes:
            nbytes = int(nbytes)
        if nbytes:
            body += await conn.read(nbytes)
        else:
            if headers.get("Transfer-Encoding") == "chunked":
                blocks = []
                while True:
                    size_header = await conn.readline()
                    if not size_header:
                        # logging
                        break

                    parts = size_header.split(b";")
                    size = int(parts[0], 16)
                    if size:
                        block = await conn.read(size)
                        assert len(block) == size, (
                            "[Response.receive] [Transfer-Encoding]",
                            len(block),
                            size,
                        )
                        blocks.append(block)

                    crlf = await conn.readline()
                    assert crlf == b"\r\n", repr(crlf)
                    if not size:
                        break

                body += b"".join(blocks)
            else:
                # reading until EOF
                pass
                # body += await conn.read(-1)

        if body and self.headers.get("Content-Encoding", "").lower() == "gzip":
            self.content = decode_gzip(body)
        elif body and self.headers.get("Content-Encoding", "").lower() == "deflate":
            self.content = decode_deflate(body)
        else:
            self.content = body

        if not self.encoding:
            # find charset from content-type
            encoding = find_encoding(self.headers.get("Content-Type", ""))
            if encoding:
                self.encoding = encoding

    @property
    def text(self):
        # TODO, use chardet to detect charset
        encoding = self.encoding or DEFAULT_ENCODING

        return str(self.content, encoding, errors="replace")

    def json(self):
        return json.loads(self.text)


class DNSCache(Singleton):
    """
    DNS Cache
    """

    def __init__(self, size=DEFAULT_DNS_CACHE_SIZE, loop=None):
        if hasattr(self, "_initiated"):
            return None

        logger.debug("instantiate DNSCache: size: {}".format(size))

        self._initiated = True
        self.__size = size
        self.__hosts = OrderedDict()
        self.loop = loop or asyncio.get_event_loop()

    def __repr__(self):
        return repr(dict(self.__hosts))

    async def get(self, host, port, uncache=False):
        if is_ip(host):
            return host, port

        key = (host, port)
        if uncache:
            ipaddrs = await self.get_ipaddrs(host, port)
            ipaddr = self.add_host(key, ipaddrs)
        else:
            ipaddr = self.__hosts.get(key)
            if not ipaddr:
                ipaddrs = await self.get_ipaddrs(host, port)
                ipaddr = self.add_host(key, ipaddrs)

        self.limit_cache()

        assert ipaddr, NotFindIP(str(key))

        family, type, proto, canonname, (ip, port, *_) = ipaddr
        return ip, port

    async def get_ipaddrs(self, host, port):
        ipaddrs = await self.loop.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        return ipaddrs

    def add_host(self, key, ipaddrs):
        for ipaddr in ipaddrs:
            family, type, proto, canonname, (ip, port, *_) = ipaddr
            if (
                family == socket.AF_INET
                and type == socket.SOCK_STREAM
                and proto == socket.IPPROTO_TCP
            ):
                self.__hosts[key] = ipaddr
                self.__hosts.move_to_end(key, last=False)  # FIFO
                return ipaddr

    def limit_cache(self):
        while len(self.__hosts) > self.__size:
            self.__hosts.popitem()

    def clear(self):
        self.__hosts.clear()
