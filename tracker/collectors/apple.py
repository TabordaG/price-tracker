"""Apple Store Brasil (preço oficial de referência)."""
from __future__ import annotations

import re

from ..models import Offer
from .base import client, get

BASE = "https://www.apple.com/br/shop/buy-iphone"
FAMILY_NAMES = {
    "promax": " Pro Max", "pro": " Pro", "plus": " Plus", "e": "e", "": "",
}


def _family_to_title(fam: str) -> str:
    # ex.: iphone18promax -> iPhone 18 Pro Max ; iphoneair -> iPhone Air
    m = re.match(r"iphone(\d+)(promax|pro|plus|e)?$", fam)
    if m:
        return f"iPhone {m.group(1)}{FAMILY_NAMES[m.group(2) or '']}"
    m = re.match(r"iphone([a-z]+)$", fam)
    return f"iPhone {m.group(1).capitalize()}" if m else fam


def collect(_terms: list[str]) -> list[Offer]:
    out: list[Offer] = []
    with client() as c:
        idx = get(c, BASE).text
        slugs = sorted(set(re.findall(r'/br/shop/buy-iphone/(iphone-[a-z0-9-]+?)["/?]', idx)))
        for slug in slugs:
            html = get(c, f"{BASE}/{slug}").text
            prices = {
                k: float(v)
                for k, v in re.findall(r'"([a-z0-9]+_a)":\{"product":"[^"]+"[^{}]*?"amountBeforeTradeIn":([\d.]+)', html)
            }
            seen = set()
            for chunk in html.split('{"partNumber":"')[1:]:
                chunk = chunk[:3000]
                f = {k: (re.search(rf'"{k}":"([^"]*)"', chunk) or [None, ""])[1]
                     for k in ("familyType", "fullPrice", "dimensionCapacity", "dimensionColor")}
                part = chunk.split('"', 1)[0]
                if f["dimensionCapacity"] != "512gb" or part in seen or f["fullPrice"] not in prices:
                    continue
                seen.add(part)
                price = prices[f["fullPrice"]]
                out.append(Offer(
                    store="Apple Store",
                    seller="Apple",
                    title=f"{_family_to_title(f['familyType'])} 512GB {f['dimensionColor']}",
                    url=f"{BASE}/{slug}",
                    price=price,
                    list_price=price,
                    sku=part,
                ))
    return out
