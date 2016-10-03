Mugen - HTTP for Asynchronous Requests
======================================

Mugen is library for http asynchronous requests.

Only running on python 3.4.0+

ok, code demo:

.. code-block:: python

    import asyncio
    import mugen

    @asyncio.coroutine
    def task():
        url = 'http://www.google.com'
        resp = yield from mugen.get(url)
        print(resp.text)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(task())


Mugen is a name from *Samurai Champloo* (サムライチャンプル, 混沌武士)


Feature Support
---------------

-   Keep-Alive & Connection Pooling
-   DNS cache
-   Sessions with Cookie Persistence
-   Automatic Decompression
-   Automatic Content Decoding
-   HTTP Proxy Support

