# -*- coding: utf-8 -*-
"""
Cliente mínimo da API pública do SIDRA (IBGE), sem autenticação.

- Valores:    https://apisidra.ibge.gov.br/values/t/<tabela>/n<nivel>/all/v/<vars>/p/<periodos>/c<classif>/<categoria>
- Metadados:  https://servicodados.ibge.gov.br/api/v3/agregados/<tabela>/metadados

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
URL_METADADOS = "https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados"

_sessao = None
_cache_metadados = {}


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


def _get_json(url):
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
    url = (
        f"{URL_VALORES}/t/{tabela}/{nivel}/all/v/{','.join(variaveis)}"
        f"/p/{','.join(periodos)}/c{classificacao}/{categoria}"
    )
    try:
        dados = _get_json(url)
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


def metadados(tabela):
    if tabela not in _cache_metadados:
        _cache_metadados[tabela] = _get_json(URL_METADADOS.format(tabela=tabela))
    return _cache_metadados[tabela]


def periodo_inicial_final(tabela):
    p = metadados(tabela)["periodicidade"]
    return int(p["inicio"]), int(p["fim"])


def _normaliza(txt):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii").lower().strip()
    return re.sub(r"^[\d\.]+\s+", "", txt)  # tira prefixo numérico ("18 Laranja", "1.5 Aveia")


def categoria_id(tabela, classificacao, nome):
    """Acha o id da categoria `nome` dentro da classificação (ignora acento/caixa/prefixo numérico)."""
    for c in metadados(tabela)["classificacoes"]:
        if int(c["id"]) != int(classificacao):
            continue
        alvo = _normaliza(nome)
        achados = [x for x in c["categorias"] if _normaliza(x["nome"]) == alvo]
        if len(achados) == 1:
            return int(achados[0]["id"])
        if len(achados) > 1:
            raise ValueError(f'"{nome}" é ambíguo na tabela {tabela}: {[(x["id"], x["nome"]) for x in achados]}')
        parecidos = difflib.get_close_matches(alvo, [_normaliza(x["nome"]) for x in c["categorias"]], n=5, cutoff=0.5)
        raise LookupError(f'"{nome}" não existe na classificação {classificacao} da tabela {tabela}. Parecidos: {parecidos}')
    raise LookupError(f"Classificação {classificacao} não existe na tabela {tabela}.")


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
