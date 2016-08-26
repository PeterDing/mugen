# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

from collections import MutableMapping, OrderedDict


class CaseInsensitiveDict(MutableMapping):

    def __init__(self, *args, **kwargs):
        self._store = OrderedDict()
        self._map = {}

        self.update(*args, **kwargs)

    def __getitem__(self, key):
        if isinstance(key, str):
            key = key.lower()

        return self._store[key]


    def __setitem__(self, key, value):
        if isinstance(key, str):
            lower_key = key.lower()
        else:
            lower_key = key

        self._store[lower_key] = value
        self._map[lower_key] = key


    def __delitem__(self, key):
        if isinstance(key, str):
            key = key.lower()

        self._store.pop(key)
        self._map.pop(key)


    def __iter__(self):
        for k in self._map.values():
            yield k


    def __len__(self):
        return len(self._store)


