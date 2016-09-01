# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import logging
import asyncio
from http.cookies import SimpleCookie
from urllib.parse import urljoin

from mugen.connection_pool import ConnectionPool
from mugen.proxy import get_proxy_key
from mugen.adapters import HTTPAdapter
from mugen.models import (
    Request,
    DNSCache,
    DEFAULT_REDIRECT_LIMIT,
    MAX_CONNECTION_POOL,
    MAX_POOL_TASKS
)
from mugen.utils import is_ip
from mugen.exceptions import RedirectLoop


class Session(object):

    def __init__(self,
                 recycle=True,
                 encoding='utf-8',
                 max_pool=MAX_CONNECTION_POOL,
                 max_tasks=MAX_POOL_TASKS,
                 loop=None):

        logging.debug('instantiate Session: '
                      'max_pool: {}, max_tasks: {}, '
                      'recycle: {}, encoding: {}'.format(
                          max_pool, max_tasks, recycle, encoding))

        self.headers = None
        self.cookies = SimpleCookie()
        self.recycle = recycle
        self.encoding = encoding

        self.max_redirects = DEFAULT_REDIRECT_LIMIT
        self.loop = loop or asyncio.get_event_loop()

        self.connection_pool = ConnectionPool(recycle=recycle,
                                              max_pool=max_pool,
                                              max_tasks=max_tasks,
                                              loop=self.loop)
        self.adapter = HTTPAdapter(self.connection_pool,
                                   recycle=recycle,
                                   loop=self.loop)
        self.dns_cache = DNSCache(loop=self.loop)


    @asyncio.coroutine
    def request(self, method, url,
                params=None,
                headers=None,
                data=None,
                cookies=None,
                proxy=None,
                allow_redirects=True,
                recycle=True,
                encoding=None,
                timeout=None):


        if allow_redirects:
            response = yield from asyncio.wait_for(
                self._redirect(method, url,
                               params=params,
                               headers=headers,
                               data=data,
                               cookies=cookies,
                               proxy=proxy,
                               allow_redirects=allow_redirects,
                               recycle=recycle,
                               encoding=encoding),
                timeout=timeout
            )
        else:
            response = yield from asyncio.wait_for(
                self._request(method, url,
                              params=params,
                              headers=headers,
                              data=data,
                              cookies=cookies,
                              proxy=proxy,
                              allow_redirects=allow_redirects,
                              recycle=recycle,
                              encoding=encoding),
                timeout=timeout
            )

        return response


    @asyncio.coroutine
    def _request(self, method, url,
                params=None,
                headers=None,
                data=None,
                cookies=None,
                proxy=None,
                allow_redirects=True,
                recycle=None,
                encoding=None):

        logging.debug('[Session.request]: '
                      'method: {}, '
                      'url: {}, '
                      'params: {}, '
                      'headers: {}, '
                      'data: {}, '
                      'cookies: {}, '
                      'proxy: {}'.format(
                          method,
                          url,
                          params,
                          headers,
                          data,
                          cookies,
                          proxy))

        if recycle is None:
            recycle = self.recycle

        if cookies:
            self.cookies.update(cookies)

        request = Request(method, url,
                          params=params,
                          headers=headers,
                          data=data,
                          proxy=proxy,
                          cookies=self.cookies,
                          encoding=encoding or self.encoding)

        host = request.url_parse_result.netloc
        ssl = request.url_parse_result.scheme == 'https'
        port = request.url_parse_result.port
        if not port:
            port = 443 if ssl else 80

        # handle connection
        key = None
        if proxy:
            key = yield from get_proxy_key(proxy, self.dns_cache)

        if not key and is_ip(host):
            ip = host.split(':')[0]
            key = (ip, port, ssl)

        if not key and not ssl:
            ip, port = yield from self.dns_cache.get(host, port)
            key = (ip, port, ssl)

        if not key and ssl:
            key = (host, port, ssl)

        conn = yield from self.adapter.get_connection(key, recycle=recycle)

        # send request
        yield from self.adapter.send_request(conn, request)

        response = yield from self.adapter.get_response(conn)

        # update cookies
        self.cookies.update(response.cookies)
        response.cookies = self.cookies

        conn.close()

        return response


    @asyncio.coroutine
    def _redirect(self, method, url,
                 params=None,
                 headers=None,
                 data=None,
                 cookies=None,
                 proxy=None,
                 allow_redirects=True,
                 recycle=None,
                 encoding=None):

        if recycle is None:
            recycle = self.recycle

        history = []
        base_url = url
        redirect_urls = set()

        while True:
            redirect_urls.add(url)
            response = yield from self._request(method, url,
                                                params=params,
                                                headers=headers,
                                                data=data,
                                                cookies=cookies,
                                                proxy=proxy,
                                                allow_redirects=allow_redirects,
                                                recycle=recycle,
                                                encoding=encoding)

            if not response.headers.get('Location'):
                response.history = history
                return response

            # XXX, not store responses in self.history, which could be used by other
            # coroutines

            location = response.headers['Location']
            url = urljoin(base_url, location)
            base_url = url

            if url in redirect_urls:
                raise RedirectLoop(url)

            history.append(response)


    @asyncio.coroutine
    def head(self, url,
             params=None,
             headers=None,
             cookies=None,
             proxy=None,
             allow_redirects=False,
             recycle=None,
             encoding=None,
             timeout=None):

        if recycle is None:
            recycle = self.recycle

        response = yield from self.request(
            'HEAD', url,
            params=params,
            headers=headers,
            cookies=cookies,
            proxy=proxy,
            allow_redirects=allow_redirects,
            recycle=recycle,
            encoding=encoding,
            timeout=timeout
        )
        return response


    @asyncio.coroutine
    def get(self, url,
            params=None,
            headers=None,
            cookies=None,
            proxy=None,
            allow_redirects=True,
            recycle=None,
            encoding=None,
            timeout=None):

        if recycle is None:
            recycle = self.recycle

        response = yield from self.request(
            'GET', url,
            params=params,
            headers=headers,
            cookies=cookies,
            proxy=proxy,
            allow_redirects=allow_redirects,
            recycle=recycle,
            encoding=encoding,
            timeout=timeout
        )
        return response


    @asyncio.coroutine
    def post(self, url,
             params=None,
             headers=None,
             data=None,
             cookies=None,
             proxy=None,
             allow_redirects=True,
             recycle=None,
             encoding=None,
             timeout=None):

        if recycle is None:
            recycle = self.recycle

        response = yield from self.request(
            'POST', url,
            params=params,
            headers=headers,
            data=data,
            cookies=cookies,
            proxy=proxy,
            allow_redirects=allow_redirects,
            recycle=recycle,
            encoding=encoding,
            timeout=timeout
        )
        return response


    def close(self):
        self.headers = self.cookies = self.dns_cache = None
