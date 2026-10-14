# -*- coding: utf-8 -*-
"""
Cliente mínimo da API pública do SIDRA (IBGE), sem autenticação.

    https://apisidra.ibge.gov.br/values/t/<tabela>/n<nivel>/all/v/<vars>/p/<periodos>/c<classif>/<categoria>

Só o host de valores é usado, de propósito: o host de metadados
(servicodados.ibge.gov.br) chegou a servir um certificado sem o intermediário
da cadeia, o que quebra clientes Python (curl e navegadores se viram, o Python
não). Os códigos de produto e os períodos disponíveis saem da própria API de
valores (consulta com categoria "all").

A API recusa requisições com mais de 50.000 valores (erro 400 "excedeu o
limite"); `valores()` divide a consulta automaticamente (primeiro por
variável, depois por período) quando isso acontece.
"""
import difflib
import re
import unicodedata

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL_VALORES = "https://apisidra.ibge.gov.br/values"

_sessao = None
_cache_tabela = {}


class LimiteExcedido(Exception):
    pass


def sessao():
    global _sessao
    if _sessao is None:
        s = requests.Session()
        retry = Retry(total=5, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
        s.mount("https://", HTTPAdapter(max_retries=retry))
        _sessao = s
    return _sessao


def _get_json(caminho):
    url = f"{URL_VALORES}/{caminho}"
    r = sessao().get(url, timeout=180)
    if r.status_code == 400 and "excedeu o limite" in r.text:
        raise LimiteExcedido(r.text)
    if r.status_code >= 400:
        raise RuntimeError(f"SIDRA respondeu {r.status_code}: {r.text[:300]} ({url})")
    return r.json()


def valores(tabela, nivel, variaveis, periodos, classificacao, categoria):
    """Retorna uma lista de registros (dicts com chaves D1C, D2C, D3C, MN, V, ...), sem a linha de cabeçalho.

    nivel: ex. "n6" (município) ou "n3" (UF). variaveis/periodos: listas de str/int."""
    variaveis = [str(v) for v in variaveis]
    periodos = [str(p) for p in periodos]
    caminho = (
        f"t/{tabela}/{nivel}/all/v/{','.join(variaveis)}"
        f"/p/{','.join(periodos)}/c{classificacao}/{categoria}"
    )
    try:
        dados = _get_json(caminho)
    except LimiteExcedido:
        if len(variaveis) > 1:
            meio = len(variaveis) // 2
            return (valores(tabela, nivel, variaveis[:meio], periodos, classificacao, categoria)
                    + valores(tabela, nivel, variaveis[meio:], periodos, classificacao, categoria))
        if len(periodos) > 1:
            meio = len(periodos) // 2
            return (valores(tabela, nivel, variaveis, periodos[:meio], classificacao, categoria)
                    + valores(tabela, nivel, variaveis, periodos[meio:], classificacao, categoria))
        raise
    return dados[1:]


def _produtos_e_periodos(tabela, classificacao):
    """Uma consulta (Brasil, área colhida, todos os períodos, todos os produtos) devolve os
    produtos {codigo: nome} e os períodos em que cada um aparece {codigo: [periodos]}."""
    chave = (tabela, classificacao)
    if chave not in _cache_tabela:
        linhas = _get_json(f"t/{tabela}/n1/all/v/216/p/all/c{classificacao}/all")[1:]
        produtos, periodos = {}, {}
        for r in linhas:
            produtos[int(r["D4C"])] = r["D4N"]
            periodos.setdefault(int(r["D4C"]), set()).add(r["D3C"])
        _cache_tabela[chave] = (produtos, {k: sorted(v) for k, v in periodos.items()})
    return _cache_tabela[chave]


def _normaliza(txt):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii").lower().strip()
    return re.sub(r"^[\d\.]+\s+", "", txt)  # tira prefixo numérico ("18 Laranja", "1.5 Aveia")


def categoria_id(tabela, classificacao, nome):
    """Acha o código do produto `nome` na classificação (ignora acento, caixa e prefixo numérico)."""
    produtos, _ = _produtos_e_periodos(tabela, classificacao)
    alvo = _normaliza(nome)
    achados = [cod for cod, n in produtos.items() if _normaliza(n) == alvo]
    if len(achados) == 1:
        return achados[0]
    if len(achados) > 1:
        raise ValueError(f'"{nome}" é ambíguo na tabela {tabela}: {[(c, produtos[c]) for c in achados]}')
    parecidos = difflib.get_close_matches(alvo, [_normaliza(n) for n in produtos.values()], n=5, cutoff=0.5)
    raise LookupError(f'"{nome}" não existe na classificação {classificacao} da tabela {tabela}. Parecidos: {parecidos}')


def periodos(tabela, classificacao, categoria):
    """Períodos (str; AAAA ou AAAAMM) em que o produto aparece na tabela."""
    return _produtos_e_periodos(tabela, classificacao)[1][int(categoria)]


def territorios():
    """Códigos e nomes de UFs e municípios, pela tabela 6579 (estimativas de população, que lista
    todos os municípios). Devolve (ufs, municipios), listas de dicts: ufs com id/nome/sigla/regiao,
    municipios com id/nome/id_estado. A sigla vem do sufixo " - UF" do nome do município e a
    região do 1º dígito do código da UF (1 Norte, 2 Nordeste, 3 Sudeste, 4 Sul, 5 Centro-Oeste)."""
    regioes = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"}
    muns = _get_json("t/6579/n6/all/v/9324/p/last")[1:]
    ufs = _get_json("t/6579/n3/all/v/9324/p/last")[1:]
    municipios, sigla_por_uf = [], {}
    for m in muns:
        nome, sigla = m["D1N"].rsplit(" - ", 1)
        municipios.append({"id": m["D1C"], "nome": nome, "id_estado": m["D1C"][:2]})
        sigla_por_uf[m["D1C"][:2]] = sigla
    estados = [{"id": u["D1C"], "nome": u["D1N"], "sigla": sigla_por_uf[u["D1C"]], "regiao": regioes[u["D1C"][0]]} for u in ufs]
    return estados, municipios


def parse_valor(v):
    """'-' (zero absoluto) vira 0.0; '...', '..', 'X' e vazio (sem dado/inibido) viram None."""
    v = str(v).strip()
    if v == "-":
        return 0.0
    if v in ("", "...", "..", "X"):
        return None
    try:
        return float(v)
    except ValueError:
        return None
