# -*- coding: utf-8 -*-
"""
Estágio 4/6 do pipeline IBGE — "Parte 1" do framework: evolução histórica
NACIONAL da cultura, da primeira safra disponível no SIDRA até o último ano
processado. Usa "área colhida" (não "área destinada à colheita", que só
existe a partir de 1988) para aproveitar a série mais longa possível.

Produto: gráfico de linha (nº de municípios + área, indexados a 100% no
primeiro ano) + tabela de valores absolutos em anos marcantes + 3 mapas-
retrato (primeiro ano / ano intermediário / último ano).

Saída: data/ibge/mapas/<cultura>/evolucao_historica_<cultura>.png

Uso: python src/ibge/04_mapa_evolucao_historica.py <cultura>
"""
import sys
import os
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
from config import paths_ibge, cultura as get_cultura  # noqa: E402

ULTIMO_ANO = 2024


def gera_mapa(cultura_slug):
    cfg = get_cultura(cultura_slug)
    ano_inicio = cfg.get("ano_inicio_ibge", 1974)
    paths = paths_ibge(cultura_slug)

    geojson_path = paths["geojson"] / "area_colhida_ha.geojson"
    if not geojson_path.exists():
        raise FileNotFoundError(f"{geojson_path} não encontrado — rode 03_gerar_geojson.py antes.")

    out_dir = paths["mapas"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"evolucao_historica_{cultura_slug}.png"

    anos_todos = [str(a) for a in range(ano_inicio, ULTIMO_ANO + 1)]
    ano_meio = str(ano_inicio + (ULTIMO_ANO - ano_inicio) // 2)
    anos_mapa = [str(ano_inicio), ano_meio, str(ULTIMO_ANO)]
    anos_tabela = sorted(set([str(ano_inicio)] + [str(a) for a in range(ano_inicio, ULTIMO_ANO, 10)] + [str(ULTIMO_ANO)]), key=int)

    print(f"[{cultura_slug}] Lendo geojson nacional (área colhida, série {ano_inicio}-{ULTIMO_ANO})...")
    gdf = gpd.read_file(geojson_path)
    for ano in anos_todos:
        gdf[ano] = gdf[ano].astype(float)

    n_municipios = [int((gdf[ano] > 0).sum()) for ano in anos_todos]
    area_total = [gdf[ano].sum() for ano in anos_todos]

    def indexa(serie):
        base = serie[0] if serie[0] else 1
        return [v / base * 100 for v in serie]

    idx_municipios = indexa(n_municipios)
    idx_area = indexa(area_total)

    vmax_mapa = gdf[anos_mapa].max().max()
    vmin_mapa = max(gdf[anos_mapa][gdf[anos_mapa] > 0].min().min(), 1)
    sem_producao = gdf[(gdf[anos_mapa] == 0).all(axis=1)]

    fig = plt.figure(figsize=(20, 19))
    gs = gridspec.GridSpec(4, 3, height_ratios=[1, 0.55, 1.6, 0.09], hspace=0.28, wspace=0.06,
                            top=0.93, bottom=0.06, left=0.06, right=0.96)

    ax_linha = fig.add_subplot(gs[0, :])
    ax_linha.plot(anos_todos, idx_municipios, marker="o", markersize=3, color="#2166ac", linewidth=2,
                  label=f"Nº de municípios com área colhida de {cultura_slug}")
    ax_linha.plot(anos_todos, idx_area, marker="o", markersize=3, color="#1a9850", linewidth=2,
                  label=f"Área colhida total de {cultura_slug} (ha)")
    ax_linha.axhline(100, color="#999999", linewidth=1, linestyle="--")
    ax_linha.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, pos: f"{x:.0f}%"))
    ax_linha.set_ylabel(f"Variação em relação a {ano_inicio} (%)", fontsize=12, fontweight="bold")
    ax_linha.set_xticks(anos_todos[::2])
    ax_linha.tick_params(axis="x", rotation=90, labelsize=8)
    ax_linha.set_title(
        f"Evolução da área colhida de {cultura_slug} — IBGE (SIDRA/PAM), {ano_inicio}-{ULTIMO_ANO}\nRecorte: Brasil inteiro\n"
        f"Cada linha mostra a variação percentual acumulada desde {ano_inicio} ({ano_inicio} = 100%). Os valores absolutos estão na tabela abaixo.",
        fontsize=16,
    )
    ax_linha.legend(loc="upper left", fontsize=11, frameon=True, facecolor="white", edgecolor="none", framealpha=0.88)
    ax_linha.grid(axis="y", color="#eeeeee")
    for spine in ["top", "right"]:
        ax_linha.spines[spine].set_visible(False)
    ax_linha.annotate(f"{idx_municipios[-1]:.0f}%", xy=(anos_todos[-1], idx_municipios[-1]), xytext=(8, 0),
                       textcoords="offset points", fontsize=10, color="#2166ac", va="center", fontweight="bold")
    ax_linha.annotate(f"{idx_area[-1]:.0f}%", xy=(anos_todos[-1], idx_area[-1]), xytext=(8, 0),
                       textcoords="offset points", fontsize=10, color="#1a9850", va="center", fontweight="bold")

    ax_tabela = fig.add_subplot(gs[1, :])
    ax_tabela.axis("off")
    linhas_tabela = [
        [f"Municípios com área colhida de {cultura_slug} (nº)"] + [f"{n_municipios[anos_todos.index(a)]:,}".replace(",", ".") for a in anos_tabela],
        [f"Área colhida total de {cultura_slug} (mil ha)"] + [f"{area_total[anos_todos.index(a)]/1000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") for a in anos_tabela],
    ]
    largura_rotulo = 0.24
    largura_ano = (1 - largura_rotulo) / len(anos_tabela)
    tabela = ax_tabela.table(
        cellText=linhas_tabela, colLabels=["Valores absolutos"] + anos_tabela,
        cellLoc="center", loc="center", bbox=[0, 0, 1, 1],
        colWidths=[largura_rotulo] + [largura_ano] * len(anos_tabela),
    )
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

    for i, ano in enumerate(anos_mapa):
        ax = fig.add_subplot(gs[2, i])
        if not sem_producao.empty:
            sem_producao.plot(ax=ax, color="#e8e8e8", edgecolor="#cccccc", linewidth=0.1)
        com_valor = gdf[gdf[ano] > 0]
        sem_valor_mas_com_historico = gdf[(gdf[anos_mapa] > 0).any(axis=1) & (gdf[ano] == 0)]
        if not sem_valor_mas_com_historico.empty:
            sem_valor_mas_com_historico.plot(ax=ax, color="#f5f0e6", edgecolor="#cccccc", linewidth=0.1)
        com_valor.plot(
            ax=ax, column=ano, cmap="YlOrRd",
            norm=mcolors.LogNorm(vmin=vmin_mapa, vmax=vmax_mapa),
            edgecolor="#999999", linewidth=0.08,
        )
        n_ano = n_municipios[anos_todos.index(ano)]
        ax.set_title(f"Área colhida de {cultura_slug} — {ano}  ({n_ano} municípios)", fontsize=13)
        ax.set_anchor("C")
        ax.set_axis_off()

    pos_cbar = gs[3, :].get_position(fig)
    cbar_ax = fig.add_axes([0.35, pos_cbar.y0, 0.3, pos_cbar.height])
    sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=mcolors.LogNorm(vmin=vmin_mapa, vmax=vmax_mapa))
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
    cbar.set_label(f"Área colhida de {cultura_slug} (ha, escala log)", fontsize=10)

    fig.text(
        0.5, 0.015,
        f"Fonte: IBGE, SIDRA (Tabela 1613 - PAM), área colhida de {cultura_slug}. Recorte: Brasil inteiro. "
        "Cinza claro = município nunca produziu nos 3 anos-retrato; bege = produziu em algum dos 3 anos-retrato mas não no ano mostrado.",
        ha="center", fontsize=9, style="italic", color="#444444",
    )

    plt.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"[{cultura_slug}] Mapa histórico salvo em: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python 04_mapa_evolucao_historica.py <cultura>")
        sys.exit(1)
    gera_mapa(sys.argv[1])
