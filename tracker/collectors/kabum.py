from __future__ import annotations

import json
from urllib.parse import quote

from ..models import Offer
from .base import client, get, next_data

STORE = "Kabum"


def collect(terms: list[str]) -> list[Offer]:
    out: dict[int, Offer] = {}
    with client() as c:
        for term in terms:
            slug = quote(term.replace(" ", "-"))
            page, pages = 1, 1
            while page <= pages and page <= 10:
                r = get(c, f"https://www.kabum.com.br/busca/{slug}?page_number={page}")
                data = next_data(r.text)["props"]["pageProps"]["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                cat = data["catalogServer"]
                if isinstance(cat, str):
                    cat = json.loads(cat)
                pages = cat.get("meta", {}).get("totalPagesCount", 1) or 1
                for p in cat.get("data", []):
                    if p["code"] in out:
                        continue
                    fl = p.get("flags") or {}
                    offer = p.get("offer") or {}
                    # Preço à vista: o menor entre desconto PIX normal e o da campanha ativa
                    cands = [p.get("priceWithDiscount"), offer.get("priceWithDiscount"), p.get("price")]
                    price = min(x for x in cands if x)
                    n_inst, inst_total = None, None
                    mi = p.get("maxInstallment") or ""
                    if "x de R$" in mi:
                        try:
                            n = int(mi.split("x")[0])
                            v = float(mi.split("R$")[1].strip().replace(".", "").replace(",", "."))
                            n_inst, inst_total = n, round(n * v, 2)
                        except ValueError:
                            pass
                    o = Offer(
                        store=STORE,
                        seller=p.get("sellerName") or STORE,
                        title=p["name"],
                        url=f"https://www.kabum.com.br/produto/{p['code']}/{p.get('friendlyName', '')}",
                        price=float(price),
                        list_price=float(p.get("oldPrice") or p.get("price") or 0) or None,
                        installments=n_inst,
                        installment_total=inst_total,
                        sku=str(p["code"]),
                        promo=offer.get("name") or "",
                        available=bool(p.get("available", True)),
                        marketplace=bool(fl.get("isMarketplace")),
                    )
                    if fl.get("isOpenbox"):
                        o.condition = "vitrine"
                    out[p["code"]] = o
                page += 1
    return list(out.values())
