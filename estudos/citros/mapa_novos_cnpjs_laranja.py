# -*- coding: utf-8 -*-
"""
Ferramenta pontual (fora do pipeline 01-06): junta o resultado da consulta
BigQuery de novos CNPJs (CNAE 0131-8/00 - Cultivo de laranja, abertos entre
2024-03 e 2026-03, agregado por município) com a malha municipal, e gera:
  - xlsx com os dados + geometria ausente sinalizada
  - gpkg (geometria + atributos)
  - um mapa coroplético de gradiente (nº de novos estabelecimentos por município)

Entrada: CSV exportado do BigQuery (colunas: id_municipio, municipio,
sigla_uf, novos_estabelecimentos, capital_social_total, capital_social_medio)

Uso:
    python estudos/citros/mapa_novos_cnpjs_laranja.py --csv "caminho/para/script_job_....csv" --saida "caminho/saida/novos_cnpjs_laranja"
"""
import argparse
import os
import sys

import geopandas as gpd
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "comum"))
from config import DATA  # noqa: E402

MALHA_SIMPLIFICADA = DATA / "geo" / "municipios_brasil_simplificado.geojson"
MALHA_COMPLETA = DATA / "geo" / "malha_municipios_brasil.shp"


def junta_e_gera(csv_path, saida_base):
    df = pd.read_csv(csv_path, dtype={"id_municipio": str})
    df["id_municipio"] = df["id_municipio"].str.zfill(7)

    malha_path = MALHA_SIMPLIFICADA if MALHA_SIMPLIFICADA.exists() else MALHA_COMPLETA
    if not malha_path.exists():
        raise FileNotFoundError(f"Malha municipal não encontrada ({MALHA_SIMPLIFICADA} nem {MALHA_COMPLETA}).")
    malha = gpd.read_file(malha_path)
    col_codigo_malha = "CD_MUN" if "CD_MUN" in malha.columns else "Codigo"
    malha[col_codigo_malha] = malha[col_codigo_malha].astype(str).str.zfill(7)
    malha = malha.rename(columns={col_codigo_malha: "CD_MUN"})[["CD_MUN", "geometry"]]

    gdf = malha.merge(df, left_on="CD_MUN", right_on="id_municipio", how="left")
    gdf["novos_estabelecimentos"] = gdf["novos_estabelecimentos"].fillna(0).astype(int)

    faltantes = set(df["id_municipio"]) - set(malha["CD_MUN"])
    if faltantes:
        print(f"Aviso: {len(faltantes)} município(s) do CSV sem geometria na malha: {sorted(faltantes)[:5]}...")

    saida_base = str(saida_base)
    xlsx_path = saida_base + ".xlsx"
    gpkg_path = saida_base + ".gpkg"
    png_path = saida_base + "_mapa.png"

    df_saida = df.sort_values("novos_estabelecimentos", ascending=False)
    df_saida.to_excel(xlsx_path, index=False)
    print(f"Excel salvo em: {xlsx_path} ({len(df_saida)} municípios com abertura)")

    gdf_saida = gdf.drop(columns=["id_municipio"])
    gdf_saida.to_file(gpkg_path, driver="GPKG")
    print(f"GeoPackage salvo em: {gpkg_path} ({len(gdf_saida)} municípios, Brasil inteiro)")

    gera_mapa(gdf, png_path)
    print(f"Mapa salvo em: {png_path}")


def gera_mapa(gdf, png_path):
    com_abertura = gdf[gdf["novos_estabelecimentos"] > 0]
    sem_abertura = gdf[gdf["novos_estabelecimentos"] == 0]

    vmin = 1
    vmax = int(gdf["novos_estabelecimentos"].max())

    fig = plt.figure(figsize=(12, 13.2))
    gs = fig.add_gridspec(3, 1, height_ratios=[0.09, 1, 0.14], hspace=0.02,
                           top=0.94, bottom=0.04, left=0.04, right=0.96)

    ax_titulo = fig.add_subplot(gs[0, 0])
    ax_titulo.axis("off")
    ax_titulo.text(
        0.5, 0.5,
        "Novos CNPJs de cultivo de laranja (CNAE 0131-8/00) por município\n"
        "Abertura entre mar/2024 e mar/2026 — Receita Federal (Base dos Dados / BigQuery)",
        ha="center", va="center", fontsize=13,
    )

    ax = fig.add_subplot(gs[1, 0])
    if not sem_abertura.empty:
        sem_abertura.plot(ax=ax, color="#e8e8e8", edgecolor="#cccccc", linewidth=0.1)
    com_abertura.plot(
        ax=ax, column="novos_estabelecimentos", cmap="YlOrRd",
        norm=mcolors.LogNorm(vmin=vmin, vmax=vmax),
        edgecolor="#999999", linewidth=0.1,
        legend=False,
    )
    ax.set_axis_off()

    ax_rodape = fig.add_subplot(gs[2, 0])
    ax_rodape.axis("off")
    cbar_ax = ax_rodape.inset_axes([0.28, 0.55, 0.44, 0.18])
    sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=mcolors.LogNorm(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
    cbar.set_label("Nº de novos estabelecimentos (escala log)", fontsize=10)

    ax_rodape.text(
        0.5, 0.05,
        "Cinza claro = sem CNPJ de cultivo de laranja aberto no período. Indicador de abertura formal de empresas,"
        " não de área plantada — complementar aos dados de IBGE/MapBiomas.",
        ha="center", va="bottom", fontsize=8.5, style="italic", color="#444444",
        transform=ax_rodape.transAxes,
    )

    plt.savefig(png_path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", required=True, help="CSV exportado do BigQuery (agregado por município)")
    parser.add_argument("--saida", default=None, help="caminho de saída sem extensão (default: ao lado do CSV)")
    args = parser.parse_args()

    saida = args.saida or os.path.splitext(args.csv)[0] + "_mapeado"
    junta_e_gera(args.csv, saida)
