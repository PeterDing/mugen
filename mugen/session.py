import logging
import asyncio
from urllib.parse import urljoin

from mugen.cookies import DictCookie
from mugen.connection_pool import ConnectionPool
from mugen.connect import Connection
from mugen.adapters import HTTPAdapter
from mugen.structures import CaseInsensitiveDict
from mugen.models import (
    Request,
    DNSCache,
    DEFAULT_REDIRECT_LIMIT,
    MAX_CONNECTION_POOL,
    MAX_POOL_TASKS,
    MAX_REDIRECTIONS,
    DEFAULT_ENCODING,
)
from mugen.exceptions import RedirectLoop, TooManyRedirections

logger = logging.getLogger(__name__)


class Session(object):
    def __init__(
        self,
        headers=None,
        cookies=None,
        recycle=True,
        encoding=None,
        max_pool=MAX_CONNECTION_POOL,
        max_tasks=MAX_POOL_TASKS,
        loop=None,
    ):
        logger.debug(
            "instantiate Session: "
            "max_pool: {}, max_tasks: {}, "
            "recycle: {}, encoding: {}".format(max_pool, max_tasks, recycle, encoding)
        )

        self.headers = CaseInsensitiveDict()
        if headers:
            self.headers.update(headers)

        self.cookies = DictCookie()
        if cookies:
            self.cookies = DictCookie.update(cookies)

        self.recycle = recycle
        self.encoding = encoding

        self.max_redirects = DEFAULT_REDIRECT_LIMIT
        self.loop = loop or asyncio.get_event_loop()

        self.connection_pool = ConnectionPool(
            recycle=recycle, max_pool=max_pool, max_tasks=max_tasks, loop=self.loop
        )
        self.adapter = HTTPAdapter(
            self.connection_pool, recycle=recycle, loop=self.loop
        )
        self.dns_cache = DNSCache(loop=self.loop)

    async def request(
        self,
        method,
        url,
        params=None,
        headers=None,
        data=None,
        cookies=None,
        proxy=None,
        proxy_auth=None,
        allow_redirects=True,
        recycle=None,
        encoding=None,
        timeout=None,
        connection=None,
    ):
        if recycle is None:
            recycle = self.recycle

        if allow_redirects:
            response = await asyncio.wait_for(
                self._redirect(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    data=data,
                    cookies=cookies,
                    proxy=proxy,
                    proxy_auth=proxy_auth,
                    allow_redirects=allow_redirects,
                    recycle=recycle,
                    encoding=encoding,
                    connection=connection,
                ),
                timeout=timeout,
            )
        else:
            response = await asyncio.wait_for(
                self._request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    data=data,
                    cookies=cookies,
                    proxy=proxy,
                    proxy_auth=proxy_auth,
                    allow_redirects=allow_redirects,
                    recycle=recycle,
                    encoding=encoding,
                    connection=connection,
                ),
                timeout=timeout,
            )

        return response

    async def _request(
        self,
        method,
        url,
        params=None,
        headers=None,
        data=None,
        cookies=None,
        proxy=None,
        proxy_auth=None,
        allow_redirects=True,
        recycle=None,
        encoding=None,
        connection=None,
    ):
        logger.debug(
            "[Session.request]: "
            "method: {}, "
            "url: {}, "
            "params: {}, "
            "headers: {}, "
            "data: {}, "
            "cookies: {}, "
            "proxy: {}".format(method, url, params, headers, data, cookies, proxy)
        )

        encoding = encoding or self.encoding

        if recycle is None:
            recycle = self.recycle

        if cookies:
            self.cookies.update(cookies)

        if headers is None or not dict(headers):
            headers = self.headers

        request = Request(
            method,
            url,
            params=params,
            headers=headers,
            data=data,
            proxy=proxy,
            proxy_auth=proxy_auth,
            cookies=self.cookies,
            encoding=encoding,
        )

        # Make connection
        if not connection:
            host, *_ = request.url_parse_result.netloc.split(":", 1)
            ssl = request.url_parse_result.scheme.lower() == "https"
            port = request.url_parse_result.port
            if not port:
                port = 443 if ssl else 80

            if proxy:
                conn = await self.adapter.generate_proxy_connect(
                    host, port, ssl, proxy, proxy_auth, self.dns_cache, recycle=recycle
                )
            else:
                conn = await self.adapter.generate_direct_connect(
                    host, port, ssl, self.dns_cache, recycle=recycle
                )
        else:
            if not isinstance(connection, Connection):
                raise TypeError(
                    "connection is NOT an instance of Mugen.connect.Connection"
                )

            conn = connection

        try:
            # send request
            await self.adapter.send_request(conn, request)
        except Exception as err:
            logger.debug("[Session._request]: send_request error, {}".format(err))
            logger.warning("Close connect at request: %s", conn)
            conn.close()
            raise err

        try:
            # receive response
            response = await self.adapter.get_response(method, conn, encoding=encoding)
        except Exception as err:
            logger.debug("[Session._request]: get_response error, {}".format(err))
            logger.warning("Close connect at response: %s", conn)
            conn.close()
            raise err

        # update cookies
        self.cookies.update(response.cookies)
        response.cookies = self.cookies

        if method.lower() != "connect":
            self.connection_pool.recycle_connection(conn)

        return response

    async def _redirect(
        self,
        method,
        url,
        params=None,
        headers=None,
        data=None,
        cookies=None,
        proxy=None,
        proxy_auth=None,
        allow_redirects=True,
        recycle=None,
        encoding=None,
        connection=None,
    ):
        if recycle is None:
            recycle = self.recycle

        history = []
        _URL = url
        base_url = url
        redirect_urls = set()

        while True:
            if len(redirect_urls) > MAX_REDIRECTIONS:
                raise TooManyRedirections(_URL)

            redirect_urls.add(url)
            response = await self._request(
                method,
                url,
                params=params,
                headers=headers,
                data=data,
                cookies=cookies,
                proxy=proxy,
                proxy_auth=proxy_auth,
                allow_redirects=allow_redirects,
                recycle=recycle,
                encoding=encoding,
                connection=connection,
            )

            response.request = Request(
                method,
                url,
                params=params,
                headers=headers,
                data=data,
                proxy=proxy,
                cookies=cookies,
                encoding=encoding,
            )

            if not response.headers.get("Location"):
                response.history = history
                return response

            # XXX, not store responses in self.history, which could be used by other
            # coroutines

            location = response.headers["Location"]
            url = urljoin(base_url, location)
            base_url = url

            if url in redirect_urls:
                raise RedirectLoop(url)

            history.append(response)

    async def head(
        self,
        url,
        params=None,
        headers=None,
        cookies=None,
        proxy=None,
        allow_redirects=False,
        recycle=None,
        encoding=None,
        timeout=None,
        connection=None,
    ):
        if recycle is None:
            recycle = self.recycle

        response = await self.request(
            "HEAD",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            proxy=proxy,
            allow_redirects=allow_redirects,
            recycle=recycle,
            encoding=encoding,
            timeout=timeout,
            connection=connection,
        )
        return response

    async def get(
        self,
        url,
        params=None,
        headers=None,
        cookies=None,
        proxy=None,
        allow_redirects=True,
        recycle=None,
        encoding=None,
        timeout=None,
        connection=None,
    ):
        if recycle is None:
            recycle = self.recycle

        response = await self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            proxy=proxy,
            allow_redirects=allow_redirects,
            recycle=recycle,
            encoding=encoding,
            timeout=timeout,
            connection=connection,
        )
        return response

    async def post(
        self,
        url,
        params=None,
        headers=None,
        data=None,
        cookies=None,
        proxy=None,
        allow_redirects=True,
        recycle=None,
        encoding=None,
        timeout=None,
        connection=None,
    ):
        if recycle is None:
            recycle = self.recycle

        response = await self.request(
            "POST",
            url,
            params=params,
            headers=headers,
            data=data,
            cookies=cookies,
            proxy=proxy,
            allow_redirects=allow_redirects,
            recycle=recycle,
            encoding=encoding,
            timeout=timeout,
            connection=connection,
        )
        return response

    def clear(self):
        """
        Reset cookies and headers to empty
        """

        self.cookies.clear()
        self.headers = None

    def close(self):
        """
        Close this session, all connections and dns cache will be cleaned.
        cookies will be set to None
        """

        # self.adapter.close()   # No sense
        self.connection_pool.clear()
        self.dns_cache.clear()
        self.headers = self.cookies = self.dns_cache = None
