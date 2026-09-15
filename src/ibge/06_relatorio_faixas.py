# -*- coding: utf-8 -*-
"""
Estágio 6/6 do pipeline IBGE: conta, para cada variável, quantos municípios
do recorte regional da cultura caem em cada faixa de variação percentual
2015->2024 (mesma lógica/dados do mapa de divergência regional). Gera um
.md (tabela por UF x faixa) e um .json (mesmos dados, para o gerador de
docx em relatorios/build_docx.js).

Saída:
  data/ibge/relatorios/<cultura>/faixas_2015_2024.md
  data/ibge/relatorios/<cultura>/faixas_2015_2024.json

Uso: python src/ibge/06_relatorio_faixas.py <cultura>
"""
import sys
import os
import json
import geopandas as gpd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
from config import paths_ibge, cultura as get_cultura  # noqa: E402
from deflator_ipca import calcula_deflatores  # noqa: E402
from faixas import FAIXAS, classifica_row, tabela_md  # noqa: E402

VARIAVEIS = [
    ("area_destinada_colheita_ha", "Área destinada à colheita", "ha", False),
    ("quantidade_produzida_t", "Quantidade produzida", "t", False),
    ("valor_producao", "Valor real da produção", "mil R$ de dez/2024", True),
]


def gera_relatorio(cultura_slug):
    cfg = get_cultura(cultura_slug)
    uf_recorte = cfg["uf_recorte"]
    titulo_recorte = ", ".join(uf_recorte)
    paths = paths_ibge(cultura_slug)
    deflatores = calcula_deflatores(2024)

    out_dir = paths["relatorios"]
    out_dir.mkdir(parents=True, exist_ok=True)

    dados_json = {"titulo_recorte": titulo_recorte, "ufs": uf_recorte, "faixas": FAIXAS, "variaveis": []}
    partes = [
        f"# Relatório de variação percentual 2015→2024 — {cultura_slug} ({titulo_recorte})",
        "",
        "Municípios agrupados por faixa de variação percentual entre 2015 e 2024, por UF, para cada variável. "
        "Município sem produção em nenhum dos dois anos fica fora da contagem.",
        "",
        "**Definição das faixas:** \"Saiu\" = produzia em 2015 e zerou em 2024 (-100%). \"Novo produtor\" = não "
        "produzia em 2015 e passou a produzir em 2024 (% indefinido). As demais faixas usam "
        "`(2024-2015)/2015 * 100` para quem produziu nos dois anos.",
        "",
    ]

    for slug_var, titulo_var, unidade_var, deflacionar in VARIAVEIS:
        print(f"[{cultura_slug}] Processando {titulo_var.lower()}...")
        gdf = gpd.read_file(paths["geojson"] / f"{slug_var}.geojson")
        gdf = gdf[gdf["SIGLA_UF"].isin(uf_recorte)].copy()
        gdf["2015"] = gdf["2015"].astype(float)
        gdf["2024"] = gdf["2024"].astype(float)
        if deflacionar:
            gdf["2015"] *= deflatores[2015]
            gdf["2024"] *= deflatores[2024]

        gdf["faixa"] = gdf.apply(classifica_row, axis=1)
        gdf_valido = gdf[gdf["faixa"].notna()]
        contagem = gdf_valido.groupby(["SIGLA_UF", "faixa"]).size()
        tab = {(uf, faixa): contagem.get((uf, faixa), 0) for uf in uf_recorte for faixa in FAIXAS}

        partes += [f"## {titulo_var} ({unidade_var})", "", tabela_md(tab, uf_recorte), ""]
        dados_json["variaveis"].append({
            "titulo": titulo_var, "unidade": unidade_var,
            "linhas": [{"uf": uf, "contagens": [int(tab.get((uf, f), 0)) for f in FAIXAS]} for uf in uf_recorte],
        })

    out_md = out_dir / "faixas_2015_2024.md"
    out_json = out_dir / "faixas_2015_2024.json"
    out_md.write_text("\n".join(partes), encoding="utf-8")
    out_json.write_text(json.dumps(dados_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{cultura_slug}] Relatório salvo em: {out_md}")
    print(f"[{cultura_slug}] JSON salvo em: {out_json}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python 06_relatorio_faixas.py <cultura>")
        sys.exit(1)
    gera_relatorio(sys.argv[1])
