# -*- coding: utf-8 -*-
"""
Estágio 3/6 do pipeline IBGE.

Parte A (roda 1x só, compartilhada entre todas as culturas): lê a malha
municipal do IBGE (shapefile em data/geo/malha_municipios_brasil.shp —
baixe em https://www.ibge.gov.br/geociencias/organizacao-do-territorio/
malhas-territoriais/15774-malhas.html, nível Município, e extraia o .shp
aqui) e gera uma versão simplificada e reprojetada (WGS84), bem mais leve
para desenhar mapas: data/geo/municipios_brasil_simplificado.geojson.

Parte B (por cultura): junta cada CSV de data/ibge/processado/<cultura>/ com
a malha simplificada, gerando 1 geojson por variável em
data/ibge/geojson/<cultura>/<variavel>.geojson — mantém TODOS os municípios
do Brasil (left join), preenchendo com 0 quem não produz essa cultura, para
os mapas mostrarem o país inteiro em cinza-claro onde não há produção.

Uso: python src/ibge/03_gerar_geojson.py <cultura>
"""
import sys
import os
import glob
import geopandas as gpd
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
from config import paths_ibge  # noqa: E402

TOLERANCIA_SIMPLIFICACAO_GRAUS = 0.005  # ~500m; suficiente para mapas nacionais, bem mais leve que a malha original


def garante_malha_simplificada(paths):
    destino = paths["malha_simplificada"]
    if destino.exists():
        return destino
    origem = paths["malha_bruta"]
    if not origem.exists():
        raise FileNotFoundError(
            f"Malha municipal não encontrada em {origem}. Baixe o shapefile de municípios do IBGE "
            f"(nível Brasil) e extraia-o nesse caminho antes de rodar este estágio."
        )
    print("Gerando malha simplificada (roda só 1 vez, compartilhada por todas as culturas)...")
    gdf = gpd.read_file(origem)
    gdf = gdf.to_crs(epsg=4326)
    gdf["geometry"] = gdf["geometry"].simplify(TOLERANCIA_SIMPLIFICACAO_GRAUS, preserve_topology=True)

    col_codigo = next(c for c in gdf.columns if c.upper() in ("CD_MUN", "CD_GEOCODM", "GEOCODIGO"))
    col_nome = next(c for c in gdf.columns if c.upper() in ("NM_MUN", "NM_MUNICIP", "NOME"))
    col_uf = next((c for c in gdf.columns if c.upper() in ("SIGLA_UF", "UF")), None)

    gdf = gdf.rename(columns={col_codigo: "CD_MUN", col_nome: "NM_MUN"})
    gdf["CD_MUN"] = gdf["CD_MUN"].astype(str)
    if col_uf is None:
        gdf["SIGLA_UF"] = gdf["CD_MUN"].str[:2]  # cai para código numérico se a malha não trouxer a sigla
    else:
        gdf = gdf.rename(columns={col_uf: "SIGLA_UF"})
    if "AREA_KM2" not in gdf.columns:
        gdf["AREA_KM2"] = gdf.to_crs(epsg=5880).geometry.area / 1e6

    gdf = gdf[["CD_MUN", "NM_MUN", "SIGLA_UF", "AREA_KM2", "geometry"]]
    destino.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(destino, driver="GeoJSON")
    print(f"Malha simplificada salva em: {destino} ({len(gdf)} municípios)")
    return destino


def gera_geojsons(cultura_slug):
    paths = paths_ibge(cultura_slug)
    garante_malha_simplificada(paths)

    malha = gpd.read_file(paths["malha_simplificada"])
    malha["CD_MUN"] = malha["CD_MUN"].astype(str)

    out_dir = paths["geojson"]
    out_dir.mkdir(parents=True, exist_ok=True)

    csvs = sorted(glob.glob(str(paths["processado"] / "*.csv")))
    if not csvs:
        raise FileNotFoundError(f"Nenhum CSV em {paths['processado']} — rode 02_exportar_do_banco.py antes.")

    for csv_path in csvs:
        var_slug = os.path.splitext(os.path.basename(csv_path))[0]
        df = pd.read_csv(csv_path, dtype={"Codigo": str}, encoding="utf-8-sig")
        joined = malha.merge(df, left_on="CD_MUN", right_on="Codigo", how="left")
        joined["Teve_Prod"] = joined["Teve_Prod"].fillna(0).astype(int)
        colunas_ano = [c for c in df.columns if c not in ("Codigo", "Nome", "Teve_Prod")]
        for ano in colunas_ano:
            joined[ano] = joined[ano].fillna(0.0)
        joined = joined.rename(columns={"NM_MUN": "Nome_Malha"})
        joined["Nome"] = joined["Nome"].fillna(joined["Nome_Malha"])
        joined = joined.drop(columns=["Nome_Malha", "Codigo"]).rename(columns={"CD_MUN": "Codigo"})

        out_path = out_dir / f"{var_slug}.geojson"
        if out_path.exists():
            os.remove(out_path)
        joined.to_file(out_path, driver="GeoJSON")
        print(f"[{cultura_slug}] {var_slug}.geojson salvo ({len(joined)} municípios, {int(joined['Teve_Prod'].sum())} com produção)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python 03_gerar_geojson.py <cultura>")
        sys.exit(1)
    gera_geojsons(sys.argv[1])
