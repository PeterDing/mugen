import logging
import asyncio
import mugen

logging.basicConfig(level=logging.DEBUG)


async def task1():
    resp = await mugen.post("http://httpbin.org/post")
    print("json:", resp.json())


loop = asyncio.get_event_loop()
tasks = asyncio.wait([task1()])
loop.run_until_complete(tasks)
