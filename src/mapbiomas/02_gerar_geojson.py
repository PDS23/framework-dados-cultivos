# -*- coding: utf-8 -*-
"""
Estágio 2/5 do pipeline MapBiomas: junta a série histórica processada
(data/mapbiomas/processado/<cultura>.csv) com a malha municipal simplificada
(gerada pelo pipeline do IBGE, estágio 3 — rode-o pelo menos 1x antes, para
qualquer cultura, já que a malha é compartilhada), mantendo TODOS os
municípios do Brasil (Teve_Prod=0 e área 0 para quem nunca teve a classe
detectada).

Saída: data/mapbiomas/geojson/<cultura>.geojson

Uso: python src/mapbiomas/02_gerar_geojson.py <cultura>
"""
import sys
import os
import geopandas as gpd
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
from config import paths_mapbiomas  # noqa: E402

ANOS = [str(a) for a in range(1985, 2025)]


def gera_geojson(cultura_slug):
    paths = paths_mapbiomas(cultura_slug)
    malha_path = paths["malha_simplificada"]
    if not malha_path.exists():
        raise FileNotFoundError(
            f"{malha_path} não encontrado — rode src/ibge/03_gerar_geojson.py para qualquer cultura antes "
            f"(ele gera a malha simplificada compartilhada)."
        )
    csv_path = paths["processado"]
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} não encontrado — rode 01_extrair_classe.py antes.")

    print(f"[{cultura_slug}] Lendo malha municipal...")
    malha = gpd.read_file(malha_path).rename(columns={"CD_MUN": "Codigo"})
    malha["Codigo"] = malha["Codigo"].astype(str)

    print(f"[{cultura_slug}] Lendo série processada do MapBiomas...")
    df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype={"Codigo": str})

    gdf = malha.merge(df.drop(columns=["Nome"]), on="Codigo", how="left")
    gdf["Teve_Prod"] = gdf["Teve_Prod"].fillna(0).astype(int)
    for ano in ANOS:
        gdf[ano] = gdf[ano].fillna(0.0)
    gdf["Estado"] = gdf["Estado"].fillna(gdf["SIGLA_UF"])
    gdf = gdf.rename(columns={"NM_MUN": "Nome"})
    gdf = gdf[["Codigo", "Nome", "SIGLA_UF", "AREA_KM2", "Teve_Prod"] + ANOS + ["geometry"]]

    out_path = paths["geojson"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        os.remove(out_path)
    gdf.to_file(out_path, driver="GeoJSON")

    print(f"[{cultura_slug}] Geojson salvo em: {out_path}")
    print(f"[{cultura_slug}] Total de municípios: {len(gdf)}")
    print(f"[{cultura_slug}] Municípios com Teve_Prod=1: {int(gdf['Teve_Prod'].sum())}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python 02_gerar_geojson.py <cultura>")
        sys.exit(1)
    gera_geojson(sys.argv[1])
