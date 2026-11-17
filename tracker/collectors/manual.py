"""Ofertas cadastradas à mão em `ofertas_manuais.toml`.

Uso: lojas que bloqueiam coleta automática (Amazon, Mercado Livre, Magalu...).
Cada oferta tem uma data de validade; depois dela deixa de entrar no relatório.
"""
from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from ..models import Offer

FILE = Path(__file__).resolve().parents[2] / "ofertas_manuais.toml"
DOMAINS = {
    "amazon.com.br": "Amazon", "mercadolivre.com.br": "Mercado Livre", "magazineluiza.com.br": "Magalu",
    "casasbahia.com.br": "Casas Bahia", "carrefour.com.br": "Carrefour", "fastshop.com.br": "Fast Shop",
    "pontofrio.com.br": "Ponto", "kabum.com.br": "Kabum", "americanas.com.br": "Americanas",
}


def store_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for d, name in DOMAINS.items():
        if host.endswith(d):
            return name
    return host or "Manual"


def collect(_terms: list[str], today: date | None = None) -> list[Offer]:
    if not FILE.exists():
        return []
    today = today or date.today()
    data = tomllib.loads(FILE.read_text())
    out = []
    for o in data.get("oferta", []):
        valid = o.get("valida_ate")
        if valid and date.fromisoformat(str(valid)) < today:
            continue
        url = o["url"].split("?")[0]
        store = o.get("loja") or store_from_url(url)
        off = Offer(
            store=store, seller=o.get("vendedor", store), title=o["titulo"], url=url,
            price=float(o["preco"]), list_price=float(o["preco_de"]) if o.get("preco_de") else None,
            installments=o.get("parcelas"), installment_total=o.get("total_parcelado"),
            promo=o.get("obs", ""), marketplace=bool(o.get("marketplace", False)),
        )
        if o.get("condicao"):
            off.condition = o["condicao"]
        off._manual = True  # type: ignore[attr-defined]
        out.append(off)
    return out
