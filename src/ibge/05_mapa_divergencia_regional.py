# -*- coding: utf-8 -*-
"""
Estágio 5/6 do pipeline IBGE — "Parte 2" do framework: divergência entre
contração/expansão física e de valor, 2015-2024, no recorte regional da
cultura (config/culturas.yaml -> uf_recorte).

Produto: gráfico de linha (4 séries indexadas a 2015=100%) + tabela de
valores absolutos + 1 mapa de variação percentual por variável (área
destinada à colheita, quantidade produzida, valor real da produção),
escala divergente fria (queda) / quente (alta), com categoria à parte para
"novo produtor" (município sem produção em 2015 que passou a produzir).

Saída: data/ibge/mapas/<cultura>/divergencia_regional_<cultura>_2015_2024.png

Uso: python src/ibge/05_mapa_divergencia_regional.py <cultura>
"""
import sys
import os
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from shapely.geometry import MultiPolygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
from config import paths_ibge, cultura as get_cultura  # noqa: E402
from deflator_ipca import calcula_deflatores  # noqa: E402

ANOS = [str(a) for a in range(2015, 2025)]
COR_NOVO = "#8e44ad"

# (slug_geojson, titulo, unidade, deflacionar, cap_positivo_pct)
VARIAVEIS_MAPA = [
    ("area_destinada_colheita_ha", "Área destinada à colheita", "ha", False, 300),
    ("quantidade_produzida_t", "Quantidade produzida", "t", False, 300),
    ("valor_producao", "Valor real da produção", "mil R$ de dez/2024", True, 1000),
]


def remove_ilhas_oceanicas(geom, limite_lon=-38.0):
    """Vitória-ES inclui administrativamente a Ilha da Trindade, a ~1.100 km
    da costa — distorce o bounding box de recortes regionais que incluam ES.
    Remove partes do multipolígono cujo centroide fique a leste do limite."""
    if geom is None or geom.geom_type != "MultiPolygon":
        return geom
    partes = [p for p in geom.geoms if p.centroid.x <= limite_lon]
    if not partes:
        return geom
    return MultiPolygon(partes) if len(partes) > 1 else partes[0]


