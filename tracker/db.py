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
