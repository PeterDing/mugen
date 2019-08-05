## Mugen - HTTP for Asynchronous Requests

Mugen is library for http asynchronous requests.

Only running on python 3.4.0+

ok, code demo:

```python
import asyncio
import mugen

async def task():
    url = 'https://www.google.com'
    resp = await mugen.get(url)
    print(resp.text)

loop = asyncio.get_event_loop()
loop.run_until_complete(task())
```

See, [Documention](https://peterding.github.io/mugen-docs/).

> Mugen is a name from _Samurai Champloo_ (サムライチャンプル, 混沌武士)

### Feature Support

- Keep-Alive & Connection Pooling
- DNS cache
- Sessions with Cookie Persistence
- Automatic Decompression
- Automatic Content Decoding
- HTTP(S)/SOCKS5 Proxy Support
- Connection Timeouts
