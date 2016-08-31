# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import asyncio

from mugen.session import Session
from mugen.models import MAX_CONNECTION_POOL, MAX_POOL_TASKS


@asyncio.coroutine
def head(url,
         params=None,
         headers=None,
         cookies=None,
         proxy=None,
         allow_redirects=False,
         recycle=True,
         encoding=None,
         timeout=None,
         loop=None):

    response = yield from request('HEAD', url,
                                   params=params,
                                   headers=headers,
                                   cookies=cookies,
                                   proxy=proxy,
                                   allow_redirects=allow_redirects,
                                   recycle=recycle,
                                   encoding=encoding,
                                   timeout=timeout,
                                   loop=loop)
    return response


@asyncio.coroutine
def get(url,
        params=None,
        headers=None,
        cookies=None,
        proxy=None,
        allow_redirects=True,
        recycle=True,
        encoding=None,
        timeout=None,
        loop=None):

    response = yield from request('GET', url,
                                  params=params,
                                  headers=headers,
                                  cookies=cookies,
                                  proxy=proxy,
                                  allow_redirects=allow_redirects,
                                  recycle=recycle,
                                  encoding=encoding,
                                  timeout=timeout,
                                  loop=loop)
    return response


@asyncio.coroutine
def post(url,
         params=None,
         headers=None,
         data=None,
         cookies=None,
         proxy=None,
         allow_redirects=True,
         recycle=True,
         encoding=None,
         timeout=None,
         loop=None):

    response = yield from request('POST', url,
                                  params=params,
                                  headers=headers,
                                  data=data,
                                  cookies=cookies,
                                  proxy=proxy,
                                  allow_redirects=allow_redirects,
                                  recycle=recycle,
                                  encoding=encoding,
                                  timeout=timeout,
                                  loop=loop)
    return response


@asyncio.coroutine
def request(method, url,
            params=None,
            headers=None,
            data=None,
            cookies=None,
            proxy=None,
            allow_redirects=True,
            recycle=True,
            encoding=None,
            timeout=None,
            loop=None):

    session = Session(recycle=recycle, loop=loop)
    response = yield from session.request(method, url,
                                          params=params,
                                          headers=headers,
                                          data=data,
                                          cookies=cookies,
                                          proxy=proxy,
                                          allow_redirects=allow_redirects,
                                          recycle=recycle,
                                          encoding=encoding,
                                          timeout=timeout)

    return response


def session(recycle=True,
            encoding='utf-8',
            max_pool=MAX_CONNECTION_POOL,
            max_tasks=MAX_POOL_TASKS,
            loop=None):

    return Session(recycle=recycle,
                   encoding='utf-8',
                   max_pool=max_pool,
                   max_tasks=max_tasks,
                   loop=loop)
