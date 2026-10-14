# -*- coding: utf-8 -*-
"""
Relatório das regiões candidatas a expansão da citricultura: lê
resultados.expansao_regional (calculado em SQL por db/03_calcular_resultados.sql,
com buffer espacial ao redor de cada município-semente, cruzando PAM, MapBiomas
e novos CNPJs) e gera:
  - xlsx (1 aba "Resumo" + 1 aba por região)
  - gpkg (municípios do raio + buffer de cada região)
  - png com 1 mapa por região

Os municípios-semente e o raio ficam em db/03_calcular_resultados.sql.

Uso:
    PGPASSWORD=... python estudos/citros/relatorio_regioes_expansao.py [--saida pasta]
"""
import argparse
import os
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "comum"))
import db  # noqa: E402
from config import DATA  # noqa: E402

SQL_MUNICIPIOS = """
    SELECT r.municipio_semente, sem.nome || ' (' || se.sigla || ')' AS regiao, r.raio_km,
           r.id_municipio, m.nome, e.sigla AS uf, r.eh_semente AS semente, r.distancia_km,
           r.pam_area_colhida_ha_2015, r.pam_area_colhida_ha_2024,
           r.mapbiomas_area_ha_2015, r.mapbiomas_area_ha_2024, r.novos_cnpjs_2024_2026,
           m.geom
    FROM resultados.expansao_regional r
    JOIN dim.municipios m ON m.id_municipio = r.id_municipio
    JOIN dim.estados e ON e.id_estado = m.id_estado
    JOIN dim.municipios sem ON sem.id_municipio = r.municipio_semente
    JOIN dim.estados se ON se.id_estado = sem.id_estado
"""
SQL_BUFFERS = """
    SELECT DISTINCT r.municipio_semente, r.raio_km,
           ST_Buffer(sem.geom::geography, r.raio_km * 1000)::geometry AS geom
    FROM resultados.expansao_regional r
    JOIN dim.municipios sem ON sem.id_municipio = r.municipio_semente
"""


def carrega():
    with db.engine().connect() as conn:
        municipios = gpd.read_postgis(SQL_MUNICIPIOS, conn, geom_col="geom")
        buffers = gpd.read_postgis(SQL_BUFFERS, conn, geom_col="geom")
    if municipios.empty:
        raise RuntimeError("resultados.expansao_regional está vazia — rode db/03_calcular_resultados.sql antes.")
    return municipios, buffers.set_index("municipio_semente")


def variacao(total_2015, total_2024):
    return round((total_2024 / total_2015 - 1) * 100, 1) if total_2015 > 0 else None


def gera_xlsx(municipios, caminho):
    colunas = ["id_municipio", "nome", "uf", "semente", "distancia_km", "pam_area_colhida_ha_2015", "pam_area_colhida_ha_2024",
               "mapbiomas_area_ha_2015", "mapbiomas_area_ha_2024", "novos_cnpjs_2024_2026"]
    resumo = []
    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        for regiao, grupo in municipios.groupby("regiao", sort=False):
            tabela = grupo.drop(columns="geom").sort_values(["semente", "novos_cnpjs_2024_2026"], ascending=[False, False])[colunas]
            tabela.round(1).to_excel(writer, sheet_name=regiao.replace("(", "").replace(")", "")[:31], index=False)
            resumo.append({
                "regiao_semente": regiao,
                "n_municipios_no_raio": len(grupo) - 1,
                "pam_area_colhida_ha_2024": grupo["pam_area_colhida_ha_2024"].sum(),
                "pam_variacao_2015_2024_pct": variacao(grupo["pam_area_colhida_ha_2015"].sum(), grupo["pam_area_colhida_ha_2024"].sum()),
                "mapbiomas_area_ha_2024": round(grupo["mapbiomas_area_ha_2024"].sum(), 1),
                "mapbiomas_variacao_2015_2024_pct": variacao(grupo["mapbiomas_area_ha_2015"].sum(), grupo["mapbiomas_area_ha_2024"].sum()),
                "novos_cnpjs_2024_2026": int(grupo["novos_cnpjs_2024_2026"].sum()),
            })
        pd.DataFrame(resumo).to_excel(writer, sheet_name="Resumo", index=False)
    print(f"Excel salvo em: {caminho}")


