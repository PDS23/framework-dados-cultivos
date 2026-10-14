# -*- coding: utf-8 -*-
"""
Estágio 1b/6 do pipeline IBGE: ingere o LSPA (SIDRA, Tabela 6588 -
Levantamento Sistemático da Produção Agrícola) direto da API para o PostGIS
(tabular.ibge_lspa). Complementa o PAM com estimativas mensais por UF, que
saem meses antes do fechamento anual do PAM (mas são preliminares e revisadas
a cada levantamento).

O LSPA não tem recorte municipal e só cobre algumas culturas; se a cultura
não existir na tabela, o estágio avisa e segue sem erro.

Uso:
    PGPASSWORD=... python src/ibge/01b_ingerir_lspa.py <cultura> [--desde AAAAMM]
"""
import argparse
import datetime
import gzip
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
import db  # noqa: E402
import sidra_api  # noqa: E402
from config import DATA, cultura as get_cultura  # noqa: E402

TABELA = 6588
CLASSIFICACAO_PRODUTO = 48

VARIAVEIS = {
    109: "area_plantada",
    216: "area_colhida",
    35: "producao",
    36: "rendimento_medio",
}


def meses(inicio, fim):
    """Lista AAAAMM de `inicio` a `fim` (inclusive)."""
    ano, mes = divmod(inicio, 100)
    saida = []
    while ano * 100 + mes <= fim:
        saida.append(ano * 100 + mes)
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1
    return saida


def ingere(cultura_slug, desde=None):
    cfg = get_cultura(cultura_slug)
    try:
        categoria = sidra_api.categoria_id(TABELA, CLASSIFICACAO_PRODUTO, cfg["nome_sidra"])
    except LookupError as e:
        print(f"[{cultura_slug}] Não consta no LSPA (tabela {TABELA}); estágio ignorado. ({e})")
        return
    inicio, fim = sidra_api.periodo_inicial_final(TABELA)
    periodos = meses(max(inicio, desde or inicio), fim)

    eng = db.engine()
    with eng.begin() as conn:
        id_fonte = db.id_fonte(conn, "IBGE")
        id_cultura = db.garante_cultura(conn, cultura_slug, cfg["nome_sidra"], id_fonte)

    print(f"[{cultura_slug}] SIDRA {TABELA}, produto categoria {categoria}, {periodos[0]}-{periodos[-1]} ({len(periodos)} meses)")
    registros = sidra_api.valores(TABELA, "n3", list(VARIAVEIS), periodos, CLASSIFICACAO_PRODUTO, categoria)

    pasta = DATA / "brutos" / "ibge_sidra"
    pasta.mkdir(parents=True, exist_ok=True)
    pacote = {"coletado_em": datetime.datetime.now().isoformat(timespec="seconds"), "tabela": TABELA, "registros": registros}
    with gzip.open(pasta / f"lspa_{cultura_slug}.json.gz", "wt", encoding="utf-8") as f:
        json.dump(pacote, f, ensure_ascii=False)

    df = pd.DataFrame(registros)
    df["valor"] = df["V"].map(sidra_api.parse_valor)
    df = df[df["valor"].notna()].copy()
    df["id_estado"] = df["D1C"].astype(str)
    df["ano"] = df["D3C"].astype(str).str[:4].astype(int)
    df["mes"] = df["D3C"].astype(str).str[4:].astype(int)
    df["variavel"] = df["D2C"].astype(int).map(VARIAVEIS)
    df["unidade"] = df["MN"]
    df["id_cultura"] = id_cultura
    df["id_fonte"] = id_fonte
    df["importado_em"] = datetime.date.today()
    df = df[["id_estado", "id_cultura", "ano", "mes", "variavel", "valor", "unidade", "id_fonte", "importado_em"]]

    with eng.begin() as conn:
        n = db.upsert(conn, df, "tabular", "ibge_lspa",
                      chave=["id_estado", "id_cultura", "ano", "mes", "variavel"],
                      atualizar=["valor", "unidade", "id_fonte", "importado_em"])
    print(f"[{cultura_slug}] Concluído: {n} valores em tabular.ibge_lspa")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingere o LSPA (SIDRA 6588) para o PostGIS.")
    parser.add_argument("cultura", help="slug em config/culturas.yaml")
    parser.add_argument("--desde", type=int, help="mês inicial AAAAMM (padrão: início da série, 200609)")
    args = parser.parse_args()
    ingere(args.cultura, args.desde)
