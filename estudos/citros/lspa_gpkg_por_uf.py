# -*- coding: utf-8 -*-
"""
Gera um GeoPackage da LSPA por UF a partir do PostGIS: 1 camada por variável
(area_plantada, area_colhida, producao, rendimento_medio), geometria de
dim.estados e 1 coluna por mês (AAAA-MM).

Uso:
    PGPASSWORD=... python estudos/citros/lspa_gpkg_por_uf.py [--cultura laranja] [--saida caminho.gpkg]
"""
import argparse
import os
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "comum"))
import db  # noqa: E402
from config import DATA  # noqa: E402

SQL = text("""
    SELECT e.id_estado, e.nome, e.sigla, l.variavel, l.ano, l.mes, l.valor
    FROM tabular.ibge_lspa l
    JOIN dim.estados e USING (id_estado)
    JOIN dim.cultura c USING (id_cultura)
    WHERE c.slug = :slug
""")


def gera(cultura, saida):
    with db.engine().connect() as conn:
        dados = pd.read_sql(SQL, conn, params={"slug": cultura})
        geoms = gpd.read_postgis("SELECT id_estado, geom FROM dim.estados", conn, geom_col="geom")
    if dados.empty:
        raise RuntimeError(f"Nada em tabular.ibge_lspa para '{cultura}' — rode src/ibge/01b_ingerir_lspa.py antes.")

    dados["periodo"] = dados["ano"].astype(str) + "-" + dados["mes"].astype(str).str.zfill(2)
    saida.parent.mkdir(parents=True, exist_ok=True)
    if saida.exists():
        saida.unlink()  # evita camadas antigas sobrando de uma execução anterior
    for variavel, sub in dados.groupby("variavel"):
        largo = sub.pivot_table(index=["id_estado", "nome", "sigla"], columns="periodo", values="valor", aggfunc="first").reset_index()
        gdf = geoms.merge(largo, on="id_estado")
        gdf.to_file(saida, driver="GPKG", layer=variavel, mode="a" if saida.exists() else "w")
        print(f"camada '{variavel}': {len(gdf)} UFs x {largo.shape[1] - 3} meses")
    print(f"GeoPackage salvo em: {saida}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cultura", default="laranja")
    parser.add_argument("--saida", type=Path, default=None)
    args = parser.parse_args()
    gera(args.cultura, args.saida or DATA / "analises" / f"lspa_{args.cultura}_por_uf.gpkg")
