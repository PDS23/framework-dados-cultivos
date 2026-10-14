# -*- coding: utf-8 -*-
"""
Estágio 2/6 do pipeline IBGE: exporta do PostGIS (tabular.ibge_pam) um CSV por
variável, em nível de município, no layout que os estágios de mapa e relatório
(03 a 06) consomem:
  data/ibge/processado/<cultura>/<variavel>.csv

Colunas: Codigo, Nome, Teve_Prod, <ano1>, <ano2>, ...
Ausência de dado vira 0; Teve_Prod = 1 se algum ano tiver valor > 0.

Uso: PGPASSWORD=... python src/ibge/02_exportar_do_banco.py <cultura>
"""
import os
import sys

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
import db  # noqa: E402
from config import paths_ibge  # noqa: E402

# variável no banco -> nome do arquivo que os estágios 03-06 esperam
ARQUIVO_POR_VARIAVEL = {
    "area_destinada_colheita": "area_destinada_colheita_ha",
    "area_destinada_colheita_pct": "area_destinada_colheita_pct",
    "area_plantada": "area_plantada_ha",  # lavouras temporárias (tabela 1612)
    "area_plantada_pct": "area_plantada_pct",
    "area_colhida": "area_colhida_ha",
    "area_colhida_pct": "area_colhida_pct",
    "quantidade_produzida": "quantidade_produzida_t",
    "rendimento_medio": "rendimento_medio_kg_ha",
    "valor_producao": "valor_producao",
    "valor_producao_pct": "valor_producao_pct",
}

SQL = text("""
    SELECT p.id_municipio AS "Codigo", m.nome AS "Nome", p.variavel, p.ano, p.valor
    FROM tabular.ibge_pam p
    JOIN dim.cultura c USING (id_cultura)
    JOIN dim.municipios m USING (id_municipio)
    WHERE c.slug = :slug
""")


def exporta(cultura_slug):
    paths = paths_ibge(cultura_slug)
    out_dir = paths["processado"]
    out_dir.mkdir(parents=True, exist_ok=True)

    with db.engine().connect() as conn:
        df = pd.read_sql(SQL, conn, params={"slug": cultura_slug})
    if df.empty:
        raise RuntimeError(f"Nada em tabular.ibge_pam para '{cultura_slug}' — rode 01_ingerir_pam.py antes.")

    anos = list(range(int(df["ano"].min()), int(df["ano"].max()) + 1))
    for variavel, arquivo in ARQUIVO_POR_VARIAVEL.items():
        sub = df[df["variavel"] == variavel]
        if sub.empty:
            continue
        largo = sub.pivot_table(index=["Codigo", "Nome"], columns="ano", values="valor", aggfunc="first")
        largo = largo.reindex(columns=anos).fillna(0.0).reset_index().sort_values("Codigo")
        valores = largo[anos]
        if (valores % 1 == 0).all().all():
            largo[anos] = valores.astype("int64")
        largo.insert(2, "Teve_Prod", (valores > 0).any(axis=1).astype(int))
        largo.columns = [str(c) for c in largo.columns]
        caminho = out_dir / f"{arquivo}.csv"
        largo.to_csv(caminho, index=False, encoding="utf-8-sig")
        print(f"[{cultura_slug}] {arquivo}.csv salvo em {caminho} ({len(largo)} municípios)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python 02_exportar_do_banco.py <cultura>")
        sys.exit(1)
    exporta(sys.argv[1])
