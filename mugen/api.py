# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import asyncio

from mugen.session import Session


@asyncio.coroutine
def head(url,
         params=None,
         headers=None,
         data=None,
         cookies=None,
         proxy=None,
         recycle=True,
         loop=None):

    response = yield from request('HEAD', url,
                                  params=params,
                                  headers=headers,
                                  data=data,
                                  cookies=cookies,
                                  proxy=proxy,
                                  recycle=recycle)
    return response


@asyncio.coroutine
def get(url,
        params=None,
        headers=None,
        data=None,
        cookies=None,
        proxy=None,
        recycle=True,
        loop=None):

    response = yield from  request('GET', url,
                                   params=params,
                                   headers=headers,
                                   data=data,
                                   cookies=cookies,
                                   proxy=proxy,
                                   recycle=recycle)
    return response


@asyncio.coroutine
def post(url,
         params=None,
         headers=None,
         data=None,
         cookies=None,
         proxy=None,
         recycle=True,
         loop=None):

    response = yield from request('POST', url,
                                  params=params,
                                  headers=headers,
                                  data=data,
                                  cookies=cookies,
                                  proxy=proxy,
                                  recycle=recycle)
    return response


@asyncio.coroutine
def request(method, url,
            params=None,
            headers=None,
            data=None,
            cookies=None,
            proxy=None,
            recycle=True,
            loop=None):

    session = Session(recycle=recycle, loop=loop)
    response = yield from session.request(method, url,
                                          params=params,
                                          headers=headers,
                                          data=data,
                                          cookies=cookies,
                                          proxy=proxy)

    return response
