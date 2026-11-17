from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Offer

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
  date TEXT NOT NULL, ts TEXT NOT NULL, store TEXT NOT NULL, seller TEXT, title TEXT, url TEXT,
  price REAL NOT NULL, list_price REAL, installment_total REAL, installments INTEGER,
  sku TEXT, ean TEXT, promo TEXT, marketplace INTEGER, model TEXT, generation INTEGER,
  storage TEXT, color TEXT, condition TEXT, tags TEXT
);
CREATE INDEX IF NOT EXISTS ix_offers_key ON offers(model, condition, date);
CREATE TABLE IF NOT EXISTS runs (
  date TEXT NOT NULL, ts TEXT NOT NULL, store TEXT NOT NULL, status TEXT NOT NULL,
  n_raw INTEGER, n_offers INTEGER, error TEXT
);
"""

COLS = ["date", "ts", "store", "seller", "title", "url", "price", "list_price", "installment_total",
        "installments", "sku", "ean", "promo", "marketplace", "model", "generation", "storage",
        "color", "condition", "tags"]


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def save_store(con: sqlite3.Connection, date: str, ts: str, store: str, offers: list[Offer],
               status: str, n_raw: int, error: str = "") -> None:
    """Substitui os dados da loja no dia (re-execuções no mesmo dia não duplicam)."""
    with con:
        if status == "ok":
            con.execute("DELETE FROM offers WHERE date=? AND store=?", (date, store))
            rows = []
            for o in offers:
                d = o.to_dict()
                d.update(date=date, ts=ts, marketplace=int(o.marketplace))
                rows.append([d.get(c) for c in COLS])
            con.executemany(f"INSERT INTO offers ({','.join(COLS)}) VALUES ({','.join('?' * len(COLS))})", rows)
        con.execute("DELETE FROM runs WHERE date=? AND store=?", (date, store))
        con.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?)", (date, ts, store, status, n_raw, len(offers), error[:500]))


def save_manual(con: sqlite3.Connection, date: str, ts: str, offers: list[Offer]) -> None:
    """Ofertas manuais: gravadas com a loja real, marcadas pela tag 'cadastro manual'."""
    with con:
        con.execute("DELETE FROM offers WHERE date=? AND tags LIKE '%cadastro manual%'", (date,))
        for o in offers:
            d = o.to_dict()
            d.update(date=date, ts=ts, marketplace=int(o.marketplace))
            con.execute(f"INSERT INTO offers ({','.join(COLS)}) VALUES ({','.join('?' * len(COLS))})",
                        [d.get(c) for c in COLS])
        con.execute("DELETE FROM runs WHERE date=? AND store='Manual'", (date,))
        con.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?)", (date, ts, "Manual", "ok", len(offers), len(offers), ""))


def flag_suspicious(con: sqlite3.Connection, date: str, ratio: float = 0.6) -> int:
    """Marca 'preço suspeito' quando o preço é menor que 60% da mediana do mesmo modelo/condição no dia.

    Pega anúncio com preço errado, de sinal/reserva ou golpe. Fica fora dos alertas e do histórico.
    """
    from statistics import median
    rows = con.execute("SELECT rowid, model, condition, price, tags FROM offers WHERE date=?", (date,)).fetchall()
    groups: dict[tuple, list[float]] = {}
    for r in rows:
        groups.setdefault((r["model"], r["condition"]), []).append(r["price"])
    n = 0
    with con:
        for r in rows:
            prices = groups[(r["model"], r["condition"])]
            if len(prices) >= 3 and r["price"] < median(prices) * ratio and "suspeito" not in (r["tags"] or ""):
                con.execute("UPDATE offers SET tags=? WHERE rowid=?", ((r["tags"] or "") + ",preço suspeito", r["rowid"]))
                n += 1
    return n
