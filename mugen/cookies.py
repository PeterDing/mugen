# -*- coding: utf-8 -*-

import json
import re

from http.cookies import (
    BaseCookie,
    Morsel,
    _LegalKeyChars,
)

_LegalValueChars = _LegalKeyChars + ' \[\]'
_CookiePattern = re.compile(r"""
    (?x)                           # This is a verbose pattern
    \s*                            # Optional whitespace at start of cookie
    (?P<key>                       # Start of group 'key'
    [""" + _LegalKeyChars + r"""]+?   # Any word of at least one letter
    )                              # End of group 'key'
    (                              # Optional group: there may not be a value.
    \s*=\s*                          # Equal Sign
    (?P<val>                         # Start of group 'val'
    "(?:[^\\"]|\\.)*"                  # Any doublequoted string
    |                                  # or
    \w{3},\s[\w\d\s-]{9,11}\s[\d:]{8}\sGMT  # Special case for "expires" attr
    |                                  # or
    [""" + _LegalValueChars + r"""]*      # Any word or empty string
    )                                # End of group 'val'
    )?                             # End of optional value group
    \s*                            # Any number of spaces.
    (\s+|;|$)                      # Ending either at space, semicolon, or EOS.
    """, re.ASCII)                 # May be removed if safe.


class DictCookie(BaseCookie):

    def __init__(self, *args, **kwargs):
        super(DictCookie, self).__init__(*args, **kwargs)


    def __repr__(self):
        return '<DictCookie: {}>'.format(json.dumps(self.get_dict(),
                                                    ensure_ascii=False))


    def get_dict(self):
        dictionary = {}
        for key, value in self.items():
            if isinstance(value, Morsel):
                value = value.value

            dictionary[key] = value
        return dictionary


    def format_cookie(self):
        return ' '.join([
            '{}={};'.format(key, value) for key, value in self.get_dict().items()
        ])


    def _BaseCookie__parse_string(self, str, patt=_CookiePattern):
        BaseCookie._BaseCookie__parse_string(self, str, patt=patt)
