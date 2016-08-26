# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import asyncio

from urllib.parse import urlparse

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
