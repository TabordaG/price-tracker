"""Execução diária: coleta → normaliza → salva → analisa → dashboard → e-mail."""
from __future__ import annotations

import argparse
import os
import tomllib
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import analyze, db, report
from .collectors import apple, generic, kabum, vtex
from .collectors.base import Blocked
from .models import normalize

ROOT = Path(__file__).resolve().parent.parent

COLLECTORS = {
    "kabum": ("Kabum", lambda t: kabum.collect(t)),
    "americanas": ("Americanas", lambda t: vtex.collect("americanas", t)),
    "carrefour": ("Carrefour", lambda t: vtex.collect("carrefour", t)),
    "apple": ("Apple Store", lambda t: apple.collect(t)),
    "magalu": ("Magalu", lambda t: generic.collect("magalu", t)),
    "casasbahia": ("Casas Bahia", lambda t: generic.collect("casasbahia", t)),
    "mercadolivre": ("Mercado Livre", lambda t: generic.collect("mercadolivre", t)),
    "amazon": ("Amazon", lambda t: generic.collect("amazon", t)),
}


def dashboard_url(cfg: dict) -> str:
    if cfg["dashboard"].get("url"):
        return cfg["dashboard"]["url"]
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner.lower()}.github.io/{name}/"
    return "(dashboard local: docs/index.html)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="rodar só estas lojas (chaves do config)")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--db", default=str(ROOT / "data" / "prices.sqlite"))
    args = ap.parse_args()

    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    today, ts = now.date().isoformat(), now.isoformat(timespec="seconds")
    con = db.connect(Path(args.db))
    terms = cfg["busca"]["termos"]

    for key, (store, fn) in COLLECTORS.items():
        if not cfg["lojas"].get(key) or (args.only and key not in args.only):
            continue
        try:
            raw = fn(terms)
            seen, offers = set(), []
            for o in raw:
                n = normalize(o, cfg, getattr(o, "_extra", ""))
                if not n:
                    continue
                k = (n.sku or n.url, n.seller, n.price)
                if k not in seen:
                    seen.add(k)
                    offers.append(n)
            db.save_store(con, today, ts, store, offers, "ok", len(raw))
            print(f"[ok] {store}: {len(raw)} anúncios, {len(offers)} válidos")
        except Blocked as e:
            db.save_store(con, today, ts, store, [], "bloqueada", 0, str(e))
            print(f"[bloqueada] {store}: {e}")
        except Exception as e:  # noqa: BLE001 - uma loja não pode derrubar as outras
            db.save_store(con, today, ts, store, [], "erro", 0, f"{type(e).__name__}: {e}")
            print(f"[erro] {store}: {e}")
            traceback.print_exc()

    summary = analyze.summarize(con, today, cfg)
    url = dashboard_url(cfg)
    summary["dashboard_url"] = url
    report.write_dashboard_data(summary, analyze.daily_min_series(con), analyze.store_series(con), ROOT / "docs")
    subject, body = report.build_email(summary, url)
    (ROOT / "data" / "last_email.html").write_text(body)
    print(subject)
    if not args.no_email:
        report.send_email(subject, body)


if __name__ == "__main__":
    main()
