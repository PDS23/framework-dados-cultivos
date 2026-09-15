# -*- coding: utf-8 -*-
"""
Utilitário compartilhado por todos os scripts do pipeline: resolve paths
relativos à raiz do repositório (em vez de paths absolutos hardcoded) e
carrega o cadastro de culturas em config/culturas.yaml.

Qualquer script do pipeline importa assim:

    from comum.config import RAIZ, DATA, carregar_culturas

    cultura = carregar_culturas()["laranja"]
    bruto_dir = DATA / "brutos" / "ibge" / "laranja"
"""
from pathlib import Path
import yaml

# raiz do repositório = 2 níveis acima deste arquivo (src/comum/config.py -> raiz)
RAIZ = Path(__file__).resolve().parents[2]

DATA = RAIZ / "data"
CONFIG_PATH = RAIZ / "config" / "culturas.yaml"


def carregar_culturas():
    """Retorna {slug: {nome_sidra, mapbiomas_classe_codigo, ...}} a partir de config/culturas.yaml."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["culturas"]


def cultura(slug):
    """Atalho para pegar a config de 1 cultura só, com erro claro se não existir."""
    culturas = carregar_culturas()
    if slug not in culturas:
        disponiveis = ", ".join(sorted(culturas))
        raise KeyError(f'Cultura "{slug}" não está em config/culturas.yaml. Disponíveis: {disponiveis}')
    return culturas[slug]


# --- paths padronizados de cada estágio do pipeline, por fonte ---

def paths_ibge(cultura_slug):
    base = DATA / "ibge"
    return {
        "brutos": base / "brutos" / cultura_slug,
        "consolidado": base / "consolidado" / f"{cultura_slug}.xlsx",
        "processado": base / "processado" / cultura_slug,
        "geojson": base / "geojson" / cultura_slug,
        "mapas": base / "mapas" / cultura_slug,
        "relatorios": base / "relatorios" / cultura_slug,
        "malha_bruta": DATA / "geo" / "malha_municipios_brasil.shp",
        "malha_simplificada": DATA / "geo" / "municipios_brasil_simplificado.geojson",
    }


def paths_mapbiomas(cultura_slug):
    base = DATA / "mapbiomas"
    return {
        "bruto_xlsx": base / "brutos" / "MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx",
        "processado": base / "processado" / f"{cultura_slug}.csv",
        "geojson": base / "geojson" / f"{cultura_slug}.geojson",
        "mapas": base / "mapas" / cultura_slug,
        "relatorios": base / "relatorios" / cultura_slug,
        "malha_simplificada": DATA / "geo" / "municipios_brasil_simplificado.geojson",
    }
