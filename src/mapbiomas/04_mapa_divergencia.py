# -*- coding: utf-8 -*-
"""
Estágio 4/5 do pipeline MapBiomas — "Parte 2" do framework: divergência de
variação, 2015-2024, no recorte automático (estados com a classe). Mesma
lógica do estágio 3 do IBGE, mas com os 2 mapas (percentual e absoluto)
combinados numa figura só, já que o MapBiomas tem 1 variável só (área).

Saída: data/mapbiomas/mapas/<cultura>/divergencia_<cultura>_2015_2024.png

Uso: python src/mapbiomas/04_mapa_divergencia.py <cultura>
"""
import sys
import os
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
from config import paths_mapbiomas, cultura as get_cultura  # noqa: E402

ANOS = [str(a) for a in range(2015, 2025)]
CAP_POSITIVO_PCT = 300
COR_NOVO = "#8e44ad"
LINTHRESH = 20
CAP_ABSOLUTO = 1000


def gera_mapa(cultura_slug):
    cfg = get_cultura(cultura_slug)
    paths = paths_mapbiomas(cultura_slug)
    gdf = gpd.read_file(paths["geojson"])
    for ano in ANOS:
        gdf[ano] = gdf[ano].astype(float)

    ufs_recorte = sorted(gdf.loc[gdf["Teve_Prod"] == 1, "SIGLA_UF"].unique())
    gdf = gdf[gdf["SIGLA_UF"].isin(ufs_recorte)].copy()

    n_municipios = [int((gdf[ano] > 0).sum()) for ano in ANOS]
    area_total = [gdf[ano].sum() for ano in ANOS]

    def indexa(serie):
        base = serie[0] if serie[0] else 1
        return [v / base * 100 for v in serie]

    idx_municipios, idx_area = indexa(n_municipios), indexa(area_total)

    tinha_2015, tem_2024 = gdf["2015"] > 0, gdf["2024"] > 0
    com_variacao = gdf[tinha_2015].copy()
    com_variacao["pct"] = (com_variacao["2024"] - com_variacao["2015"]) / com_variacao["2015"] * 100
    com_variacao["pct_plot"] = com_variacao["pct"].clip(upper=CAP_POSITIVO_PCT)
    novos = gdf[~tinha_2015 & tem_2024]
    nunca_pct = gdf[~tinha_2015 & ~tem_2024]
    n_truncados_pct = int((com_variacao["pct"] > CAP_POSITIVO_PCT).sum())

    tem_algum = (gdf["2015"] > 0) | (gdf["2024"] > 0)
    nunca_abs = gdf[~tem_algum]
    com_delta = gdf[tem_algum].copy()
    com_delta["delta"] = com_delta["2024"] - com_delta["2015"]
    com_delta["delta_plot"] = com_delta["delta"].clip(lower=-CAP_ABSOLUTO, upper=CAP_ABSOLUTO)
    n_truncados_abs = int((com_delta["delta"].abs() > CAP_ABSOLUTO).sum())

    fig = plt.figure(figsize=(26, 18))
    gs = gridspec.GridSpec(4, 2, height_ratios=[1, 0.5, 1.5, 0.1], hspace=0.3, wspace=0.08,
                            top=0.92, bottom=0.05, left=0.05, right=0.97)

    ax_linha = fig.add_subplot(gs[0, :])
    ax_linha.plot(ANOS, idx_municipios, marker="o", color="#2166ac", linewidth=2.5, label=f"Nº de municípios com área de {cultura_slug}")
    ax_linha.plot(ANOS, idx_area, marker="o", color="#1a9850", linewidth=2.5, label=f"Área total de {cultura_slug} (ha)")
    ax_linha.axhline(100, color="#999999", linewidth=1, linestyle="--")
    ax_linha.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, pos: f"{x:.1f}%"))
    ax_linha.set_ylabel("Variação em relação a 2015 (%)", fontsize=13, fontweight="bold")
    ax_linha.set_title(
        f"Divergência de variação (percentual e absoluta) — área de {cultura_slug}, MapBiomas (Coleção 11), 2015-2024\n"
        f"Recorte: {', '.join(ufs_recorte)}\nCada linha mostra a variação percentual acumulada desde 2015 (2015 = 100%). Valores na tabela abaixo.",
        fontsize=17,
    )
    ax_linha.legend(loc="upper left", fontsize=12, frameon=True, facecolor="white", edgecolor="none", framealpha=0.88)
    ax_linha.grid(axis="y", color="#eeeeee")
    for spine in ["top", "right"]:
        ax_linha.spines[spine].set_visible(False)
    ax_linha.annotate(f"{idx_municipios[-1]:.1f}%", xy=(ANOS[-1], idx_municipios[-1]), xytext=(8, -8),
                       textcoords="offset points", fontsize=11, color="#2166ac", va="center", fontweight="bold")
    ax_linha.annotate(f"{idx_area[-1]:.1f}%", xy=(ANOS[-1], idx_area[-1]), xytext=(8, 8),
                       textcoords="offset points", fontsize=11, color="#1a9850", va="center", fontweight="bold")

    ax_tabela = fig.add_subplot(gs[1, :])
    ax_tabela.axis("off")
    linhas_tabela = [
        [f"Municípios com área de {cultura_slug} (nº)"] + [f"{v:,}".replace(",", ".") for v in n_municipios],
        [f"Área total de {cultura_slug} (mil ha)"] + [f"{v/1000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") for v in area_total],
    ]
    largura_rotulo = 0.16
    largura_ano = (1 - largura_rotulo) / len(ANOS)
    tabela = ax_tabela.table(cellText=linhas_tabela, colLabels=["Valores absolutos"] + ANOS, cellLoc="center",
                              loc="center", bbox=[0, 0, 1, 1], colWidths=[largura_rotulo] + [largura_ano] * len(ANOS))
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(11.5)
    for (row, col), cell in tabela.get_celld().items():
        cell.set_edgecolor("#dddddd")
        if row == 0:
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#f2f2f2")
        if col == 0:
            cell.set_text_props(ha="left", fontweight="bold")
            cell.PAD = 0.02

    ax_pct = fig.add_subplot(gs[2, 0])
    if not nunca_pct.empty:
        nunca_pct.plot(ax=ax_pct, color="#e8e8e8", edgecolor="#cccccc", linewidth=0.1)
    if not novos.empty:
        novos.plot(ax=ax_pct, color=COR_NOVO, edgecolor="#555555", linewidth=0.15)
    com_variacao.plot(ax=ax_pct, column="pct_plot", cmap="RdBu_r",
                       norm=mcolors.TwoSlopeNorm(vmin=-100, vcenter=0, vmax=CAP_POSITIVO_PCT), edgecolor="#999999", linewidth=0.1)
    ax_pct.set_title(f"Variação PERCENTUAL da área de {cultura_slug}, 2015 → 2024\n"
                     f"(truncado em +{CAP_POSITIVO_PCT}%, {n_truncados_pct} municípios saturados · {len(novos)} novos produtores)", fontsize=14)
    ax_pct.set_anchor("C")
    ax_pct.set_axis_off()

    ax_abs = fig.add_subplot(gs[2, 1])
    norm_abs = mcolors.SymLogNorm(linthresh=LINTHRESH, vmin=-CAP_ABSOLUTO, vmax=CAP_ABSOLUTO)
    if not nunca_abs.empty:
        nunca_abs.plot(ax=ax_abs, color="#e8e8e8", edgecolor="#cccccc", linewidth=0.1)
    com_delta.plot(ax=ax_abs, column="delta_plot", cmap="RdBu_r", norm=norm_abs, edgecolor="#999999", linewidth=0.1)
    ax_abs.set_title(f"Variação ABSOLUTA da área de {cultura_slug}, 2015 → 2024\n"
                     f"(escala symlog, truncado em ±{CAP_ABSOLUTO} ha, {n_truncados_abs} municípios saturados)", fontsize=14)
    ax_abs.set_anchor("C")
    ax_abs.set_axis_off()

    pos_cbar = gs[3, 0].get_position(fig)
    cbar_ax1 = fig.add_axes([pos_cbar.x0 + 0.05, pos_cbar.y0, pos_cbar.width - 0.10, pos_cbar.height])
    sm1 = plt.cm.ScalarMappable(cmap="RdBu_r", norm=mcolors.TwoSlopeNorm(vmin=-100, vcenter=0, vmax=CAP_POSITIVO_PCT))
    sm1.set_array([])
    cbar1 = fig.colorbar(sm1, cax=cbar_ax1, orientation="horizontal")
    passo1 = max(round(CAP_POSITIVO_PCT / 5 / 10) * 10, 10)
    cbar1.set_ticks(sorted(set([-100, -50, 0] + list(range(passo1, CAP_POSITIVO_PCT + 1, passo1)))))
    cbar1.set_label(f"Variação (%) da área de {cultura_slug}", fontsize=11)

    pos_cbar2 = gs[3, 1].get_position(fig)
    cbar_ax2 = fig.add_axes([pos_cbar2.x0 + 0.05, pos_cbar2.y0, pos_cbar2.width - 0.10, pos_cbar2.height])
    sm2 = plt.cm.ScalarMappable(cmap="RdBu_r", norm=norm_abs)
    sm2.set_array([])
    cbar2 = fig.colorbar(sm2, cax=cbar_ax2, orientation="horizontal")
    ticks_positivos = [10 ** e for e in range(2, len(str(CAP_ABSOLUTO))) if CAP_ABSOLUTO / (10 ** e) >= 3] + [CAP_ABSOLUTO]
    cbar2.set_ticks(sorted(set([-t for t in ticks_positivos] + [0] + ticks_positivos)))
    cbar2.set_label(f"Delta de área de {cultura_slug} (ha)", fontsize=11)

    legenda = [
        mpatches.Patch(color=COR_NOVO, label=f"Novo produtor (não tinha área em 2015) — {len(novos)} municípios"),
        mpatches.Patch(color="#e8e8e8", label=f"Sem área de {cultura_slug} em 2015 nem 2024"),
    ]
    fig.legend(handles=legenda, loc="lower center", ncol=2, fontsize=11, bbox_to_anchor=(0.5, -0.005), frameon=False)

    fig.text(
        0.5, -0.035,
        f"Fonte: MapBiomas Brasil, Coleção 11 (classe {cfg.get('mapbiomas_classe_codigo')} - {cfg.get('mapbiomas_classe_nome', '')}). "
        f"Registros só em {', '.join(ufs_recorte)}. No mapa absoluto, delta bem definido para todos, inclusive quem entrou "
        "ou saiu do zero — por isso não há categoria \"novo produtor\" separada nele.",
        ha="center", fontsize=9.5, style="italic", color="#444444",
    )

    out_dir = paths["mapas"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"divergencia_{cultura_slug}_2015_2024.png"
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"[{cultura_slug}] Mapa de divergência salvo em: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python 04_mapa_divergencia.py <cultura>")
        sys.exit(1)
    gera_mapa(sys.argv[1])
