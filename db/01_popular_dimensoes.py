# -*- coding: utf-8 -*-
"""
Popula as tabelas de dim (fontes, estados, municipios, cultura). Idempotente:
pode rodar de novo para atualizar nomes/geometrias sem duplicar.

Dois modos:
  - padrão: com geometria. Baixe do IBGE (Geociências > Malhas territoriais) e coloque em data/geo/:
      malha_municipios_brasil.shp   malha municipal (colunas CD_MUN, NM_MUN, AREA_KM2)
      BR_UF_2025.shp                malha de UFs (colunas CD_UF, NM_UF, SIGLA_UF, NM_REGIAO)
    Geometria gravada em SIRGAS 2000 (EPSG:4674), na resolução original da malha.
  - --sem-geometria: nada para baixar. Códigos e nomes vêm da API do SIDRA
    e a coluna geom fica vazia. Basta para coletar PAM e LSPA; rode o modo padrão depois
    (atualiza as mesmas linhas) quando precisar de mapas ou consultas espaciais.

Uso:
    PGPASSWORD=... python db/01_popular_dimensoes.py [--sem-geometria]
"""
import argparse
import os
import sys

import geopandas as gpd
from shapely.geometry import MultiPolygon
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "comum"))
import db  # noqa: E402
import sidra_api  # noqa: E402
from config import DATA  # noqa: E402

MALHA_MUNICIPIOS = DATA / "geo" / "malha_municipios_brasil.shp"
MALHA_UF = DATA / "geo" / "BR_UF_2025.shp"


def le_malha(caminho):
    if not caminho.exists():
        raise FileNotFoundError(f"{caminho} não encontrado — baixe a malha do IBGE e coloque nesse caminho (ver docstring).")
    gdf = gpd.read_file(caminho).to_crs(epsg=4674)
    gdf["geometry"] = gdf["geometry"].apply(lambda g: MultiPolygon([g]) if g.geom_type == "Polygon" else g)
    return gdf.rename_geometry("geom")


def popula_fontes(eng):
    with eng.begin() as conn:
        conn.execute(text("""
            INSERT INTO dim.fontes (nome, sigla, url, descricao) VALUES
            ('IBGE', 'IBGE', 'https://sidra.ibge.gov.br', 'Instituto Brasileiro de Geografia e Estatística - SIDRA (PAM Tabelas 1612/1613, LSPA Tabela 6588)'),
            ('MapBiomas', 'MapBiomas', 'https://brasil.mapbiomas.org', 'Coleção 11 de uso e cobertura da terra'),
            ('Receita Federal', 'RFB', 'https://basedosdados.org', 'Cadastro CNPJ, acessado via Base dos Dados / BigQuery')
            ON CONFLICT (nome) DO NOTHING;
        """))
    print("dim.fontes ok.")


def popula_estados(eng, id_fonte):
    uf = le_malha(MALHA_UF)[["CD_UF", "NM_UF", "SIGLA_UF", "NM_REGIAO", "geom"]]
    uf.columns = ["id_estado", "nome", "sigla", "regiao", "geom"]
    uf = uf.set_geometry("geom")
    uf.to_postgis("_stg_estados", eng, schema="dim", if_exists="replace", index=False)
    with eng.begin() as conn:
        conn.execute(text("""
            INSERT INTO dim.estados (id_estado, nome, sigla, regiao, geom, id_fonte, importado_em)
            SELECT id_estado, nome, sigla, regiao, geom, :fonte, CURRENT_DATE FROM dim._stg_estados
            ON CONFLICT (id_estado) DO UPDATE SET nome = EXCLUDED.nome, sigla = EXCLUDED.sigla,
                regiao = EXCLUDED.regiao, geom = EXCLUDED.geom, importado_em = EXCLUDED.importado_em;
            DROP TABLE dim._stg_estados;
        """), {"fonte": id_fonte})
    print(f"dim.estados ok ({len(uf)} UFs).")


