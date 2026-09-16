# -*- coding: utf-8 -*-
"""
Estágio 1/5 do pipeline MapBiomas: extrai a série histórica de área de uma
classe de cobertura/uso da terra (código em config/culturas.yaml ->
mapbiomas_classe_codigo) por município, a partir do arquivo bruto de
Coleção do MapBiomas (cobertura e uso da terra, biomas/estados/municípios).

Entrada: data/mapbiomas/brutos/MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx
(baixe em https://brasil.mapbiomas.org/downloads/estatisticas/, Coleção 11,
planilha "biome, state, municipality"), aba COVERAGE_11, formato longo (1 linha por município x
classe), colunas y<ano>... em hectares.

Um município pode aparecer em mais de uma linha quando seu território cruza
mais de um bioma — nesse caso a área da classe vem dividida por bioma e é
SOMADA por município antes de exportar.

Saída: data/mapbiomas/processado/<cultura>.csv (Codigo, Nome, Estado,
Teve_Prod, <ano1>...<anoN>).

Uso: python src/mapbiomas/01_extrair_classe.py <cultura>
"""
import sys
import os
import openpyxl
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "comum"))
from config import paths_mapbiomas, cultura as get_cultura  # noqa: E402

ANO_INICIO_COLECAO_11 = 1985
ANO_FIM = 2024  # descarta y2025 em diante; framework usa 2024 como último ano em todo lugar


def extrai(cultura_slug):
    cfg = get_cultura(cultura_slug)
    classe_codigo = cfg.get("mapbiomas_classe_codigo")
    if classe_codigo is None:
        raise ValueError(
            f'Cultura "{cultura_slug}" não tem mapbiomas_classe_codigo definido em config/culturas.yaml '
            f"— essa cultura não tem classe própria no MapBiomas, pule a parte MapBiomas para ela."
        )
    paths = paths_mapbiomas(cultura_slug)
    xlsx_path = paths["bruto_xlsx"]
    if not xlsx_path.exists():
        raise FileNotFoundError(f"{xlsx_path} não encontrado — baixe o arquivo bruto do MapBiomas primeiro.")

    anos = [str(a) for a in range(ANO_INICIO_COLECAO_11, ANO_FIM + 1)]

    print(f"[{cultura_slug}] Lendo {xlsx_path} (aba COVERAGE_11, classe {classe_codigo})...")
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb["COVERAGE_11"]
    linhas = ws.iter_rows(values_only=True)
    header = next(linhas)
    idx = {nome: i for i, nome in enumerate(header)}
    i_geocode, i_municipio, i_uf, i_classe = idx["geocode"], idx["municipality"], idx["state"], idx["class"]
    i_ano_ini = idx[f"y{ANO_INICIO_COLECAO_11}"]

    registros = []
    for row in linhas:
        if row[i_classe] != classe_codigo:
            continue
        valores = row[i_ano_ini: i_ano_ini + len(anos)]
        registros.append({
            "Codigo": str(row[i_geocode]), "Nome": row[i_municipio], "Estado": row[i_uf],
            **{ano: (v if v is not None else 0.0) for ano, v in zip(anos, valores)},
        })
    wb.close()

    if not registros:
        raise ValueError(f"Nenhum registro da classe {classe_codigo} encontrado — confira o código no bruto.")

    df = pd.DataFrame(registros)
    n_antes = df["Codigo"].nunique()
    df = df.groupby(["Codigo", "Nome", "Estado"], as_index=False)[anos].sum()
    print(f"[{cultura_slug}] Municípios (código único): {len(df)} (agrupados de {n_antes} linhas município×bioma)")

    df["Teve_Prod"] = (df[anos] > 0).any(axis=1).astype(int)
    df = df[["Codigo", "Nome", "Estado", "Teve_Prod"] + anos].sort_values("Codigo").reset_index(drop=True)

    out_path = paths["processado"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    estados_com_dado = sorted(df.loc[df["Teve_Prod"] == 1, "Estado"].unique())
    print(f"[{cultura_slug}] Salvo em: {out_path}")
    print(f"[{cultura_slug}] Estados com registro da classe: {', '.join(estados_com_dado)}")
    print(f"[{cultura_slug}] Área total em {ANO_FIM} (Brasil): {df[str(ANO_FIM)].sum():,.0f} ha")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python 01_extrair_classe.py <cultura>")
        sys.exit(1)
    extrai(sys.argv[1])
