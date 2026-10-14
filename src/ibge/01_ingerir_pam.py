# -*- coding: utf-8 -*-
"""
Estágio 1/6 do pipeline IBGE: ingere o PAM (SIDRA, Produção Agrícola
Municipal) direto da API do IBGE para o PostGIS (tabular.ibge_pam). Nenhum
arquivo precisa ser baixado à mão.

- Lavouras permanentes estão na Tabela 1613 e as temporárias na 1612. A tabela
  e o código do produto são resolvidos pelo `nome_sidra` de config/culturas.yaml,
  consultando os metadados (opcionalmente fixe com `sidra_tabela_pam`).
- Uma requisição por ano (8 variáveis x todos os municípios), gravada também
  em data/brutos/ibge_sidra/pam_<cultura>/<ano>.json.gz com a data de coleta.
- Idempotente: reprocessar um ano atualiza as linhas (o IBGE revisa o ano
  anterior quando publica o novo) em vez de duplicar.
- Unidade: gravada em `unidade`, como a API devolve. Exceção documentada pelo
  IBGE (nota 2 da tabela): para frutíferas, a quantidade produzida e o
  rendimento até 2000 eram "mil frutos" e "frutos por hectare", embora a API
  rotule como toneladas / kg por hectare. Culturas afetadas declaram
  `quebra_unidade_quantidade_ate: 2000` em config/culturas.yaml.

Uso:
    PGPASSWORD=... python src/ibge/01_ingerir_pam.py <cultura> [--anos 2024,2025]
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

_COMUNS = {
    216: "area_colhida",
    1000216: "area_colhida_pct",
    214: "quantidade_produzida",
    112: "rendimento_medio",
    215: "valor_producao",
    1000215: "valor_producao_pct",
}
TABELAS = {
    1613: {  # lavouras permanentes
        "classificacao": 82,
        "variaveis": {2313: "area_destinada_colheita", 1002313: "area_destinada_colheita_pct", **_COMUNS},
    },
    1612: {  # lavouras temporárias (o IBGE chama a variável de área de "área plantada")
        "classificacao": 81,
        "variaveis": {109: "area_plantada", 1000109: "area_plantada_pct", **_COMUNS},
    },
}
UNIDADE_ATE_QUEBRA = {214: "Mil frutos", 112: "Frutos por hectare"}


def resolve_tabela(cfg):
    """Devolve (tabela, categoria_do_produto) para a cultura, procurando o nome_sidra nas tabelas do PAM."""
    candidatas = [cfg["sidra_tabela_pam"]] if "sidra_tabela_pam" in cfg else list(TABELAS)
    erros = []
    for tabela in candidatas:
        try:
            return tabela, sidra_api.categoria_id(tabela, TABELAS[tabela]["classificacao"], cfg["nome_sidra"])
        except LookupError as e:
            erros.append(str(e))
    raise LookupError(f'"{cfg["nome_sidra"]}" não encontrado no PAM: ' + " | ".join(erros))


def salva_bruto(cultura_slug, ano, tabela, registros):
    pasta = DATA / "brutos" / "ibge_sidra" / f"pam_{cultura_slug}"
    pasta.mkdir(parents=True, exist_ok=True)
    pacote = {"coletado_em": datetime.datetime.now().isoformat(timespec="seconds"), "tabela": tabela, "registros": registros}
    with gzip.open(pasta / f"{ano}.json.gz", "wt", encoding="utf-8") as f:
        json.dump(pacote, f, ensure_ascii=False)


def transforma(registros, ano, variaveis, id_cultura, id_fonte, quebra_ate, municipios_validos):
    df = pd.DataFrame(registros)
    if df.empty:
        return df, 0
    df["valor"] = df["V"].map(sidra_api.parse_valor)
    df = df[df["valor"].notna()].copy()
    df["variavel"] = df["D2C"].astype(int).map(variaveis)
    df["unidade"] = df["MN"]
    if quebra_ate is not None and ano <= quebra_ate:
        for var, unidade in UNIDADE_ATE_QUEBRA.items():
            df.loc[df["D2C"].astype(int) == var, "unidade"] = unidade
    df["id_municipio"] = df["D1C"].astype(str)
    fora_da_dim = int((~df["id_municipio"].isin(municipios_validos)).sum())
    df = df[df["id_municipio"].isin(municipios_validos)]
    df["id_cultura"] = id_cultura
    df["ano"] = ano
    df["id_fonte"] = id_fonte
    df["importado_em"] = datetime.date.today()
    return df[["id_municipio", "id_cultura", "ano", "variavel", "valor", "unidade", "id_fonte", "importado_em"]], fora_da_dim


def ingere(cultura_slug, anos=None):
    cfg = get_cultura(cultura_slug)
    tabela, categoria = resolve_tabela(cfg)
    info = TABELAS[tabela]
    _, ultimo_ano = sidra_api.periodo_inicial_final(tabela)
    anos = anos or list(range(cfg.get("ano_inicio_ibge", 1974), ultimo_ano + 1))
    quebra_ate = cfg.get("quebra_unidade_quantidade_ate")

    eng = db.engine()
    with eng.begin() as conn:
        id_fonte = db.id_fonte(conn, "IBGE")
        id_cultura = db.garante_cultura(conn, cultura_slug, cfg["nome_sidra"], id_fonte)
        municipios_validos = {r[0] for r in conn.exec_driver_sql("SELECT id_municipio FROM dim.municipios")}

    print(f"[{cultura_slug}] SIDRA {tabela}, produto '{cfg['nome_sidra']}' (categoria {categoria}), anos {anos[0]}-{anos[-1]}")
    total = 0
    for ano in anos:
        registros = sidra_api.valores(tabela, "n6", list(info["variaveis"]), [ano], info["classificacao"], categoria)
        salva_bruto(cultura_slug, ano, tabela, registros)
        df, fora = transforma(registros, ano, info["variaveis"], id_cultura, id_fonte, quebra_ate, municipios_validos)
        with eng.begin() as conn:
            n = db.upsert(conn, df, "tabular", "ibge_pam",
                          chave=["id_municipio", "id_cultura", "ano", "variavel"],
                          atualizar=["valor", "unidade", "id_fonte", "importado_em"])
        total += n
        aviso = f" ({fora} valores de municípios fora de dim.municipios)" if fora else ""
        print(f"[{cultura_slug}] {ano}: {n} valores gravados{aviso}")
    print(f"[{cultura_slug}] Concluído: {total} valores em tabular.ibge_pam")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingere o PAM (SIDRA 1612/1613) para o PostGIS.")
    parser.add_argument("cultura", help="slug em config/culturas.yaml")
    parser.add_argument("--anos", help="lista separada por vírgula (padrão: série inteira até o último ano publicado)")
    args = parser.parse_args()
    ingere(args.cultura, [int(a) for a in args.anos.split(",")] if args.anos else None)
