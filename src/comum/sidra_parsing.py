# -*- coding: utf-8 -*-
"""
Leitura de abas de planilhas exportadas do SIDRA (Tabela 1613 - PAM), que
mudam de formato dependendo de como a exportação foi feita:

- Exportação nacional multi-UF costuma ter ~5 linhas de cabeçalho (título,
  nome da variável, rótulos de coluna, linha de anos, linha de produto),
  1 coluna de valor por ano, sem coluna de unidade.
- Exportação recortada por UF (ex.: só Rio Grande do Sul) pode ter o mesmo
  layout de 5 linhas mas com uma coluna extra de UNIDADE logo depois de cada
  coluna de ano, e o nome do município já vem com a UF entre parênteses
  (ex.: "Água Santa (RS)").

Em vez de assumir um número fixo de linhas/colunas, detecta automaticamente:
a primeira linha de dados é a primeira cujo col[0] é "UF"/"MU"/"BR"; a linha
de anos é a linha anterior com mais células parecendo um ano de 4 dígitos
(colunas de unidade não têm esse padrão, então ficam de fora sozinhas).
"""
import re

NIVEIS_VALIDOS = ("BR", "UF", "MU")


def detecta_cabecalho(ws):
    """Retorna (todas_linhas, idx_primeira_linha_dado, col_ano) de uma aba.

    col_ano: {indice_da_coluna: "AAAA"} só para colunas de valor (não pega
    colunas de unidade, que não têm um token de 4 dígitos)."""
    todas_linhas = list(ws.iter_rows(values_only=True))
    idx_primeira_linha_dado = next(
        (i for i, row in enumerate(todas_linhas) if row and row[0] in NIVEIS_VALIDOS),
        None,
    )
    if idx_primeira_linha_dado is None:
        return todas_linhas, None, {}

    def conta_anos(row):
        if row is None:
            return 0
        n = 0
        for val in row:
            if val not in (None, ""):
                digits = "".join(ch for ch in str(val)[:4] if ch.isdigit())
                if len(digits) == 4:
                    n += 1
        return n

    candidatas = todas_linhas[:idx_primeira_linha_dado]
    year_row = max(candidatas, key=conta_anos) if candidatas else []

    col_ano = {}
    for ci, val in enumerate(year_row):
        if ci < 3:
            continue
        if val not in (None, ""):
            digits = "".join(ch for ch in str(val)[:4] if ch.isdigit())
            if len(digits) == 4:
                col_ano[ci] = digits

    return todas_linhas, idx_primeira_linha_dado, col_ano


_RE_UF_SUFIXO = re.compile(r"^(.*?)\s*\(([A-Z]{2})\)\s*$")


def separa_nome_uf(municipio_raw):
    """'Água Santa (RS)' -> ('Água Santa', 'RS'). Se não tiver o sufixo
    '(UF)', devolve (municipio_raw, None)."""
    if not isinstance(municipio_raw, str):
        return municipio_raw, None
    m = _RE_UF_SUFIXO.match(municipio_raw)
    if m:
        return m.group(1), m.group(2)
    return municipio_raw, None


def trata_valor(v):
    """'-' (zero absoluto do SIDRA) vira 0; '...' (não informado) vira None."""
    if v == "-":
        return 0
    if v in (None, "", "..."):
        return None
    return v
