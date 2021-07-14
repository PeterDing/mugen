import logging
import asyncio
import mugen

logging.basicConfig(level=logging.DEBUG)


async def task1():
    resp = await mugen.get("http://httpbin.org/ip", timeout=1)
    print(list(resp.headers.items()))
    print(resp.text)
    print(len(resp.content))


loop = asyncio.get_event_loop()
tasks = asyncio.wait([task1()])
loop.run_until_complete(tasks)
