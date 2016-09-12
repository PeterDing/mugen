# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import


class NotFindIP(Exception): pass

class RedirectLoop(Exception): pass

class TooManyRedirections(Exception): pass

class ConnectionIsStale(Exception): pass
