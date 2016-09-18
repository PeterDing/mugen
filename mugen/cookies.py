# -*- coding: utf-8 -*-

from http.cookies import BaseCookie, Morsel


class DictCookie(BaseCookie):

    def __init__(self, *args, **kwargs):
        super(DictCookie, self).__init__(*args, **kwargs)

    def get_dict(self):
        dictionary = {}
        for key, value in self.items():
            if isinstance(value, Morsel):
                value = value.value

            dictionary[key] = value
        return dictionary
