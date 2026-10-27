from __future__ import annotations

import asyncio

import httpx

from app.config import settings


class IntegrationError(Exception):
    def __init__(self, source: str, detail: str):
        self.source = source
        self.detail = detail
        super().__init__(detail)


def user_agent() -> str:
    if settings.contact_email:
        return f"ResearchOS/1.0 (mailto:{settings.contact_email})"
    return "ResearchOS/1.0"


def retry_delay(header: str | None) -> float:
    if not header:
        return settings.retry_after_default_seconds
    try:
        return min(float(header), settings.retry_after_cap_seconds)
    except ValueError:
        return settings.retry_after_default_seconds


async def request_json(
    http: httpx.AsyncClient,
    source: str,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
) -> dict | list:
    request_headers = {"User-Agent": user_agent(), **(headers or {})}
    clean_params = {key: value for key, value in (params or {}).items() if value is not None}
    try:
        response = await http.get(url, params=clean_params, headers=request_headers)
        if response.status_code == 429:
            await asyncio.sleep(retry_delay(response.headers.get("Retry-After")))
            response = await http.get(url, params=clean_params, headers=request_headers)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise IntegrationError(source, "The source did not respond") from exc


async def request_text(
    http: httpx.AsyncClient,
    source: str,
    url: str,
    *,
    params: dict | None = None,
) -> str:
    headers = {"User-Agent": user_agent()}
    try:
        response = await http.get(url, params=params, headers=headers)
        if response.status_code == 429:
            await asyncio.sleep(retry_delay(response.headers.get("Retry-After")))
            response = await http.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError as exc:
        raise IntegrationError(source, "The source did not respond") from exc
