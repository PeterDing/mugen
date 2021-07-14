import asyncio
import mugen


def test():
    loop = asyncio.get_event_loop()

    async def test_recycle():
        session = mugen.session(recycle=False)
        await session.get("http://baidu.com")
        assert len(session.connection_pool) == 0

        session = mugen.session(recycle=True)
        await session.get("http://baidu.com")
        assert len(session.connection_pool) == 1

    loop.run_until_complete(test_recycle())

    async def test_head():
        resp = await mugen.head("http://httpbin.org")
        assert len(resp.headers.items()) > 0
        assert len(resp.text) == 0

    loop.run_until_complete(test_head())

    async def test_get():
        resp = await mugen.get("http://www.baidu.com/")
        assert resp.text.startswith("<!DOCTYPE html><!--STATUS OK-->")

    loop.run_until_complete(test_get())

    async def test_post():
        resp = await mugen.post("http://httpbin.org/post", data={"k": "v"})
        assert resp.json()["form"] == {"k": "v"}

    loop.run_until_complete(test_post())

    async def test_cookies():
        resp = await mugen.get("http://httpbin.org/cookies/set?k2=v2&k1=v1")
        assert resp.cookies.get_dict() == {"k1": "v1", "k2": "v2"}

    loop.run_until_complete(test_cookies())

    async def test_session_cookies():
        ss = mugen.session()
        resp = await ss.get(
            "http://httpbin.org/cookies/set?k2=v2&k1=v1", cookies={"a": 1, "b": 2}
        )

        assert resp.cookies.get_dict() == {"k1": "v1", "k2": "v2", "a": 1, "b": 2}
        assert ss.cookies.get_dict() == {"k1": "v1", "k2": "v2", "a": 1, "b": 2}

    loop.run_until_complete(test_session_cookies())

    async def test_timeout():
        try:
            await mugen.get("http://httpbin.org/ip", timeout=0.01)
            assert "No timeout"
        except Exception as err:
            assert isinstance(err, asyncio.TimeoutError)

    loop.run_until_complete(test_timeout())
