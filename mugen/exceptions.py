class NotFindIP(Exception):
    pass


class RedirectLoop(Exception):
    pass


class TooManyRedirections(Exception):
    pass


class ConnectionIsStale(Exception):
    pass


class UnknownProxyScheme(Exception):
    pass


class CanNotCreateConnect(Exception):
    pass
