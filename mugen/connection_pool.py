# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import logging
import asyncio

from collections import defaultdict, deque

from mugen.connect import Connection
from mugen.models import (
    Singleton,
    MAX_CONNECTION_POOL,
    MAX_POOL_TASKS,
    DEFAULT_RECHECK_INTERNAL
)
from mugen.proxy import _make_https_proxy_connection



class ConnectionPool(Singleton):
    '''
    recycle is True, restore connections for reuse
    '''

    def __init__(self,
                 recycle=True,
                 max_pool=MAX_CONNECTION_POOL,
                 max_tasks=MAX_POOL_TASKS,
                 recheck_internal=DEFAULT_RECHECK_INTERNAL,
                 loop=None):

        if hasattr(self, '_initiated'):
            return None

        logging.debug('instantiate ConnectionPool')

        self._initiated = True
        self.recycle = recycle
        self.max_pool = max_pool     # overall pool
        self.max_tasks = max_tasks   # per-key limit
        self.loop = loop or asyncio.get_event_loop()
        self.__connections = defaultdict(deque)
        self.__connection_sizes = defaultdict(int)
        self.__recheck_internal = recheck_internal
        self.__call_count = 0


    def __repr__(self):
        return ('<ConnectionPool: ' + 'connections: ' + ', '.join(
            ['{}: {}'.format(key, len(conns))
                for key, conns in self.__connections.items()])
             + ' pool_size: {}'.format(len(self.__connections))
             + '>'
        )


    def get_connections(self, key):
        return self.__connections[key]


    @asyncio.coroutine
    def get_connection(self, key, recycle=None):
        logging.debug(
            '[ConnectionPool.get_connection]: '
            '{}, recycle: {}'.format(key, recycle))

        # recheck connections at each self.__recheck_internal
        self.__call_count = (self.__call_count + 1) % self.__recheck_internal
        if self.__call_count == 0:
            self.recheck_connections()

        if recycle is None:
            recycle = self.recycle

        if recycle is False:
            return self.make_connection(key, recycle=recycle)

        conns = self.__connections[key]
        while len(conns):
            conn = conns.popleft()
            self.count_connections(key, -1)
            if not conn.stale():
                return conn
            else:
                conn.close()

        if not conns:
            del self.__connections[key]

        if isinstance(key[-1], bool):
            conn = self.make_connection(key, recycle=recycle)
        else:
            conn = yield from _make_https_proxy_connection(key, recycle=recycle)
        return conn


    def make_connection(self, key, recycle=None):
        logging.debug('[ConnectionPool.make_connection]'
                      ': {}, recycle: {}'.format(key, recycle))

        if recycle is None:
            recycle = self.recycle

        ip, port, ssl = key
        conn = Connection(ip, port, ssl=ssl, recycle=recycle, loop=self.loop)
        return conn


    def recycle_connection(self, conn):
        logging.debug('[ConnectionPool.recycle_connection]: {}'.format(conn))

        if conn.recycle and not conn.stale():
            key = conn.key
            conns = self.__connections[key]
            if len(conns) < self.max_tasks and \
                    len(self.__connections) < self.max_pool:
                conns.append(conn)
                self.count_connections(key, 1)
                return None
        conn.close()


    def recheck_connections(self):
        logging.debug('[ConnectionPool.recheck_connections]: {!r}'.format(self))

        empty_conns = []
        for key in self.__connections:
            # to ignore "RuntimeError: dictionary changed size during iteration"
            # when iterating a dictionary
            conns = self.__connections[key]
            conn_num = len(conns)
            for _ in range(conn_num):
                conn = conns.popleft()
                self.count_connections(key, -1)
                self.recycle_connection(conn)
            if not conns:
                empty_conns.append(key)

        for key in empty_conns:
            del self.__connections[key]


    def count_connections(self, key, incr):
        if self.__connection_sizes[key] > 0:
            self.__connection_sizes[key] += incr
        else:
            del self.__connection_sizes[key]


    def clear(self):
        """
        Close all connnections
        """

        logging.debug('[ConnectionPool.clear]')

        for key in self.__connections:
            conns = self.__connections[key]
            while len(conns):
                conn = conns.popleft()
                self.count_connections(key, -1)
                conn.recycle = False
                conn.close()

        self.__connections.clear()


    def closed(self):
        return self._initiated is None and self.__connections is None


    def close(self):
        """
        clear connection_pool and reset the instance to uninitiated
        """

        self.clear()
        self._initiated = self.__connections = None
        self.__connection_sizes = self.loop = None
