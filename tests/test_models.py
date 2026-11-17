import tomllib
from pathlib import Path

import pytest

from tracker.models import Offer, normalize, parse_model, parse_storage

CFG = tomllib.loads((Path(__file__).parent.parent / "config.toml").read_text())


def mk(title, price=8000.0, seller="Loja", marketplace=False, list_price=None):
    return Offer(store="X", seller=seller, title=title, url="u", price=price,
                 marketplace=marketplace, list_price=list_price)


@pytest.mark.parametrize("t,model", [
    ("Smartphone Apple iPhone 17 Pro Max 512GB 12GB RAM Azul-intenso", "iPhone 17 Pro Max"),
    ("Iphone 18 Pro Bordo 512gb Mjrw4be/a", "iPhone 18 Pro"),
    ("Apple iPhone 16e 512GB Branco", "iPhone 16e"),
    ("Smartphone Apple iPhone 17e 512GB 8GB RAM Preto", "iPhone 17e"),
    ("iPhone 15 Plus 512 GB Rosa", "iPhone 15 Plus"),
    ("Smartphone Apple iPhone Air 512GB 8GB RAM Azul-céu", "iPhone Air"),
    ("iPhone Duo Apple 512GB Night Sky Desbloqueado", "iPhone Duo"),
    ("Apple Iphone 17 Pro 512gb Azul-intenso", "iPhone 17 Pro"),
])
def test_model(t, model):
    assert parse_model(t)[0] == model


def test_storage_ignores_ram():
    assert parse_storage("iPhone 17 Pro 512GB 12GB RAM") == "512GB"
    assert parse_storage("iPhone 17 Pro 256GB 12GB RAM") == "256GB"
    assert parse_storage("iPhone 17 Pro Max 2TB 12GB RAM") == "2TB"


def test_filters():
    assert normalize(mk("iPhone 14 Pro 512GB"), CFG) is None            # geração antiga
    assert normalize(mk("iPhone 12 Pro 512GB Grafite"), CFG) is None
    assert normalize(mk("iPhone 17 256GB Preto"), CFG) is None           # armazenamento
    assert normalize(mk("Capa para iPhone 17 Pro 512GB", 99), CFG) is None
    assert normalize(mk("Apple MacBook Pro 512GB SSD"), CFG) is None
    assert normalize(mk("iPhone 17 512GB Preto"), CFG) is not None


@pytest.mark.parametrize("t,seller,cond", [
    ("Usado: iPhone 15 Pro Max 512GB Titânio Azul Muito Bom - Trocafone", "Trocafone", "usado"),
    ("iPhone 16 Pro 512GB Seminovo", "X", "usado"),
    ("iPhone 16 Pro 512GB Vitrine", "X", "vitrine"),
    ("iPhone 16 Pro 512GB Open Box", "X", "vitrine"),
    ("iPhone 16 Pro 512GB Recondicionado", "X", "recondicionado"),
    ("Apple iPhone 16 Pro 512GB (Renewed)", "X", "recondicionado"),
    ("iPhone 17 Pro 512GB Lacrado", "X", "novo"),
])
def test_condition(t, seller, cond):
    o = normalize(mk(t, seller=seller), CFG)
    assert o.condition == cond and cond in o.tags


def test_tags():
    o = normalize(mk("iPhone 18 Pro Max 512GB Apple Black Desbloqueado", seller="infotec importados USA",
                     marketplace=True, list_price=10000, price=9000), CFG)
    assert "importado" in o.tags and "marketplace" in o.tags and "-10% vs preço 'de'" in o.tags
    o = normalize(mk("Usado: iPhone 15 512GB Preto Excelente - Trocafone"), CFG)
    assert "estado: excelente" in o.tags
    o = normalize(mk("IPHONE 18 PRO MAX BORDO 512GB MJXV4BE/A"), CFG)
    assert "importado" not in o.tags and o.color == "Bordô"
