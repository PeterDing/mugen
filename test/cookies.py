import logging
import asyncio

import mugen
from mugen import session

logging.basicConfig(level=logging.DEBUG)


async def task1():
    resp = await mugen.get("http://httpbin.org/cookies/set?k2=v2&k1=v1")
    print("task1 response cookies", resp.cookies.get_dict())


async def task2():
    ss = session()
    resp = await ss.get(
        "http://httpbin.org/cookies/set?k2=v2&k1=v1", cookies={"a": 1, "b": 2}
    )

    print("task2 response cookies", resp.cookies.get_dict())
    print("task2 session cookies", ss.cookies.get_dict())


loop = asyncio.get_event_loop()
tasks = asyncio.wait([task1(), task2()])
loop.run_until_complete(tasks)