def popula_municipios(eng, id_fonte):
    mun = le_malha(MALHA_MUNICIPIOS)[["CD_MUN", "NM_MUN", "AREA_KM2", "geom"]]
    mun.columns = ["id_municipio", "nome", "area_km2", "geom"]
    mun["id_municipio"] = mun["id_municipio"].astype(str)
    mun = mun.set_geometry("geom")
    mun.to_postgis("_stg_municipios", eng, schema="dim", if_exists="replace", index=False, chunksize=500)
    with eng.begin() as conn:
        conn.execute(text("""
            INSERT INTO dim.municipios (id_municipio, nome, id_estado, area_km2, geom, id_fonte, importado_em)
            SELECT id_municipio, nome, substr(id_municipio, 1, 2), area_km2, geom, :fonte, CURRENT_DATE FROM dim._stg_municipios
            ON CONFLICT (id_municipio) DO UPDATE SET nome = EXCLUDED.nome, area_km2 = EXCLUDED.area_km2,
                geom = EXCLUDED.geom, importado_em = EXCLUDED.importado_em;
            DROP TABLE dim._stg_municipios;
        """), {"fonte": id_fonte})
    print(f"dim.municipios ok ({len(mun)} municípios).")


def popula_cultura(eng, id_fonte_ibge, id_fonte_mapbiomas):
    """Hierarquia dos citros: o grupo 'citros' (classe 47 do MapBiomas, que não separa espécies)
    e as 3 espécies do IBGE. Outras culturas entram sozinhas pela ingestão (db.garante_cultura)."""
    with eng.begin() as conn:
        conn.execute(text("""
            INSERT INTO dim.cultura (slug, nome_exibicao, nivel, mapbiomas_classe_codigo, mapbiomas_classe_nome, id_fonte, importado_em)
            VALUES ('citros', 'Citros (grupo)', 'grupo', 47, 'Citrus', :mb, CURRENT_DATE)
            ON CONFLICT (slug) DO NOTHING;
        """), {"mb": id_fonte_mapbiomas})
        grupo = conn.execute(text("SELECT id_cultura FROM dim.cultura WHERE slug = 'citros'")).scalar_one()
        conn.execute(text("""
            INSERT INTO dim.cultura (slug, nome_exibicao, nivel, id_cultura_grupo, nome_sidra, id_fonte, importado_em) VALUES
            ('laranja', 'Laranja', 'especie', :g, 'Laranja', :ibge, CURRENT_DATE),
            ('limao', 'Limão', 'especie', :g, 'Limão', :ibge, CURRENT_DATE),
            ('tangerina', 'Tangerina', 'especie', :g, 'Tangerina', :ibge, CURRENT_DATE)
            ON CONFLICT (slug) DO UPDATE SET id_cultura_grupo = EXCLUDED.id_cultura_grupo;
        """), {"g": grupo, "ibge": id_fonte_ibge})
    print("dim.cultura ok (citros + laranja/limão/tangerina).")


def popula_territorios_api(eng, id_fonte):
    ufs, municipios = sidra_api.territorios()
    with eng.begin() as conn:
        conn.execute(text("""
            INSERT INTO dim.estados (id_estado, nome, sigla, regiao, id_fonte, importado_em)
            VALUES (:id, :nome, :sigla, :regiao, :fonte, CURRENT_DATE)
            ON CONFLICT (id_estado) DO UPDATE SET nome = EXCLUDED.nome, sigla = EXCLUDED.sigla, regiao = EXCLUDED.regiao
        """), [{**u, "fonte": id_fonte} for u in ufs])
        conn.execute(text("""
            INSERT INTO dim.municipios (id_municipio, nome, id_estado, id_fonte, importado_em)
            VALUES (:id, :nome, :id_estado, :fonte, CURRENT_DATE)
            ON CONFLICT (id_municipio) DO UPDATE SET nome = EXCLUDED.nome
        """), [{**m, "fonte": id_fonte} for m in municipios])
    print(f"dim.estados ok ({len(ufs)} UFs) e dim.municipios ok ({len(municipios)} municípios), sem geometria.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sem-geometria", action="store_true", help="carrega só códigos e nomes pela API do IBGE (nada para baixar)")
    args = parser.parse_args()

    eng = db.engine()
    popula_fontes(eng)
    with eng.begin() as conn:
        ibge, mapbiomas = db.id_fonte(conn, "IBGE"), db.id_fonte(conn, "MapBiomas")
    if args.sem_geometria:
        popula_territorios_api(eng, ibge)
    else:
        popula_estados(eng, ibge)
        popula_municipios(eng, ibge)
    popula_cultura(eng, ibge, mapbiomas)
    print("Dimensões populadas com sucesso.")
