from __future__ import annotations

from urllib.parse import urljoin

import httpx

from app.config import settings
from app.security.urls import UrlRejected, assert_public_http_url


async def download_public_pdf(http: httpx.AsyncClient, url: str) -> bytes:
    current = url
    for _ in range(settings.pdf_redirect_limit + 1):
        assert_public_http_url(current)
        async with http.stream("GET", current, follow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise UrlRejected("Redirect did not include a location")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > settings.pdf_download_max_bytes:
                    raise UrlRejected("PDF is too large")
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data.startswith(settings.pdf_signature.encode("ascii")):
                raise UrlRejected("The URL did not return a PDF")
            return data
    raise UrlRejected("Too many redirects")
