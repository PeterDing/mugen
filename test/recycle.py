import asyncio
import mugen
import logging

logging.basicConfig(level=logging.DEBUG)


async def task1():
    session = mugen.session(recycle=False)

    await session.get("http://baidu.com")

    print(session.connection_pool)


loop = asyncio.get_event_loop()
tasks = asyncio.wait([task1()])
loop.run_until_complete(tasks)
