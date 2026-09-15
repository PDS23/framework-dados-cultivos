# -*- coding: utf-8 -*-
"""
Estágio 3/5 do pipeline MapBiomas — "Parte 1" do framework: evolução
histórica da área da classe, 1985-2024. O recorte geográfico é AUTOMÁTICO:
só os estados onde a classe tem pelo menos 1 registro (Teve_Prod=1) — o
MapBiomas costuma não cobrir uma cultura em todo o território nacional
(ex.: citros só aparece em SP/MG/PR/GO/MS na Coleção 11).

Produto: gráfico de linha (nº de municípios + área, indexados a 100% em
1985) + tabela de valores absolutos em anos marcantes + 3 mapas-retrato
(1985 / ano intermediário / 2024).

Saída: data/mapbiomas/mapas/<cultura>/evolucao_historica_<cultura>.png

Uso: python src/mapbiomas/03_mapa_evolucao_historica.py <cultura>
"""
import sys
import os
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
from config import paths_mapbiomas, cultura as get_cultura  # noqa: E402

ANO_INICIO, ANO_FIM = 1985, 2024


def gera_mapa(cultura_slug):
    cfg = get_cultura(cultura_slug)
    paths = paths_mapbiomas(cultura_slug)
    geojson_path = paths["geojson"]
    if not geojson_path.exists():
        raise FileNotFoundError(f"{geojson_path} não encontrado — rode 02_gerar_geojson.py antes.")

    anos_todos = [str(a) for a in range(ANO_INICIO, ANO_FIM + 1)]
    ano_meio = str(ANO_INICIO + (ANO_FIM - ANO_INICIO) // 2)
    anos_mapa = [str(ANO_INICIO), ano_meio, str(ANO_FIM)]
    anos_tabela = sorted(set([str(ANO_INICIO)] + [str(a) for a in range(ANO_INICIO, ANO_FIM, 5)] + [str(ANO_FIM)]), key=int)

    print(f"[{cultura_slug}] Lendo geojson (MapBiomas)...")
    gdf = gpd.read_file(geojson_path)
    for ano in anos_todos:
        gdf[ano] = gdf[ano].astype(float)

    ufs_recorte = sorted(gdf.loc[gdf["Teve_Prod"] == 1, "SIGLA_UF"].unique())
    if not ufs_recorte:
        raise ValueError(f"Nenhum estado com Teve_Prod=1 para {cultura_slug} — confira o código de classe no config.")
    gdf = gdf[gdf["SIGLA_UF"].isin(ufs_recorte)].copy()
    print(f"[{cultura_slug}] Recorte automático (estados com a classe): {', '.join(ufs_recorte)}")

    n_municipios = [int((gdf[ano] > 0).sum()) for ano in anos_todos]
    area_total = [gdf[ano].sum() for ano in anos_todos]

    def indexa(serie):
        base = serie[0] if serie[0] else 1
        return [v / base * 100 for v in serie]

    idx_municipios, idx_area = indexa(n_municipios), indexa(area_total)
    vmax_mapa = gdf[anos_mapa].max().max()
    vmin_mapa = max(gdf[anos_mapa][gdf[anos_mapa] > 0].min().min(), 1)
    sem_producao = gdf[gdf["Teve_Prod"] == 0]

    fig = plt.figure(figsize=(20, 19))
    gs = gridspec.GridSpec(4, 3, height_ratios=[1, 0.55, 1.6, 0.09], hspace=0.28, wspace=0.06,
                            top=0.93, bottom=0.06, left=0.06, right=0.96)

    ax_linha = fig.add_subplot(gs[0, :])
    ax_linha.plot(anos_todos, idx_municipios, marker="o", markersize=3, color="#2166ac", linewidth=2,
                  label=f"Nº de municípios com área de {cultura_slug}")
    ax_linha.plot(anos_todos, idx_area, marker="o", markersize=3, color="#1a9850", linewidth=2,
                  label=f"Área total de {cultura_slug} (ha)")
    ax_linha.axhline(100, color="#999999", linewidth=1, linestyle="--")
    ax_linha.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, pos: f"{x:.1f}%"))
    ax_linha.set_ylabel(f"Variação em relação a {ANO_INICIO} (%)", fontsize=12, fontweight="bold")
    ax_linha.set_xticks(anos_todos[::2])
    ax_linha.tick_params(axis="x", rotation=90, labelsize=8)
    ax_linha.set_title(
        f"Evolução da área de {cultura_slug} — MapBiomas (Coleção 11), {ANO_INICIO}-{ANO_FIM}\n"
        f"Recorte: {', '.join(ufs_recorte)} (únicos estados com registro da classe)\n"
        f"Cada linha mostra a variação percentual acumulada desde {ANO_INICIO} ({ANO_INICIO} = 100%). Valores absolutos na tabela abaixo.",
        fontsize=16,
    )
    ax_linha.legend(loc="upper left", fontsize=11, frameon=True, facecolor="white", edgecolor="none", framealpha=0.88)
    ax_linha.grid(axis="y", color="#eeeeee")
    for spine in ["top", "right"]:
        ax_linha.spines[spine].set_visible(False)
    ax_linha.annotate(f"{idx_municipios[-1]:.1f}%", xy=(anos_todos[-1], idx_municipios[-1]), xytext=(8, 0),
                       textcoords="offset points", fontsize=10, color="#2166ac", va="center", fontweight="bold")
    ax_linha.annotate(f"{idx_area[-1]:.1f}%", xy=(anos_todos[-1], idx_area[-1]), xytext=(8, 0),
                       textcoords="offset points", fontsize=10, color="#1a9850", va="center", fontweight="bold")

    ax_tabela = fig.add_subplot(gs[1, :])
    ax_tabela.axis("off")
    linhas_tabela = [
        [f"Municípios com área de {cultura_slug} (nº)"] + [f"{n_municipios[anos_todos.index(a)]:,}".replace(",", ".") for a in anos_tabela],
        [f"Área total de {cultura_slug} (mil ha)"] + [f"{area_total[anos_todos.index(a)]/1000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") for a in anos_tabela],
    ]
    largura_rotulo = 0.22
    largura_ano = (1 - largura_rotulo) / len(anos_tabela)
    tabela = ax_tabela.table(cellText=linhas_tabela, colLabels=["Valores absolutos"] + anos_tabela, cellLoc="center",
                              loc="center", bbox=[0, 0, 1, 1], colWidths=[largura_rotulo] + [largura_ano] * len(anos_tabela))
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
        sem_valor_mas_com_historico = gdf[(gdf["Teve_Prod"] == 1) & (gdf[ano] == 0)]
        if not sem_valor_mas_com_historico.empty:
            sem_valor_mas_com_historico.plot(ax=ax, color="#f5f0e6", edgecolor="#cccccc", linewidth=0.1)
        com_valor.plot(ax=ax, column=ano, cmap="YlOrRd", norm=mcolors.LogNorm(vmin=vmin_mapa, vmax=vmax_mapa),
                       edgecolor="#999999", linewidth=0.1)
        n_ano = n_municipios[anos_todos.index(ano)]
        ax.set_title(f"Área de {cultura_slug} — {ano}  ({n_ano} municípios)", fontsize=13)
        ax.set_anchor("C")
        ax.set_axis_off()

    pos_cbar = gs[3, :].get_position(fig)
    cbar_ax = fig.add_axes([0.35, pos_cbar.y0, 0.3, pos_cbar.height])
    sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=mcolors.LogNorm(vmin=vmin_mapa, vmax=vmax_mapa))
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
    cbar.set_label(f"Área de {cultura_slug} identificada por satélite (ha, escala log)", fontsize=10)

    fig.text(
        0.5, 0.015,
        f"Fonte: MapBiomas Brasil, Coleção 11 (classe {cfg.get('mapbiomas_classe_codigo')} - {cfg.get('mapbiomas_classe_nome', '')}).\n"
        f"A classe só tem registros em {', '.join(ufs_recorte)} — não há dados para os demais estados nessa série.",
        ha="center", fontsize=9, style="italic", color="#444444",
    )

    out_dir = paths["mapas"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"evolucao_historica_{cultura_slug}.png"
    plt.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"[{cultura_slug}] Mapa histórico salvo em: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python 03_mapa_evolucao_historica.py <cultura>")
        sys.exit(1)
    gera_mapa(sys.argv[1])
