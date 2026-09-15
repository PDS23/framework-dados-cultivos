# -*- coding: utf-8 -*-
"""
Calcula o deflator IPCA (IBGE) para trazer valores nominais de qualquer ano
a poder de compra de dezembro do ano-base, e devolve um dict {ano: fator}.

Fonte: IPCA - Variação mensal (%), série 433 do SGS/Banco Central (dado
calculado pelo IBGE). https://api.bcb.gov.br/dados/serie/bcdata.sgs.433

Série pronta cobre 2015-2024 (janela usada no framework). Para analisar
outra janela de anos, adicione os meses correspondentes em IPCA_MENSAL.
"""

IPCA_MENSAL = {
    2015: [1.24, 1.22, 1.32, 0.71, 0.74, 0.79, 0.62, 0.22, 0.54, 0.82, 1.01, 0.96],
    2016: [1.27, 0.90, 0.43, 0.61, 0.78, 0.35, 0.52, 0.44, 0.08, 0.26, 0.18, 0.30],
    2017: [0.38, 0.33, 0.25, 0.14, 0.31, -0.23, 0.24, 0.19, 0.16, 0.42, 0.28, 0.44],
    2018: [0.29, 0.32, 0.09, 0.22, 0.40, 1.26, 0.33, -0.09, 0.48, 0.45, -0.21, 0.15],
    2019: [0.32, 0.43, 0.75, 0.57, 0.13, 0.01, 0.19, 0.11, -0.04, 0.10, 0.51, 1.15],
    2020: [0.21, 0.25, 0.07, -0.31, -0.38, 0.26, 0.36, 0.24, 0.64, 0.86, 0.89, 1.35],
    2021: [0.25, 0.86, 0.93, 0.31, 0.83, 0.53, 0.96, 0.87, 1.16, 1.25, 0.95, 0.73],
    2022: [0.54, 1.01, 1.62, 1.06, 0.47, 0.67, -0.68, -0.36, -0.29, 0.59, 0.41, 0.62],
    2023: [0.53, 0.84, 0.71, 0.61, 0.23, -0.08, 0.12, 0.23, 0.26, 0.24, 0.28, 0.56],
    2024: [0.42, 0.83, 0.16, 0.38, 0.46, 0.21, 0.38, -0.02, 0.44, 0.56, 0.39, 0.52],
}


def calcula_deflatores(ano_base=2024):
    """Retorna {ano: fator_multiplicador} para converter valor nominal do
    ano em reais de dezembro do ano_base (índice acumulado dez/ano_base
    dividido pelo índice acumulado dez/ano)."""
    indice = 1.0
    indice_dezembro = {}
    for ano in sorted(IPCA_MENSAL):
        for variacao in IPCA_MENSAL[ano]:
            indice *= (1 + variacao / 100)
        indice_dezembro[ano] = indice

    indice_base = indice_dezembro[ano_base]
    return {ano: indice_base / indice_dezembro[ano] for ano in indice_dezembro}


if __name__ == "__main__":
    deflatores = calcula_deflatores(2024)
    print("Deflatores IPCA (multiplicar valor nominal por isso para obter R$ de dez/2024):")
    for ano, fator in deflatores.items():
        print(f"  {ano}: x{fator:.4f}  (IPCA acumulado desde então: {(fator - 1) * 100:.1f}%)")
