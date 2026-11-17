from __future__ import annotations

import json
import re
import time

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}


class Blocked(Exception):
    """Loja recusou o acesso (anti-bot, 403, captcha)."""


def client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True, http2=False)


def get(c: httpx.Client, url: str, retries: int = 2, **kw) -> httpx.Response:
    last = None
    for i in range(retries + 1):
        try:
            r = c.get(url, **kw)
            if r.status_code in (403, 429, 503):
                raise Blocked(f"HTTP {r.status_code} em {url}")
            if "suspicious-traffic" in r.text[:3000]:
                raise Blocked(f"página de verificação anti-bot em {url}")
            r.raise_for_status()
            return r
        except (httpx.HTTPError, Blocked) as e:
            last = e
            time.sleep(2 + 3 * i)
    raise last  # type: ignore[misc]


def next_data(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise Blocked("__NEXT_DATA__ não encontrado (página mudou ou bloqueio)")
    return json.loads(m.group(1))
