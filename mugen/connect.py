import re
import time
import logging
import asyncio
from asyncio import streams

from functools import wraps

from mugen.exceptions import ConnectionIsStale
from mugen.models import MAX_CONNECTION_TIMEOUT, MAX_KEEP_ALIVE_TIME

logger = logging.getLogger(__name__)


def async_error_proof(gen):
    @wraps(gen)
    async def wrap(self, *args, **kwargs):
        try:
            rs = await gen(self, *args, **kwargs)
            return rs
        except Exception as err:
            logger.error("[{}]: {}".format(gen, repr(err)))
            self.close()
            raise err

    return wrap


def error_proof(func):
    @wraps(func)
    def wrap(self, *args, **kwargs):
        try:
            rs = func(self, *args, **kwargs)
            return rs
        except Exception as err:
            logger.error("[{}]: {}".format(func, repr(err)))
            self.close()
            raise err

    return wrap


FD_USED_ERROR = re.compile(r"File descriptor (\d+) is used by transport")


class Connection(object):
    def __init__(
        self, ip, port, ssl=False, key=None, recycle=True, timeout=None, loop=None
    ):
        self.ip = ip
        self.port = port
        self.ssl = ssl
        self.key = key or (ip, port, ssl)
        self.recycle = recycle
        self.loop = loop or asyncio.get_event_loop()
        self.reader = None
        self.writer = None
        self.ssl_on = False  # For http/socks proxy which need ssl connection
        self.socks_on = False  # socks proxy which needs to be initiated
        self.timeout = timeout or MAX_KEEP_ALIVE_TIME
        self.__last_action = time.time()

    def __repr__(self):
        return "<Connection: {!r}>".format(self.key)

    def _watch(self):
        self.__last_action = time.time()
        return self.__last_action

    def is_timeout(self):
        return time.time() - self.__last_action > self.timeout

    @async_error_proof
    async def connect(self):
        logger.debug(f"[Connection.connect]: {self.key}")

        try:
            reader, writer = await streams.open_connection(
                self.ip, self.port, ssl=self.ssl
            )
        except RuntimeError as err:
            logger.error("[Connection.connect]: %s:%s, %s", self.ip, self.port, err)
            info = str(err)

            # If the fd is used, we remove it
            m = FD_USED_ERROR.search(info)
            if m:
                fd = int(m.group(1))
                transp = self.loop._transports[fd]
                if transp:
                    transp.close()
                del self.loop._transports[fd]

            raise err
        except Exception as err:
            logger.error("[Connection.connect]: %s:%s, %s", self.ip, self.port, err)
            raise err

        self.reader = reader
        self.writer = writer

    @async_error_proof
    async def ssl_handshake(self, host):
        logger.debug("[Connection.ssl_handshake]: {}, {}".format(self.key, host))
        transport = self.reader._transport
        raw_socket = transport.get_extra_info("socket", default=None)
        self.reader, self.writer = await streams.open_connection(
            ssl=True, sock=raw_socket, server_hostname=host
        )

    @error_proof
    def send(self, data):
        logger.debug("[Connection.send]: {!r}".format(data))
        self._watch()

        self.writer.write(data)

    @async_error_proof
    async def read(self, size=-1):
        logger.debug("[Connection.read]: {}: size = {}".format(self.key, size))
        self._watch()
        # assert self.closed() is not True, 'connection is closed'
        # assert self.stale() is not True, 'connection is stale'

        if self.stale():
            logger.debug(
                "[Connection.read] [Error] [ConnectionIsStale]: {}".format(self.key)
            )
            raise ConnectionIsStale("{}".format(self.key))

        if size < 0:
            chunk = await asyncio.wait_for(
                self.reader.read(size), timeout=MAX_CONNECTION_TIMEOUT
            )
            return chunk
        else:
            chunks = b""
            while size:
                chunk = await asyncio.wait_for(
                    self.reader.read(size), timeout=MAX_CONNECTION_TIMEOUT
                )
                size -= len(chunk)
                chunks += chunk
            return chunks

    @async_error_proof
    async def readline(self):
        # assert self.closed() is False, 'connection is closed'
        # assert self.stale() is not True, 'connection is stale'

        if self.stale():
            logger.debug(
                "[Connection.readline] [Error] [ConnectionIsStale]: {}".format(self.key)
            )
            raise ConnectionIsStale("{}".format(self.key))

        chunk = await asyncio.wait_for(
            self.reader.readline(), timeout=MAX_CONNECTION_TIMEOUT
        )

        logger.debug(
            "[Connection.readline]: " "{}: size = {}".format(self.key, len(chunk))
        )

        return chunk

    def close(self):
        logger.debug(
            "[Connection.close]: {}, " "recycle: {}".format(self.key, self.recycle)
        )

        if not self.closed():
            self.reader.feed_eof()
            self.writer.close()
            self.reader = self.writer = None
            logger.debug(
                "[Connection.close]: DONE. {}, recycle: {}".format(
                    self.key, self.recycle
                )
            )

    def closed(self):
        return self.reader is None or self.writer is None

    def stale(self):
        is_stale = self.reader is None or self.reader.at_eof()
        if is_stale:
            logger.debug("[Connection.stale]: {} is stale".format(self.key))
        return is_stale
