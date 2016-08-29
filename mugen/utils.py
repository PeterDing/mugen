# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import re


def default_headers():
    return {
        'User-Agent': 'mugen',
        'Accept': '*/*',
        'Accept-Encoding': 'deflate, gzip',
        'Connection': 'Keep-Alive',
    }


def str_encode(dt, encoding='utf-8'):
    '''
    check dt type, then encoding
    '''

    if isinstance(dt, str):
        return dt.encode(encoding) if encoding else dt
    elif isinstance(dt, bytes):
        return dt
    else:
        raise TypeError('argument must be str or bytes, NOT {!r}'.format(dt))


def url_params_encode(params):
    if isinstance(params, str):
        return params
    elif isinstance(params, bytes):
        return params
    elif isinstance(params, dict):
        _params = []
        for k, v in params.items():
            _params.append(k + '=' + v)
        return '&'.join(_params)
    else:
        raise TypeError('argument must be str or bytes or dict, NOT {!r}'.format(params))


_re_ip = re.compile(r'^(http://|https://|)\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}')
def is_ip(netloc):
    return _re_ip.search(netloc) is not None
