# -*- coding: utf-8 -*-
"""
Classificação de variação percentual 2015->2024 em faixas, usada tanto nos
mapas de divergência quanto nos relatórios de faixas por UF. Lógica única,
compartilhada entre IBGE e MapBiomas (antes duplicada em cada script).

  Saiu (-100%)      -> tinha valor em v_inicial, zerou em v_final
  Queda >50%        -> pct < -50
  Queda 20-50%      -> -50 <= pct < -20
  Queda <20%        -> -20 <= pct < -5
  Estável (+-5%)    -> -5 <= pct <= 5
  Alta <20%         -> 5 < pct <= 20
  Alta 20-50%       -> 20 < pct <= 50
  Alta >50%         -> pct > 50
  Novo produtor     -> não tinha valor em v_inicial, passou a ter em v_final
  None              -> sem valor nos dois anos (fora da contagem)
"""

FAIXAS = [
    "Saiu (-100%)",
    "Queda >50%",
    "Queda 20-50%",
    "Queda <20%",
    "Estável (±5%)",
    "Alta <20%",
    "Alta 20-50%",
    "Alta >50%",
    "Novo produtor",
]


def classifica(v_inicial, v_final):
    """Classifica um par (valor no ano inicial, valor no ano final) numa das FAIXAS, ou None."""
    if v_inicial == 0 and v_final == 0:
        return None
    if v_inicial == 0 and v_final > 0:
        return "Novo produtor"
    if v_inicial > 0 and v_final == 0:
        return "Saiu (-100%)"
    pct = (v_final - v_inicial) / v_inicial * 100
    if pct < -50:
        return "Queda >50%"
    if pct < -20:
        return "Queda 20-50%"
    if pct < -5:
        return "Queda <20%"
    if pct <= 5:
        return "Estável (±5%)"
    if pct <= 20:
        return "Alta <20%"
    if pct <= 50:
        return "Alta 20-50%"
    return "Alta >50%"


def classifica_row(row, col_inicial="2015", col_final="2024"):
    """Wrapper para usar com DataFrame.apply(axis=1)."""
    return classifica(row[col_inicial], row[col_final])


def tabela_md(tab, ufs, faixas=FAIXAS):
    """tab: dict {(uf, faixa): contagem}. Devolve uma tabela Markdown com totais por linha e coluna."""
    linhas = ["| UF | " + " | ".join(faixas) + " | Total |", "|---|" + "---|" * (len(faixas) + 1)]
    for uf in ufs:
        contagens = [int(tab.get((uf, f), 0)) for f in faixas]
        total = sum(contagens)
        linhas.append(f"| {uf} | " + " | ".join(str(c) for c in contagens) + f" | {total} |")
    totais_col = [int(sum(tab.get((uf, f), 0) for uf in ufs)) for f in faixas]
    linhas.append("| **Total** | " + " | ".join(f"**{c}**" for c in totais_col) + f" | **{sum(totais_col)}** |")
    return "\n".join(linhas)
