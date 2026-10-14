# -*- coding: utf-8 -*-
"""
Acesso ao PostGIS. A conexão vem de variáveis de ambiente (nada de senha em
arquivo): PGPASSWORD (obrigatória) e, opcionais, PGHOST (localhost), PGPORT
(5432), PGUSER (postgres), PGDATABASE (framework_dados_cultivos).
"""
import os

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


def engine():
    senha = os.environ.get("PGPASSWORD")
    if not senha:
        raise RuntimeError("Defina a variável de ambiente PGPASSWORD (e, se preciso, PGHOST/PGPORT/PGUSER/PGDATABASE).")
    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("PGUSER", "postgres"),
        password=senha,
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        database=os.environ.get("PGDATABASE", "framework_dados_cultivos"),
    )
    return create_engine(url)


def id_fonte(conn, nome):
    return conn.execute(text("SELECT id_fonte FROM dim.fontes WHERE nome = :n"), {"n": nome}).scalar_one()


def garante_cultura(conn, slug, nome_sidra, id_fonte_ibge):
    """Devolve o id_cultura da espécie `slug`, criando a linha em dim.cultura se ainda não existir."""
    conn.execute(
        text("""
            INSERT INTO dim.cultura (slug, nome_exibicao, nivel, nome_sidra, id_fonte, importado_em)
            VALUES (:slug, :nome, 'especie', :nome, :fonte, CURRENT_DATE)
            ON CONFLICT (slug) DO NOTHING
        """),
        {"slug": slug, "nome": nome_sidra, "fonte": id_fonte_ibge},
    )
    return conn.execute(text("SELECT id_cultura FROM dim.cultura WHERE slug = :s"), {"s": slug}).scalar_one()


def upsert(conn, df, schema, tabela, chave, atualizar, tamanho_lote=5000):
    """INSERT ... ON CONFLICT (chave) DO UPDATE em lote. Reprocessar o mesmo período atualiza (ex.: revisões do IBGE) em vez de duplicar."""
    if df.empty:
        return 0
    df = df.drop_duplicates(subset=chave, keep="last")
    colunas = list(df.columns)
    sql = (
        f"INSERT INTO {schema}.{tabela} ({', '.join(colunas)}) VALUES %s "
        f"ON CONFLICT ({', '.join(chave)}) DO UPDATE SET "
        + ", ".join(f"{c} = EXCLUDED.{c}" for c in atualizar)
    )
    linhas = df.astype(object).where(df.notna(), None).values.tolist()
    with conn.connection.cursor() as cur:
        execute_values(cur, sql, linhas, page_size=tamanho_lote)
    return len(linhas)


def registra_dataset(conn, nome, nome_fonte, schema_tabela, ano_referencia=None, licenca=None, observacoes=None):
    """Registra o dataset em catalogo.datasets (1 linha por nome) e atualiza a data da última importação."""
    conn.execute(
        text("""
            INSERT INTO catalogo.datasets (nome, tipo, id_fonte, schema_tabela, ano_referencia, data_importacao, licenca, observacoes)
            SELECT :nome, 'tabular', (SELECT id_fonte FROM dim.fontes WHERE nome = :fonte), :tabela, :ano, CURRENT_DATE, :lic, :obs
            WHERE NOT EXISTS (SELECT 1 FROM catalogo.datasets WHERE nome = :nome)
        """),
        {"nome": nome, "fonte": nome_fonte, "tabela": schema_tabela, "ano": ano_referencia, "lic": licenca, "obs": observacoes},
    )
    conn.execute(text("UPDATE catalogo.datasets SET data_importacao = CURRENT_DATE WHERE nome = :nome"), {"nome": nome})
