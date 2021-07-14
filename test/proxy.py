import logging
import asyncio
import mugen

logging.basicConfig(level=logging.DEBUG)


async def task1():
    resp = await mugen.get("https://baidu.com", proxy="https://127.0.0.1:8081")
    print(resp.json())


loop = asyncio.get_event_loop()
tasks = asyncio.wait([task1()])
loop.run_until_complete(tasks)
