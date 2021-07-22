from mugen.session import Session
from mugen.models import MAX_CONNECTION_POOL, MAX_POOL_TASKS


async def head(
    url,
    params=None,
    headers=None,
    cookies=None,
    proxy=None,
    proxy_auth=None,
    allow_redirects=False,
    recycle=True,
    encoding=None,
    timeout=None,
    connection=None,
    loop=None,
):
    response = await request(
        "HEAD",
        url,
        params=params,
        headers=headers,
        cookies=cookies,
        proxy=proxy,
        proxy_auth=proxy_auth,
        allow_redirects=allow_redirects,
        recycle=recycle,
        encoding=encoding,
        timeout=timeout,
        connection=connection,
        loop=loop,
    )
    return response


async def get(
    url,
    params=None,
    headers=None,
    cookies=None,
    proxy=None,
    proxy_auth=None,
    allow_redirects=True,
    recycle=True,
    encoding=None,
    timeout=None,
    connection=None,
    loop=None,
):
    response = await request(
        "GET",
        url,
        params=params,
        headers=headers,
        cookies=cookies,
        proxy=proxy,
        proxy_auth=proxy_auth,
        allow_redirects=allow_redirects,
        recycle=recycle,
        encoding=encoding,
        timeout=timeout,
        connection=connection,
        loop=loop,
    )
    return response


async def post(
    url,
    params=None,
    headers=None,
    data=None,
    cookies=None,
    proxy=None,
    proxy_auth=None,
    allow_redirects=True,
    recycle=True,
    encoding=None,
    timeout=None,
    connection=None,
    loop=None,
):
    response = await request(
        "POST",
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
        timeout=timeout,
        connection=connection,
        loop=loop,
    )
    return response


async def request(
    method,
    url,
    params=None,
    headers=None,
    data=None,
    cookies=None,
    proxy=None,
    proxy_auth=None,
    allow_redirects=True,
    recycle=True,
    encoding=None,
    timeout=None,
    connection=None,
    loop=None,
):
    session = Session(recycle=recycle, encoding=encoding, loop=loop)
    response = await session.request(
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
        timeout=timeout,
        connection=connection,
    )

    return response


def session(
    headers=None,
    cookies=None,
    recycle=True,
    encoding=None,
    max_pool=MAX_CONNECTION_POOL,
    max_tasks=MAX_POOL_TASKS,
    loop=None,
):
    return Session(
        headers=headers,
        cookies=cookies,
        recycle=recycle,
        encoding=encoding,
        max_pool=max_pool,
        max_tasks=max_tasks,
        loop=loop,
    )
