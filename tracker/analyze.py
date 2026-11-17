"""Estatísticas de histórico e geração de alertas."""
from __future__ import annotations

import sqlite3
from datetime import date as Date, timedelta
from statistics import median

COND_ORDER = {"novo": 0, "vitrine": 1, "recondicionado": 2, "usado": 3}


def _model_sort(m: str) -> tuple:
    import re
    g = re.search(r"\d+", m)
    gen = int(g.group()) if g else (17 if "Air" in m else 18)
    var = 0 if m.endswith(("Pro Max",)) else 1 if m.endswith("Pro") else 2
    return (-gen, var, m)


def daily_min_series(con: sqlite3.Connection) -> dict[str, list[tuple[str, float]]]:
    rows = con.execute(
        "SELECT model, condition, date, MIN(price) p FROM offers GROUP BY model, condition, date ORDER BY date"
    ).fetchall()
    out: dict[str, list] = {}
    for r in rows:
        out.setdefault(f"{r['model']}|{r['condition']}", []).append((r["date"], r["p"]))
    return out


def store_series(con: sqlite3.Connection) -> dict[str, dict[str, list]]:
    rows = con.execute(
        "SELECT model, condition, store, date, MIN(price) p FROM offers GROUP BY model, condition, store, date ORDER BY date"
    ).fetchall()
    out: dict[str, dict[str, list]] = {}
    for r in rows:
        out.setdefault(f"{r['model']}|{r['condition']}", {}).setdefault(r["store"], []).append((r["date"], r["p"]))
    return out


def summarize(con: sqlite3.Connection, today: str, cfg: dict) -> dict:
    series = daily_min_series(con)
    t = Date.fromisoformat(today)
    d7, d30, d90 = (str(t - timedelta(days=n)) for n in (7, 30, 90))
    a = cfg["alertas"]
    targets = a.get("preco_alvo", {}) or {}

    offers_today = [dict(r) for r in con.execute(
        "SELECT * FROM offers WHERE date=? ORDER BY price", (today,)).fetchall()]
    best: dict[str, dict] = {}
    for o in offers_today:
        best.setdefault(f"{o['model']}|{o['condition']}", o)

    apple_ref = {o["model"]: o["price"] for o in offers_today if o["store"] == "Apple Store"}
    # Apple não muda preço com frequência: usa último preço conhecido se hoje falhou
    for r in con.execute("SELECT model, price FROM offers WHERE store='Apple Store' ORDER BY date"):
        apple_ref.setdefault(r["model"], r["price"])

    items, alerts = [], []
    for key, o in best.items():
        model, cond = key.split("|")
        s = series.get(key, [])
        past = [p for d, p in s if d < today]
        last30 = [p for d, p in s if d30 <= d < today]
        days = len(s)
        it = {
            "key": key, "model": model, "condition": cond, "price": o["price"], "store": o["store"],
            "seller": o["seller"], "url": o["url"], "title": o["title"], "tags": o["tags"],
            "list_price": o["list_price"], "installments": o["installments"],
            "installment_total": o["installment_total"], "promo": o["promo"],
            "yesterday": past[-1] if past else None,
            "min7": min([p for d, p in s if d >= d7] or [o["price"]]),
            "min30": min([p for d, p in s if d >= d30] or [o["price"]]),
            "min90": min([p for d, p in s if d >= d90] or [o["price"]]),
            "min_all": min([p for _, p in s] or [o["price"]]),
            "median30": round(median(last30), 2) if last30 else None,
            "days": days,
            "apple_price": apple_ref.get(model),
            "n_offers": sum(1 for x in offers_today if x["model"] == model and x["condition"] == cond),
        }
        it["delta_yesterday"] = round(o["price"] - it["yesterday"], 2) if it["yesterday"] else None
        it["pct_vs_median30"] = (round((o["price"] / it["median30"] - 1) * 100, 1) if it["median30"] else None)
        it["pct_vs_apple"] = (round((o["price"] / it["apple_price"] - 1) * 100, 1)
                              if it["apple_price"] and o["store"] != "Apple Store" else None)
        sig = []
        if past and o["price"] < min(past) * 0.99 and days >= a["dias_minimos_para_recorde"]:
            sig.append("Menor preço já registrado")
        if it["pct_vs_median30"] is not None and it["pct_vs_median30"] <= -a["pct_abaixo_mediana_30d"]:
            sig.append(f"{abs(it['pct_vs_median30'])}% abaixo da mediana de 30 dias")
        tgt = targets.get(model)
        if tgt and cond == "novo" and o["price"] <= tgt:
            sig.append(f"Atingiu preço-alvo (R$ {tgt:,.0f})")
        if (o["list_price"] and o["list_price"] >= o["price"] * 1.25 and it["median30"]
                and o["price"] >= it["median30"] * 0.98 and days >= 7):
            sig.append("Desconto possivelmente inflado: preço 'de' alto, mas preço igual à média")
        it["signals"] = sig
        items.append(it)
        if sig and not sig[0].startswith("Desconto possivelmente"):
            alerts.append(it)

    items.sort(key=lambda x: (_model_sort(x["model"]), COND_ORDER.get(x["condition"], 9)))
    alerts.sort(key=lambda x: (x["pct_vs_median30"] or 0))
    runs = [dict(r) for r in con.execute("SELECT * FROM runs WHERE date=? ORDER BY store", (today,))]
    first = con.execute("SELECT MIN(date) FROM offers").fetchone()[0]
    return {"date": today, "items": items, "alerts": alerts, "offers": offers_today, "runs": runs,
            "history_start": first, "n_days": con.execute("SELECT COUNT(DISTINCT date) FROM offers").fetchone()[0]}
