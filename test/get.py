
import logging
import asyncio
import mugen

import uvloop

logging.basicConfig(level=logging.DEBUG)

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


async def task():
    resp = await mugen.get('http://httpbin.org/ip')
    print(list(resp.headers.items()))
    print(resp.text)
    print(len(resp.content))


loop = asyncio.get_event_loop()
tasks = asyncio.wait([task()])
loop.run_until_complete(tasks)

