
import logging
import asyncio
import mugen

logging.basicConfig(level=logging.DEBUG)


async def task1():
    resp = await mugen.get('https://www.v2ex.com', proxy='http://127.0.0.1:8080', recycle=False)
    print(resp.text)


loop = asyncio.get_event_loop()
tasks = asyncio.wait([task1()])
loop.run_until_complete(tasks)

