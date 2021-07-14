import json

from http.cookies import BaseCookie, Morsel


class DictCookie(BaseCookie):
    def __init__(self, *args, **kwargs):
        super(DictCookie, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "<DictCookie: {}>".format(
            json.dumps(self.get_dict(), ensure_ascii=False)
        )

    def get_dict(self):
        dictionary = {}
        for key, value in self.items():
            if isinstance(value, Morsel):
                value = value.value

            dictionary[key] = value
        return dictionary

    def format_cookie(self):
        return " ".join(
            ["{}={};".format(key, value) for key, value in self.get_dict().items()]
        )