def gera_gpkg(municipios, buffers, caminho):
    if caminho.exists():
        caminho.unlink()
    for semente, grupo in municipios.groupby("municipio_semente"):
        grupo.to_file(caminho, driver="GPKG", layer=f"municipios_{semente}", mode="a" if caminho.exists() else "w")
        buf = gpd.GeoDataFrame({"municipio_semente": [semente], "raio_km": [float(buffers.loc[semente, "raio_km"])]},
                               geometry=[buffers.loc[semente, "geom"]], crs=4326)
        buf.to_file(caminho, driver="GPKG", layer=f"buffer_{semente}", mode="a")
    print(f"GeoPackage salvo em: {caminho}")


def gera_mapa(municipios, buffers, caminho):
    regioes = list(municipios.groupby("regiao", sort=False))
    fig, axes = plt.subplots(2, 2, figsize=(16, 16))
    for ax, (regiao, gdf) in zip(axes.flat, regioes):
        gdf = gdf.copy()
        gdf["indicador"] = gdf[["pam_area_colhida_ha_2024", "mapbiomas_area_ha_2024"]].max(axis=1)
        semente = gdf.loc[gdf["semente"], "municipio_semente"].iloc[0]
        raio = float(buffers.loc[semente, "raio_km"])
        gpd.GeoSeries([buffers.loc[semente, "geom"]], crs=4326).boundary.plot(ax=ax, color="#2166ac", linewidth=1.5, linestyle="--")

        sem_producao, com_producao = gdf[gdf["indicador"] <= 0], gdf[gdf["indicador"] > 0]
        if not sem_producao.empty:
            sem_producao.plot(ax=ax, color="#eeeeee", edgecolor="#bbbbbb", linewidth=0.4)
        if not com_producao.empty:
            com_producao.plot(ax=ax, column="indicador", cmap="YlOrRd", norm=mcolors.LogNorm(vmin=1, vmax=max(com_producao["indicador"].max(), 1)),
                              edgecolor="#999999", linewidth=0.4)
        com_cnpj = gdf[gdf["novos_cnpjs_2024_2026"] > 0]
        if not com_cnpj.empty:
            centroides = com_cnpj.geometry.to_crs(5880).centroid.to_crs(4326)
            ax.scatter(centroides.x, centroides.y, s=com_cnpj["novos_cnpjs_2024_2026"] * 25 + 15,
                       facecolor="none", edgecolor="#1a1a2e", linewidth=1.3, zorder=5)
        gdf[gdf["semente"]].boundary.plot(ax=ax, color="#00b300", linewidth=2.2, zorder=6)
        ax.set_title(f"{regiao} — raio de {raio:g} km", fontsize=13, fontweight="bold")
        ax.set_axis_off()

    fig.suptitle(
        "Regiões candidatas a expansão da citricultura\n"
        "Cor = área de laranja 2024 (PAM ou MapBiomas, o que for maior, escala log) · "
        "Círculo = novos CNPJs de cultivo de laranja (2024-2026) · Contorno verde = município-semente",
        fontsize=13,
    )
    fig.text(0.5, 0.005, "Fontes: IBGE (PAM), MapBiomas Coleção 11, Receita Federal (Base dos Dados/BigQuery).",
             ha="center", fontsize=9, style="italic", color="#444444")
    plt.tight_layout(rect=[0, 0.02, 1, 0.95])
    plt.savefig(caminho, dpi=130)
    plt.close(fig)
    print(f"Mapa salvo em: {caminho}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--saida", type=Path, default=DATA / "analises" / "regioes_expansao")
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    municipios, buffers = carrega()
    gera_xlsx(municipios, args.saida / "regioes_expansao_citros.xlsx")
    gera_gpkg(municipios, buffers, args.saida / "regioes_expansao_citros.gpkg")
    gera_mapa(municipios, buffers, args.saida / "regioes_expansao_citros_mapa.png")
