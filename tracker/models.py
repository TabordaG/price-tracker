"""Normalização de anúncios: modelo, armazenamento, cor, condição e tags."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict


@dataclass
class Offer:
    store: str                 # loja onde o anúncio foi encontrado
    seller: str                # vendedor (loja própria ou parceiro de marketplace)
    title: str
    url: str
    price: float               # menor preço à vista (PIX/boleto) quando disponível
    list_price: float | None = None      # preço "de" exibido
    installment_total: float | None = None
    installments: int | None = None
    sku: str = ""
    ean: str = ""
    promo: str = ""            # texto de promoção / cupom / campanha
    available: bool = True
    marketplace: bool = False  # vendido por terceiro
    # preenchidos por normalize()
    model: str = ""
    generation: int = 0
    storage: str = ""
    color: str = ""
    condition: str = ""        # novo | vitrine | recondicionado | usado
    tags: list[str] = field(default_factory=list)

    def key(self) -> str:
        return f"{self.model}|{self.condition}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tags"] = ",".join(self.tags)
        return d


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


ACCESSORY = re.compile(
    r"\b(capa|capinha|case|pelicula|vidro temperado|carregador|cabo|fonte|suporte|"
    r"skin|adesivo|bateria para|tela para|display|lente|protetor|carcaca|tampa|"
    r"magsafe|airpods|watch|ipad|macbook|pulseira|caneta|kit capa)\b"
)

# Ordem importa: variantes mais longas primeiro.
_MODEL_RE = re.compile(
    r"iphone\s*(?P<gen>1[5-9]|2\d)\s*(?P<var>pro\s*max|pro|plus|mini|e\b)?"
)
_SPECIAL_RE = re.compile(r"iphone\s*(?P<name>air|duo|fold)\b")
_STORAGE_RE = re.compile(r"(?<![\d.])(64|128|256|512|1|2)\s*(gb|tb)\b")

COLORS = {
    "preto": "Preto", "black": "Preto", "meia-noite": "Meia-noite", "meia noite": "Meia-noite",
    "midnight": "Meia-noite", "branco": "Branco", "white": "Branco", "estelar": "Estelar",
    "starlight": "Estelar", "azul-intenso": "Azul-intenso", "azul intenso": "Azul-intenso",
    "deep blue": "Azul-intenso", "azul-nevoa": "Azul-névoa", "azul nevoa": "Azul-névoa",
    "mist blue": "Azul-névoa", "azul-ceu": "Azul-céu", "azul ceu": "Azul-céu", "sky blue": "Azul-céu",
    "azul": "Azul", "blue": "Azul", "ultramarino": "Ultramarino", "ultramarine": "Ultramarino",
    "verde-acinzentado": "Verde-acinzentado", "teal": "Verde-acinzentado", "verde": "Verde",
    "green": "Verde", "salvia": "Sálvia", "sage": "Sálvia", "rosa": "Rosa", "pink": "Rosa",
    "lavanda": "Lavanda", "lavender": "Lavanda", "amarelo": "Amarelo", "yellow": "Amarelo",
    "laranja-cosmico": "Laranja-cósmico", "laranja cosmico": "Laranja-cósmico",
    "cosmic orange": "Laranja-cósmico", "laranja": "Laranja", "orange": "Laranja",
    "prateado": "Prateado", "prata": "Prateado", "silver": "Prateado",
    "dourado": "Dourado", "gold": "Dourado", "dourado-claro": "Dourado-claro", "light gold": "Dourado-claro",
    "titanio natural": "Titânio natural", "natural titanium": "Titânio natural",
    "titanio preto": "Titânio preto", "black titanium": "Titânio preto",
    "titanio branco": "Titânio branco", "white titanium": "Titânio branco",
    "titanio azul": "Titânio azul", "blue titanium": "Titânio azul",
    "titanio deserto": "Titânio deserto", "desert titanium": "Titânio deserto",
    "bordo": "Bordô", "burgundy": "Bordô", "vinho": "Bordô", "glacial": "Glacial",
    "grafite": "Grafite", "cinza": "Cinza", "night sky": "Night Sky", "star white": "Star White",
    "branco-estrela": "Branco-estrela",
}
_COLOR_KEYS = sorted(COLORS, key=len, reverse=True)

CONDITION_RULES = [
    # (condição, regex no texto normalizado)
    ("usado", r"\b(usado|seminovo|semi novo|semi-novo|pre-owned|pre owned|swap)\b"),
    ("recondicionado", r"\b(recondicionado|reacondicionado|refurbished|renewed|remanufaturado|"
                        r"recertificado|reformado)\b"),
    ("vitrine", r"\b(vitrine|mostruario|open ?box|openbox|caixa aberta|embalagem aberta|"
                r"produto de exposicao)\b"),
]

GRADE_RE = re.compile(r"\b(excelente|muito bom|bom estado|bom|grade [abc]|condicao [abc])\b")
IMPORT_RE = re.compile(
    r"\b(importado|importados|internacional|versao (global|americana|usa)|usa|eua|"
    r"modelo americano|ll/a|ch/a|zp/a|j/a)\b"
)
ESIM_RE = re.compile(r"\b(somente esim|apenas esim|so esim|esim only)\b")
BR_PART_RE = re.compile(r"\b[a-z]{2}\d{3}\s?(bz|br|be)/a\b")


def parse_model(text: str) -> tuple[str, int]:
    t = _plain(text)
    m = _MODEL_RE.search(t)
    if m:
        gen = int(m.group("gen"))
        var = (m.group("var") or "").replace(" ", "")
        suffix = {"promax": " Pro Max", "pro": " Pro", "plus": " Plus", "mini": " mini", "e": "e"}.get(var, "")
        return f"iPhone {gen}{suffix}", gen
    m = _SPECIAL_RE.search(t)
    if m:
        name = m.group("name").capitalize()
        # Air (2025) ~ geração 17; Duo/Fold tratados como geração 18+.
        return f"iPhone {name}", 17 if name == "Air" else 18
    return "", 0


def parse_storage(text: str) -> str:
    t = _plain(text)
    found = []
    for num, unit in _STORAGE_RE.findall(t):
        if unit == "gb" and num in ("64", "128", "256", "512"):
            found.append(f"{num}GB")
        elif unit == "tb" and num in ("1", "2"):
            found.append(f"{num}TB")
    if "512GB" in found:
        return "512GB"
    return found[0] if found else ""


def parse_color(text: str) -> str:
    t = _plain(text)
    for k in _COLOR_KEYS:
        if re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", t):
            return COLORS[k]
    return ""


def classify(offer: Offer, extra_text: str = "") -> None:
    """Preenche condição e tags. `extra_text` = descrição/seller para ajudar na detecção."""
    t = _plain(f"{offer.title} {offer.seller} {extra_text}")
    title = _plain(offer.title)
    cond = "novo"
    for name, rx in CONDITION_RULES:
        # condição deve aparecer no título ou no nome do vendedor (descrição gera falsos positivos)
        if re.search(rx, _plain(f"{offer.title} {offer.seller}")):
            cond = name
            break
    if offer.condition in ("vitrine", "usado", "recondicionado"):
        cond = offer.condition  # coletor já sabia (ex.: flag openbox da Kabum)
    offer.condition = cond

    tags = [cond]
    if cond == "novo" and "lacrado" in title:
        tags.append("lacrado")
    if cond in ("usado", "recondicionado"):
        g = GRADE_RE.search(title)
        if g:
            tags.append(f"estado: {g.group(1)}")
    tags.append("marketplace" if offer.marketplace else "loja oficial")
    if IMPORT_RE.search(t) and not BR_PART_RE.search(t):
        tags.append("importado")
    if ESIM_RE.search(t):
        tags.append("somente eSIM")
    if offer.list_price and offer.list_price > offer.price * 1.01:
        pct = round((1 - offer.price / offer.list_price) * 100)
        tags.append(f"-{pct}% vs preço 'de'")
    if offer.promo:
        tags.append("promoção")
    offer.tags = list(dict.fromkeys(tags))


def normalize(offer: Offer, cfg: dict, extra_text: str = "") -> Offer | None:
    """Retorna a oferta normalizada ou None se não passar no filtro."""
    f = cfg["filtro"]
    title_plain = _plain(offer.title)
    # Acessório: palavra de acessório aparece antes de "iphone" ("Capa para iPhone 17...")
    acc = ACCESSORY.search(title_plain)
    pos = title_plain.find("iphone")
    if acc and (pos < 0 or acc.start() < pos):
        return None
    model, gen = parse_model(offer.title)
    if not model or gen < f["geracao_minima"]:
        return None
    storage = parse_storage(offer.title)
    if storage != f["armazenamento"]:
        return None
    if not offer.price or offer.price < f["preco_minimo"]:
        return None
    offer.model, offer.generation, offer.storage = model, gen, storage
    offer.color = offer.color or parse_color(offer.title)
    classify(offer, extra_text)
    if offer.condition not in f["condicoes"]:
        return None
    return offer
