import logging
import asyncio
import mugen

logging.basicConfig(level=logging.DEBUG)


async def task1():
    resp = await mugen.get("http://httpbin.org/cookies/set?k2=v2&k1=v1")
    print(resp.cookies.get_dict())
    print(resp.history)


loop = asyncio.get_event_loop()
tasks = asyncio.wait([task1()])
loop.run_until_complete(tasks)
