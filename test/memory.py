import asyncio
import time
from mugen.session import Session


async def task():
    session = Session()
    while True:
        url = "http://www.baidu.com"
        resp = await session.request("GET", url)
        print(time.time(), len(resp.content))


loop = asyncio.get_event_loop()
loop.run_until_complete(task())
