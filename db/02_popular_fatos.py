# -*- coding: utf-8 -*-
"""
Popula tabular.mapbiomas_cobertura e tabular.receita_federal_cnpj a partir de
arquivos locais. Idempotente (upsert). IBGE PAM e LSPA não passam por aqui:
vêm direto da API (src/ibge/01_ingerir_pam.py e 01b_ingerir_lspa.py).

- mapbiomas: lê data/mapbiomas/processado/<cultura>.csv (saída do estágio 01 do
  pipeline MapBiomas) e grava no grupo da cultura (ex.: 'citros' para laranja).
- cnpj: lê o CSV detalhado exportado do BigQuery (Base dos Dados,
  br_rf_cnpj.estabelecimentos + empresas). Se o CSV tiver a coluna id_municipio
  (código IBGE, recomendado) ela é usada; senão o município é achado por nome + UF.

Uso:
    PGPASSWORD=... python db/02_popular_fatos.py mapbiomas [--cultura laranja]
    PGPASSWORD=... python db/02_popular_fatos.py cnpj --csv caminho.csv [--cultura laranja]
"""
import argparse
import datetime
import os
import sys
import unicodedata

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "comum"))
import db  # noqa: E402
from config import paths_mapbiomas  # noqa: E402

HOJE = datetime.date.today()

SITUACAO = {"1": "Nula", "2": "Ativa", "3": "Suspensa", "4": "Inapta", "8": "Baixada"}
PORTE = {"0": "Não informado", "1": "Micro Empresa", "3": "Empresa de Pequeno Porte", "5": "Demais"}
MATRIZ_FILIAL = {"1": "Matriz", "2": "Filial"}
# grafias diferentes entre a Receita Federal e o IBGE para o mesmo município
ALIAS_MUNICIPIO = {"sao luis do paraitinga": "sao luiz do paraitinga"}


def normaliza(txt):
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode("ascii").lower().strip()
    return ALIAS_MUNICIPIO.get(txt, txt)


def popula_mapbiomas(eng, cultura):
    with eng.begin() as conn:
        id_fonte = db.id_fonte(conn, "MapBiomas")
        id_cultura = conn.execute(text("SELECT COALESCE(id_cultura_grupo, id_cultura) FROM dim.cultura WHERE slug = :s"), {"s": cultura}).scalar_one()
        df = pd.read_csv(paths_mapbiomas(cultura)["processado"], dtype={"Codigo": str})
        anos = [c for c in df.columns if c.isdigit()]
        longo = df.melt(id_vars=["Codigo"], value_vars=anos, var_name="ano", value_name="area_ha").dropna(subset=["area_ha"])
        longo = pd.DataFrame({
            "id_municipio": longo["Codigo"].str.zfill(7), "id_cultura": id_cultura, "ano": longo["ano"].astype(int),
            "area_ha": longo["area_ha"].astype(float), "id_fonte": id_fonte, "importado_em": HOJE,
        })
        n = db.upsert(conn, longo, "tabular", "mapbiomas_cobertura", chave=["id_municipio", "id_cultura", "ano"], atualizar=["area_ha", "id_fonte", "importado_em"])
        db.registra_dataset(conn, "MapBiomas Colecao 11 - classe Citrus (municipio)", "MapBiomas", "tabular.mapbiomas_cobertura",
                            licenca="MapBiomas (CC BY-SA)", observacoes="Estatisticas municipais da Colecao 11, area em hectares da classe da cultura")
    print(f"tabular.mapbiomas_cobertura: {n} linhas gravadas.")


def popula_cnpj(eng, cultura, csv):
    with eng.begin() as conn:
        id_fonte = db.id_fonte(conn, "Receita Federal")
        id_cultura = conn.execute(text("SELECT id_cultura FROM dim.cultura WHERE slug = :s"), {"s": cultura}).scalar_one()
        df = pd.read_csv(csv, dtype={"cnpj": str, "id_municipio": str})

        if "id_municipio" not in df.columns:
            ufs = dict(conn.execute(text("SELECT sigla, id_estado FROM dim.estados")).fetchall())
            muns = {(normaliza(n), e): i for n, e, i in conn.execute(text("SELECT nome, id_estado, id_municipio FROM dim.municipios")).fetchall()}
            df["id_municipio"] = [muns.get((normaliza(m), ufs.get(u))) for m, u in zip(df["municipio"], df["sigla_uf"])]
        sem_municipio = int(df["id_municipio"].isna().sum())
        if sem_municipio:
            print(f"Aviso: {sem_municipio} CNPJ(s) sem município resolvido; ficam de fora.")
            df = df[df["id_municipio"].notna()]

        cnpj = df["cnpj"].str.zfill(14)
        final = pd.DataFrame({
            "cnpj": cnpj, "cnpj_basico": cnpj.str[:8],
            "razao_social": df["razao_social"], "nome_fantasia": df["nome_fantasia"],
            "id_municipio": df["id_municipio"], "id_cultura": id_cultura,
            "cnae_fiscal_principal": "0131800",
            "data_inicio_atividade": pd.to_datetime(df["data_inicio_atividade"]).dt.date,
            "situacao_cadastral": df["situacao"].astype(str).map(SITUACAO).fillna(df["situacao"]),
            "capital_social": df["capital_social"],
            "porte": df["porte"].astype(str).map(PORTE).fillna(df["porte"]),
            "identificador_matriz_filial": df["identificador_matriz_filial"].astype(str).map(MATRIZ_FILIAL).fillna(df["identificador_matriz_filial"]),
            "id_fonte": id_fonte, "importado_em": HOJE,
        })
        n = db.upsert(conn, final, "tabular", "receita_federal_cnpj", chave=["cnpj"],
                      atualizar=[c for c in final.columns if c != "cnpj"])
        nome = "Receita Federal - CNPJs CNAE 0131-8/00 (laranja)"
        db.registra_dataset(conn, nome, "Receita Federal", "tabular.receita_federal_cnpj", licenca="Dados publicos (Base dos Dados/BigQuery)",
                            observacoes="Estabelecimentos novos por CNPJ, grao fino")
        conn.execute(text("""
            UPDATE catalogo.datasets SET cobertura = (
                SELECT ST_Multi(ST_Union(m.geom)) FROM dim.municipios m
                WHERE m.id_municipio IN (SELECT DISTINCT id_municipio FROM tabular.receita_federal_cnpj))
            WHERE nome = :nome
        """), {"nome": nome})
    print(f"tabular.receita_federal_cnpj: {n} linhas gravadas.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fonte", choices=["mapbiomas", "cnpj"])
    parser.add_argument("--cultura", default="laranja")
    parser.add_argument("--csv", help="CSV do BigQuery (só para 'cnpj')")
    args = parser.parse_args()
    eng = db.engine()
    if args.fonte == "mapbiomas":
        popula_mapbiomas(eng, args.cultura)
    else:
        if not args.csv:
            parser.error("'cnpj' exige --csv")
        popula_cnpj(eng, args.cultura, args.csv)
