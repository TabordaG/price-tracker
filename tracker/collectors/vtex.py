"""Lojas na plataforma VTEX (API pública Intelligent Search)."""
from __future__ import annotations

from urllib.parse import quote

from ..models import Offer
from .base import client, get

STORES = {
    "americanas": ("Americanas", "https://www.americanas.com.br", {"americanas sa", "americanas"}),
    "carrefour": ("Carrefour", "https://www.carrefour.com.br", {"carrefour"}),
}


def collect(store_key: str, terms: list[str], max_pages: int = 6) -> list[Offer]:
    name, base, own = STORES[store_key]
    out: dict[tuple, Offer] = {}
    with client() as c:
        for term in terms:
            for page in range(1, max_pages + 1):
                url = (f"{base}/api/io/_v/api/intelligent-search/product_search/"
                       f"?query={quote(term)}&count=50&page={page}&locale=pt-BR&hideUnavailableItems=true")
                d = get(c, url).json()
                prods = d.get("products") or []
                for p in prods:
                    for it in p.get("items", []):
                        for s in it.get("sellers", []):
                            co = s.get("commertialOffer") or {}
                            if not co.get("Price") or not co.get("AvailableQuantity"):
                                continue
                            k = (it.get("itemId"), s.get("sellerId"))
                            if k in out:
                                continue
                            insts = co.get("Installments") or []
                            best = max(insts, key=lambda x: x.get("NumberOfInstallments", 0), default={})
                            spot = co.get("spotPrice") or co["Price"]
                            teasers = [t.get("name", "") for t in co.get("teasers") or []]
                            hl = [h.get("name", "") for h in co.get("discountHighlights") or []]
                            seller = s.get("sellerName") or name
                            desc = (p.get("description") or "")[:600]
                            o = Offer(
                                store=name,
                                seller=seller,
                                title=it.get("nameComplete") or p.get("productName", ""),
                                url=f"{base}/{p.get('linkText')}/p?idsku={it.get('itemId')}",
                                price=float(min(spot, co["Price"])),
                                list_price=float(co.get("ListPrice") or 0) or None,
                                installments=best.get("NumberOfInstallments"),
                                installment_total=best.get("TotalValuePlusInterestRate"),
                                sku=str(it.get("itemId")),
                                ean=str(it.get("ean") or ""),
                                promo=" | ".join(x for x in teasers + hl if x)[:300],
                                marketplace=seller.strip().lower() not in own,
                            )
                            o._extra = desc  # type: ignore[attr-defined]
                            out[k] = o
                last = (d.get("pagination") or {}).get("count") or 1
                if page >= last or not prods:
                    break
    return list(out.values())
