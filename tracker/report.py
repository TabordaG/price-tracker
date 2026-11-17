"""E-mail diário (HTML) e dados do dashboard."""
from __future__ import annotations

import html
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def brl(v) -> str:
    if v is None:
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v) -> str:
    if v is None:
        return "—"
    color = "#0a7d32" if v < 0 else "#b3261e" if v > 0 else "#555"
    return f'<span style="color:{color}">{v:+.1f}%</span>'


def write_dashboard_data(summary: dict, series: dict, store_series: dict, docs: Path) -> None:
    d = docs / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "latest.json").write_text(json.dumps(summary, ensure_ascii=False, default=str))
    (d / "history.json").write_text(json.dumps({"series": series, "stores": store_series}, ensure_ascii=False))


def _tag_html(tags: str) -> str:
    colors = {"novo": "#0a7d32", "vitrine": "#b26a00", "recondicionado": "#5b3cc4", "usado": "#8a3b12",
              "marketplace": "#555", "loja oficial": "#1b5fad", "importado": "#b3261e"}
    out = []
    for t in (tags or "").split(","):
        if t:
            c = colors.get(t, "#666")
            out.append(f'<span style="display:inline-block;border:1px solid {c};color:{c};border-radius:9px;'
                       f'padding:0 6px;margin:1px;font-size:11px">{html.escape(t)}</span>')
    return "".join(out)


def build_email(summary: dict, dash_url: str) -> tuple[str, str]:
    items, alerts = summary["items"], summary["alerts"]
    novos = [i for i in items if i["condition"] == "novo"]
    best_new = min(novos, key=lambda x: x["price"]) if novos else None
    subj = f"iPhone 512GB {summary['date']}: "
    subj += f"{len(alerts)} alerta(s)" if alerts else "sem alertas"
    if best_new:
        subj += f" · menor novo {best_new['model']} {brl(best_new['price'])}"

    def row(i):
        sig = "<br>".join(html.escape(s) for s in i["signals"])
        return (
            f"<tr><td><b>{html.escape(i['model'])}</b><br>{_tag_html(i['tags'])}</td>"
            f"<td style='white-space:nowrap'><b>{brl(i['price'])}</b><br><small>{i['installments'] or ''}"
            f"{'x · ' + brl(i['installment_total']) if i['installment_total'] else ''}</small></td>"
            f"<td>{pct(i['pct_vs_median30'])}<br><small>mín 30d {brl(i['min30'])}</small></td>"
            f"<td>{pct(i['delta_yesterday'] / i['yesterday'] * 100 if i['yesterday'] else None)}</td>"
            f"<td>{pct(i['pct_vs_apple'])}</td>"
            f"<td><a href='{html.escape(i['url'])}'>{html.escape(i['store'])}</a><br><small>{html.escape(i['seller'] or '')}</small></td>"
            f"<td><small>{sig}</small></td></tr>"
        )

    head = ("<tr style='background:#f2f2f2;text-align:left'><th>Modelo</th><th>Preço à vista</th>"
            "<th>vs mediana 30d</th><th>vs ontem</th><th>vs Apple</th><th>Loja</th><th>Sinais</th></tr>")
    tbl = "<table cellpadding='6' style='border-collapse:collapse;font-size:13px;width:100%' border='1' bordercolor='#ddd'>"
    parts = [f"<div style='font-family:Arial,sans-serif;max-width:900px'>",
             f"<h2>Monitor iPhone 512GB · {summary['date']}</h2>",
             f"<p><a href='{dash_url}'>Abrir dashboard completo</a> · histórico desde {summary['history_start']} "
             f"({summary['n_days']} dia(s))</p>"]
    if alerts:
        parts += ["<h3>🔔 Alertas</h3>", tbl, head, *map(row, alerts), "</table>"]
    for cond, label in [("novo", "Novos"), ("vitrine", "Vitrine / open box"),
                        ("recondicionado", "Recondicionados"), ("usado", "Usados / seminovos")]:
        rows = [i for i in items if i["condition"] == cond]
        if rows:
            parts += [f"<h3>{label} · menor preço por modelo</h3>", tbl, head, *map(row, rows), "</table>"]
    st = "".join(
        f"<li>{html.escape(r['store'])}: "
        + (f"{r['n_offers']} ofertas válidas" if r["status"] == "ok" else f"<b>{r['status']}</b> <small>({html.escape(r['error'] or '')})</small>")
        + "</li>" for r in summary["runs"])
    parts += ["<h3>Status das lojas</h3><ul>", st, "</ul>",
              "<p style='color:#777;font-size:11px'>Preço à vista = menor preço PIX/boleto anunciado. "
              "Frete e cupons de checkout não estão incluídos. Confira o vendedor e a garantia antes de comprar.</p></div>"]
    return subj, "".join(parts)


def send_email(subject: str, body_html: str) -> bool:
    user, pw, to = os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"), os.getenv("EMAIL_TO")
    if not (user and pw and to):
        print("SMTP_USER/SMTP_PASS/EMAIL_TO não definidos: e-mail não enviado.")
        return False
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "465"))
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    with smtplib.SMTP_SSL(host, port, timeout=60) as s:
        s.login(user, pw)
        s.sendmail(user, [x.strip() for x in to.split(",")], msg.as_string())
    print(f"E-mail enviado para {to}")
    return True