def gera_mapa(cultura_slug):
    cfg = get_cultura(cultura_slug)
    uf_recorte = cfg["uf_recorte"]
    titulo_recorte = ", ".join(uf_recorte)
    paths = paths_ibge(cultura_slug)
    deflatores = calcula_deflatores(2024)

    out_dir = paths["mapas"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"divergencia_regional_{cultura_slug}_2015_2024.png"

    qtd = pd.read_csv(paths["processado"] / "quantidade_produzida_t.csv", encoding="utf-8-sig", dtype={"Codigo": str})
    area = pd.read_csv(paths["processado"] / "area_destinada_colheita_ha.csv", encoding="utf-8-sig", dtype={"Codigo": str})
    valor = pd.read_csv(paths["processado"] / "valor_producao.csv", encoding="utf-8-sig", dtype={"Codigo": str})
    malha = gpd.read_file(paths["malha_simplificada"])[["CD_MUN", "SIGLA_UF"]].rename(columns={"CD_MUN": "Codigo"})

    for df in (qtd, area, valor):
        for ano in ANOS:
            df[ano] = df[ano].astype(float)

    def filtra_recorte(df):
        com_uf = df.merge(malha, on="Codigo", how="left")
        return com_uf[com_uf["SIGLA_UF"].isin(uf_recorte)]

    qtd_r, area_r, valor_r = filtra_recorte(qtd), filtra_recorte(area), filtra_recorte(valor)

    n_municipios = [int((qtd_r[ano] > 0).sum()) for ano in ANOS]
    area_total = [area_r[ano].sum() for ano in ANOS]
    qtd_total = [qtd_r[ano].sum() for ano in ANOS]
    valor_real_total = [valor_r[ano].sum() * deflatores[int(ano)] for ano in ANOS]

    def indexa(serie):
        base = serie[0] if serie[0] else 1
        return [v / base * 100 for v in serie]

    idx_municipios, idx_area = indexa(n_municipios), indexa(area_total)
    idx_qtd, idx_valor = indexa(qtd_total), indexa(valor_real_total)

    mapas_dados = []
    for slug_var, titulo_var, unidade_var, deflacionar, cap_pct in VARIAVEIS_MAPA:
        print(f"[{cultura_slug}] Lendo geojson de {titulo_var.lower()}...")
        gdf_var = gpd.read_file(paths["geojson"] / f"{slug_var}.geojson")
        gdf_var = gdf_var[gdf_var["SIGLA_UF"].isin(uf_recorte)].copy()
        gdf_var["geometry"] = gdf_var["geometry"].apply(remove_ilhas_oceanicas)
        for ano in ["2015", "2024"]:
            gdf_var[ano] = gdf_var[ano].astype(float)
            if deflacionar:
                gdf_var[ano] = gdf_var[ano] * deflatores[int(ano)]

        tinha_2015 = gdf_var["2015"] > 0
        tem_2024 = gdf_var["2024"] > 0
        com_variacao = gdf_var[tinha_2015].copy()
        com_variacao["pct"] = (com_variacao["2024"] - com_variacao["2015"]) / com_variacao["2015"] * 100
        com_variacao["pct_plot"] = com_variacao["pct"].clip(upper=cap_pct)
        novos = gdf_var[~tinha_2015 & tem_2024]
        nunca = gdf_var[~tinha_2015 & ~tem_2024]
        n_truncados = int((com_variacao["pct"] > cap_pct).sum())

        mapas_dados.append({"com_variacao": com_variacao, "novos": novos, "nunca": nunca,
                             "titulo": titulo_var, "unidade": unidade_var, "cap_pct": cap_pct, "n_truncados": n_truncados})

    n_mapas = len(VARIAVEIS_MAPA)
    fig = plt.figure(figsize=(28, 16))
    gs = gridspec.GridSpec(4, n_mapas, height_ratios=[1, 0.78, 1.35, 0.09], hspace=0.32, wspace=0.08,
                            top=0.91, bottom=0.09, left=0.05, right=0.97)

    ax_linha = fig.add_subplot(gs[0, :])
    ax_linha.plot(ANOS, idx_municipios, marker="o", color="#2166ac", linewidth=2.5, label="Nº de municípios produtores")
    ax_linha.plot(ANOS, idx_area, marker="o", color="#d6604d", linewidth=2.5, label="Área destinada à colheita (ha)")
    ax_linha.plot(ANOS, idx_qtd, marker="o", color="#f4a300", linewidth=2.5, label="Quantidade produzida (t)")
    ax_linha.plot(ANOS, idx_valor, marker="o", color="#1a9850", linewidth=2.5, label="Valor real da produção (R$ dez/2024)")
    ax_linha.axhline(100, color="#999999", linewidth=1, linestyle="--")
    ax_linha.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, pos: f"{x:.0f}%"))
    ax_linha.set_ylabel("Variação em relação a 2015 (%)", fontsize=12, fontweight="bold")
    ax_linha.set_title(
        f"Contração física x expansão de valor da cultura de {cultura_slug} — {titulo_recorte}, 2015-2024\n"
        "Cada linha mostra a variação percentual acumulada desde 2015 (2015 = 100%). Os valores absolutos estão na tabela abaixo.",
        fontsize=16,
    )
    ax_linha.legend(loc="upper left", fontsize=11, frameon=True, facecolor="white", edgecolor="none", framealpha=0.88)
    ax_linha.grid(axis="y", color="#eeeeee")
    for spine in ["top", "right"]:
        ax_linha.spines[spine].set_visible(False)
    fisicos = sorted([(idx_municipios, "#2166ac"), (idx_area, "#d6604d"), (idx_qtd, "#f4a300")], key=lambda s: s[0][-1])
    for rank, (serie, cor) in enumerate(fisicos):
        offset_y = (rank - (len(fisicos) - 1) / 2) * 10
        ax_linha.annotate(f"{serie[-1]:.0f}%", xy=(ANOS[-1], serie[-1]), xytext=(8, offset_y),
                           textcoords="offset points", fontsize=10, color=cor, va="center", fontweight="bold")
    ax_linha.annotate(f"{idx_valor[-1]:.0f}%", xy=(ANOS[-1], idx_valor[-1]), xytext=(8, 0),
                       textcoords="offset points", fontsize=10, color="#1a9850", va="center", fontweight="bold")

    ax_tabela = fig.add_subplot(gs[1, :])
    ax_tabela.axis("off")
    linhas_tabela = [
        ["Municípios produtores (nº)"] + [f"{v:,}".replace(",", ".") for v in n_municipios],
        ["Área destinada à colheita (mil ha)"] + [f"{v/1000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") for v in area_total],
        ["Quantidade produzida (mil t)"] + [f"{v/1000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") for v in qtd_total],
        ["Valor real da produção\n(R$ milhões, dez/2024)"] + [f"{v/1000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") for v in valor_real_total],
    ]
    largura_rotulo = 0.20
    largura_ano = (1 - largura_rotulo) / len(ANOS)
    tabela = ax_tabela.table(cellText=linhas_tabela, colLabels=["Valores absolutos"] + ANOS, cellLoc="center",
                              loc="center", bbox=[0, 0, 1, 1], colWidths=[largura_rotulo] + [largura_ano] * len(ANOS))
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(10.5)
    for (row, col), cell in tabela.get_celld().items():
        cell.set_edgecolor("#dddddd")
        if row == 0:
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#f2f2f2")
        if col == 0:
            cell.set_text_props(ha="left", fontweight="bold")
            cell.PAD = 0.02

    for idx, dados_var in enumerate(mapas_dados):
        com_variacao, novos, nunca, cap_pct = dados_var["com_variacao"], dados_var["novos"], dados_var["nunca"], dados_var["cap_pct"]
        ax = fig.add_subplot(gs[2, idx])
        if not nunca.empty:
            nunca.plot(ax=ax, color="#e8e8e8", edgecolor="#cccccc", linewidth=0.15)
        if not novos.empty:
            novos.plot(ax=ax, color=COR_NOVO, edgecolor="#555555", linewidth=0.2)
        com_variacao.plot(ax=ax, column="pct_plot", cmap="RdBu_r",
                           norm=mcolors.TwoSlopeNorm(vmin=-100, vcenter=0, vmax=cap_pct), edgecolor="#999999", linewidth=0.15)
        ax.set_title(f"{dados_var['titulo']} — variação % 2015→2024\n"
                     f"(truncado em +{cap_pct}%, {dados_var['n_truncados']} municípios saturados · {len(novos)} novos produtores)", fontsize=12)
        ax.set_anchor("C")
        ax.set_axis_off()

        pos_cbar = gs[3, idx].get_position(fig)
        cbar_ax = fig.add_axes([pos_cbar.x0 + pos_cbar.width * 0.1, pos_cbar.y0, pos_cbar.width * 0.8, pos_cbar.height])
        sm = plt.cm.ScalarMappable(cmap="RdBu_r", norm=mcolors.TwoSlopeNorm(vmin=-100, vcenter=0, vmax=cap_pct))
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
        passo = max(round(cap_pct / 5 / 10) * 10, 10)
        cbar.set_ticks(sorted(set([-100, -50, 0] + list(range(passo, cap_pct + 1, passo)))))
        cbar.set_label(f"Variação (%) — {dados_var['unidade']}", fontsize=9)

    legenda = [
        mpatches.Patch(color=COR_NOVO, label="Novo produtor (não produzia em 2015)"),
        mpatches.Patch(color="#e8e8e8", label="Sem produção em 2015 nem 2024"),
    ]
    fig.legend(handles=legenda, loc="lower center", ncol=2, fontsize=10.5, bbox_to_anchor=(0.5, 0.045), frameon=False)

    fig.text(
        0.5, 0.012,
        r"Valores monetários deflacionados pelo IPCA (IBGE, série 433 SGS/Banco Central) para R\$ de dezembro/2024. "
        f"% de variação só é definida para municípios que já produziam em 2015. Recorte: {titulo_recorte}.",
        ha="center", fontsize=9.5, style="italic", color="#444444",
    )

    plt.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"[{cultura_slug}] Mapa de divergência regional salvo em: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python 05_mapa_divergencia_regional.py <cultura>")
        sys.exit(1)
    gera_mapa(sys.argv[1])
