import logging
import asyncio

from mugen.utils import is_ip, parse_proxy
from mugen.exceptions import UnknownProxyScheme
from mugen.proxy import _make_https_proxy_connection, Socks5Proxy
from mugen.models import Singleton, Response, DEFAULT_ENCODING

logger = logging.getLogger(__name__)


class HTTPAdapter(Singleton):
    def __init__(self, connection_pool, recycle=True, loop=None):
        if hasattr(self, "_initiated"):
            return

        logger.debug("instantiate HTTPAdapter: recycle: {}, ".format(recycle))

        self._initiated = True
        self.recycle = recycle
        self.loop = loop or asyncio.get_event_loop()
        self.connection_pool = connection_pool

    async def generate_direct_connect(self, host, port, ssl, dns_cache, recycle=True):
        key = None
        if is_ip(host):
            ip = host.split(":")[0]
            key = (ip, port, ssl)

        if not key and not ssl:
            ip, port = await dns_cache.get(host, port)
            key = (ip, port, ssl)

        if not key and ssl:
            key = (host, port, ssl)

        conn = await self.get_connection(key, recycle=recycle)
        return conn

    async def generate_proxy_connect(
        self, host, port, ssl, proxy, proxy_auth, dns_cache, recycle=True
    ):
        proxy_scheme, proxy_host, proxy_port, username, password = parse_proxy(proxy)
        if not proxy_auth and username and password:
            proxy_auth = f"{username}:{password}"

        proxy_ip, proxy_port = await dns_cache.get(proxy_host, proxy_port)
        key = (proxy_ip, proxy_port, False, host)

        if proxy_scheme.lower() == "http":
            if not ssl:
                key = (
                    proxy_ip,
                    proxy_port,
                    False,
                )  # http proxy not needs CONNECT request
            conn = await self.generate_http_proxy_connect(
                key, host, port, ssl, proxy_auth, recycle=recycle
            )
        elif proxy_scheme.lower() == "socks5":
            conn = await self.generate_socks5_proxy_connect(
                key, host, port, ssl, username, password, recycle=recycle
            )
        else:
            raise UnknownProxyScheme(proxy_scheme)

        return conn

    async def generate_http_proxy_connect(
        self, key, host, port, ssl, proxy_auth, recycle=True
    ):
        conn = await self.get_connection(key, recycle=recycle)

        if ssl and not conn.ssl_on:
            logger.debug("[ssl_handshake]: {}".format(key))
            await _make_https_proxy_connection(
                conn, host, port, proxy_auth, recycle=recycle
            )
            conn.ssl_on = True
        return conn

    async def generate_socks5_proxy_connect(
        self, key, host, port, ssl, username, password, recycle=True
    ):
        conn = await self.get_connection(key, recycle=recycle)
        if conn.socks_on:
            return conn

        socks5_proxy = Socks5Proxy(conn, host, port, ssl, username, password)
        await socks5_proxy.init()
        return conn

    async def get_connection(self, key, recycle=True):
        conn = await self.connection_pool.get_connection(key, recycle=recycle)
        if not conn.reader:
            try:
                await conn.connect()
            except Exception as err:
                logger.debug("Fail connect to %s, error: %s", key, err)
                conn.close()
                raise err
        return conn

    async def send_request(self, conn, request):
        request_line, headers, data = request.make_request()
        request_line = request_line.encode("utf-8")
        headers = headers.encode("utf-8")
        if isinstance(data, str):
            data = data.encode("utf-8")

        conn.send(request_line + b"\r\n")
        conn.send(headers + b"\r\n")
        conn.send(b"\r\n")
        if data:
            conn.send(data)

    async def get_response(self, method, conn, encoding=DEFAULT_ENCODING):
        response = Response(method, conn, encoding=encoding)
        await response.receive()

        if response.headers.get("connection") == "close":
            conn.recycle = False
            conn.close()
        return response

    def closed(self):
        return self._initiated is None and self.connection_pool is None

    def close(self):
        self._initiated = self.connection_pool = self.loop = None
