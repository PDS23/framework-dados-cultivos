# -*- coding: utf-8 -*-
"""
Estágio 5/5 do pipeline MapBiomas: mesma lógica de faixas do IBGE, mas com
1 variável só (área) — recorte automático (estados com a classe).

Saída:
  data/mapbiomas/relatorios/<cultura>/faixas_2015_2024.md
  data/mapbiomas/relatorios/<cultura>/faixas_2015_2024.json

Uso: python src/mapbiomas/05_relatorio_faixas.py <cultura>
"""
import sys
import os
import json
import geopandas as gpd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
from config import paths_mapbiomas  # noqa: E402
from faixas import FAIXAS, classifica_row, tabela_md  # noqa: E402


def gera_relatorio(cultura_slug):
    paths = paths_mapbiomas(cultura_slug)
    gdf = gpd.read_file(paths["geojson"])
    gdf["2015"] = gdf["2015"].astype(float)
    gdf["2024"] = gdf["2024"].astype(float)

    ufs_recorte = sorted(gdf.loc[gdf["Teve_Prod"] == 1, "SIGLA_UF"].unique())
    gdf = gdf[gdf["SIGLA_UF"].isin(ufs_recorte)].copy()
    titulo_recorte = ", ".join(ufs_recorte)

    gdf["faixa"] = gdf.apply(classifica_row, axis=1)
    gdf_valido = gdf[gdf["faixa"].notna()]
    contagem = gdf_valido.groupby(["SIGLA_UF", "faixa"]).size()
    tab = {(uf, faixa): contagem.get((uf, faixa), 0) for uf in ufs_recorte for faixa in FAIXAS}

    partes = [
        f"# Relatório de variação percentual 2015→2024 — Área de {cultura_slug} (MapBiomas)",
        "",
        f"Municípios agrupados por faixa de variação percentual da área de {cultura_slug} entre 2015 e 2024, por UF. "
        f"Recorte automático: {titulo_recorte} (únicos estados com registro da classe no MapBiomas). Município sem "
        "área em nenhum dos dois anos fica fora da contagem.",
        "",
        "**Definição das faixas:** \"Saiu\" = tinha área em 2015 e zerou em 2024 (-100%). \"Novo produtor\" = não "
        "tinha área em 2015 e passou a ter em 2024 (% indefinido). As demais faixas usam "
        "`(2024-2015)/2015 * 100` para quem teve área nos dois anos.",
        "",
        f"### Área de {cultura_slug} (ha)",
        "",
        tabela_md(tab, ufs_recorte),
        "",
    ]

    dados_json = {
        "titulo_recorte": titulo_recorte,
        "ufs": ufs_recorte,
        "faixas": FAIXAS,
        "variavel": {
            "titulo": f"Área de {cultura_slug}", "unidade": "ha",
            "linhas": [{"uf": uf, "contagens": [int(tab.get((uf, f), 0)) for f in FAIXAS]} for uf in ufs_recorte],
        },
    }

    out_dir = paths["relatorios"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_md, out_json = out_dir / "faixas_2015_2024.md", out_dir / "faixas_2015_2024.json"
    out_md.write_text("\n".join(partes), encoding="utf-8")
    out_json.write_text(json.dumps(dados_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{cultura_slug}] Relatório salvo em: {out_md}")
    print(f"[{cultura_slug}] JSON salvo em: {out_json}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python 05_relatorio_faixas.py <cultura>")
        sys.exit(1)
    gera_relatorio(sys.argv[1])
