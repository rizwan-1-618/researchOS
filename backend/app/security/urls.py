from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UrlRejected(ValueError):
    pass


def assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UrlRejected("Only public http(s) URLs can be fetched")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port)
    except socket.gaierror as exc:
        raise UrlRejected("Could not resolve the PDF host") from exc
    if not infos:
        raise UrlRejected("Could not resolve the PDF host")
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise UrlRejected("That PDF host is not public")
