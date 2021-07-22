from typing import Union
import json
import re
import gzip
import zlib
import base64
from urllib.parse import quote as url_quote
from urllib.parse import urlparse

from mugen.cookies import DictCookie
from mugen.structures import CaseInsensitiveDict


def default_headers():
    return {
        "User-Agent": "mugen",
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "Connection": "Keep-Alive",
    }


def str_encode(dt, encoding="utf-8"):
    """
    check dt type, then encoding
    """

    if isinstance(dt, str):
        return dt.encode(encoding) if encoding else dt
    elif isinstance(dt, bytes):
        return dt
    else:
        raise TypeError("argument must be str or bytes, NOT {!r}".format(dt))


def form_encode(data):
    """
    form-encode data
    """

    assert isinstance(data, dict), "data must be dict like"

    enc_data = "&".join(
        [
            "{}={}".format(
                k,
                url_quote(
                    v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
                ),
            )
            for k, v in data.items()
        ]
    )
    return enc_data


def url_params_encode(params):
    if isinstance(params, str):
        return params
    elif isinstance(params, bytes):
        return params
    elif isinstance(params, dict):
        _params = []
        for k, v in params.items():
            _params.append(k + "=" + v)
        return "&".join(_params)
    else:
        raise TypeError(
            "argument must be str or bytes or dict, NOT {!r}".format(params)
        )


_re_ip = re.compile(r"^(http://|https://|)\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}")


def is_ip(netloc):
    return _re_ip.search(netloc) is not None


def parse_headers(lines):
    headers = CaseInsensitiveDict()
    cookies = DictCookie()

    protocol, status_code, ok = lines[0].decode("utf-8").split(" ", 2)

    for line in lines[1:]:
        line = line.decode("utf-8").strip()
        if not line:
            continue

        index = line.find(": ")
        key = line[:index]
        value = line[index + 2 :]

        if key.lower() == "set-cookie":
            cookies.load(value)
            if headers.get(key):
                headers[key] += ", " + value
        else:
            headers[key] = value

    return (protocol, status_code, ok), headers, cookies


def parse_proxy(proxy_url):
    parser = urlparse(proxy_url)

    proxy_scheme = parser.scheme
    if "@" in parser.netloc:
        user_pwd, host_port = parser.netloc.split("@", 1)
        proxy_host, pt = host_port.split(":", 1)
        proxy_port = int(pt)
        username, password = user_pwd.split(":", 1)
    else:
        proxy_host = parser.netloc.split(":")[0]
        proxy_port = parser.port
        username = None
        password = None
    return proxy_scheme, proxy_host, proxy_port, username, password


def decode_gzip(content):
    assert isinstance(content, bytes)
    return gzip.decompress(content)


def decode_deflate(content):
    assert isinstance(content, bytes)
    try:
        return zlib.decompress(content)
    except Exception:
        return zlib.decompress(content, -zlib.MAX_WBITS)


def find_encoding(content_type):
    if "charset" in content_type.lower():
        chucks = content_type.split(";")
        for chuck in chucks:
            if "charset" in chuck.lower():
                cks = chuck.split("=")
                if len(cks) == 1:
                    return None
                else:
                    return cks[-1].strip()


def base64encode(buf: Union[str, bytes]) -> str:
    if isinstance(buf, str):
        buf = buf.encode("utf-8")

    return base64.b64encode(buf).decode("utf-8")
