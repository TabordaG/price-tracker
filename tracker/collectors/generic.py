"""Coletor genérico via JSON-LD (schema.org) para lojas que bloqueiam servidores.

Magalu, Casas Bahia, Mercado Livre e Amazon recusaram acesso a partir de servidores
nos testes (17/11/2026). Este coletor tenta mesmo assim; se a loja liberar o acesso,
os produtos com JSON-LD são aproveitados. Caso contrário, a loja aparece como
"bloqueada" no relatório. Parte das ofertas da Magalu/iPlace chega pelo marketplace
da Americanas e da Kabum.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from ..models import Offer
from .base import Blocked, client, get

SEARCH = {
    "magalu": ("Magalu", "https://www.magazineluiza.com.br/busca/{q}/"),
    "casasbahia": ("Casas Bahia", "https://www.casasbahia.com.br/{q}/b"),
    "mercadolivre": ("Mercado Livre", "https://lista.mercadolivre.com.br/{q}"),
    "amazon": ("Amazon", "https://www.amazon.com.br/s?k={q}"),
}


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def collect(store_key: str, terms: list[str]) -> list[Offer]:
    name, tpl = SEARCH[store_key]
    out: dict[str, Offer] = {}
    with client() as c:
        for term in terms:
            q = quote(term.replace(" ", "-")) if "{q}/" in tpl or "/{q}" in tpl else quote(term)
            if store_key == "amazon":
                q = quote(term).replace("%20", "+")
            html = get(c, tpl.format(q=q)).text
            if re.search(r"captcha|algo deu errado|não é possível acessar", html[:5000], re.I):
                raise Blocked("captcha/bloqueio")
            for blob in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S):
                try:
                    data = json.loads(blob)
                except json.JSONDecodeError:
                    continue
                for node in _walk(data):
                    if node.get("@type") != "Product":
                        continue
                    offers = node.get("offers") or {}
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    price = offers.get("price") or offers.get("lowPrice")
                    url = node.get("url") or offers.get("url") or ""
                    if not price or not node.get("name") or url in out:
                        continue
                    seller = ((offers.get("seller") or {}).get("name")) or name
                    out[url or node["name"]] = Offer(
                        store=name, seller=seller, title=node["name"], url=url,
                        price=float(str(price).replace(",", ".")),
                        sku=str(node.get("sku") or ""), marketplace=seller.lower() != name.lower(),
                    )
    if not out:
        raise Blocked("nenhum produto legível (provável bloqueio anti-bot)")
    return list(out.values())
