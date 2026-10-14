-- Schema do banco framework_dados_cultivos.
-- Convenções: schemas vetorial/tabular/dim/resultados/catalogo; id_<dimensao> como PK
-- das tabelas de dim; id_fonte + importado_em em toda tabela de dim/tabular/resultados;
-- geometria (coluna geom) em SIRGAS 2000, EPSG:4674.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS vetorial;
CREATE SCHEMA IF NOT EXISTS tabular;
CREATE SCHEMA IF NOT EXISTS dim;
CREATE SCHEMA IF NOT EXISTS resultados;
CREATE SCHEMA IF NOT EXISTS catalogo;

-- ============================================================
-- DIM
-- ============================================================

CREATE TABLE dim.fontes (
    id_fonte    smallserial PRIMARY KEY,
    nome        text NOT NULL UNIQUE,
    sigla       text,
    url         text,
    descricao   text
);

CREATE TABLE dim.estados (
    id_estado   varchar(2) PRIMARY KEY,         -- código IBGE da UF (ex.: '35')
    nome        text NOT NULL,
    sigla       varchar(2) NOT NULL UNIQUE,
    regiao      text,
    geom        geometry(MultiPolygon, 4674),
    id_fonte    smallint REFERENCES dim.fontes(id_fonte),
    importado_em date
);
CREATE INDEX idx_estados_geom ON dim.estados USING GIST (geom);

CREATE TABLE dim.municipios (
    id_municipio varchar(7) PRIMARY KEY,         -- código IBGE do município
    nome         text NOT NULL,
    id_estado    varchar(2) REFERENCES dim.estados(id_estado),
    area_km2     numeric,
    geom         geometry(MultiPolygon, 4674),
    id_fonte     smallint REFERENCES dim.fontes(id_fonte),
    importado_em date
);
CREATE INDEX idx_municipios_geom ON dim.municipios USING GIST (geom);
CREATE INDEX idx_municipios_id_estado ON dim.municipios (id_estado);

CREATE TABLE dim.cultura (
    id_cultura              smallserial PRIMARY KEY,
    slug                    text NOT NULL UNIQUE,                 -- laranja, limao, tangerina, citros
    nome_exibicao           text NOT NULL,
    nivel                   text NOT NULL CHECK (nivel IN ('especie','grupo')),
    id_cultura_grupo        smallint REFERENCES dim.cultura(id_cultura),  -- NULL só na linha 'citros'
    nome_sidra              text,                                  -- só preenchido nas espécies
    mapbiomas_classe_codigo int,                                   -- só preenchido no grupo
    mapbiomas_classe_nome   text,                                  -- só preenchido no grupo
    id_fonte                smallint REFERENCES dim.fontes(id_fonte),
    importado_em            date
);

-- ============================================================
-- TABULAR  (nenhum dos 4 datasets tem geometria própria — ela mora
-- só nas dimensões e entra via id_municipio/id_estado)
-- ============================================================

CREATE TABLE tabular.ibge_pam (
    id           bigserial PRIMARY KEY,
    id_municipio varchar(7) REFERENCES dim.municipios(id_municipio),
    id_cultura   smallint REFERENCES dim.cultura(id_cultura),
    ano          int NOT NULL,
    variavel     text NOT NULL,     -- area_destinada_colheita, area_colhida, quantidade_produzida, rendimento_medio, valor_producao (+ variantes _pct)
    valor        numeric,
    unidade      text,              -- unidade real do valor (Hectares, Toneladas, Mil frutos, Mil Cruzeiros, Mil Reais, %...)
    id_fonte     smallint REFERENCES dim.fontes(id_fonte),
    importado_em date
);
CREATE INDEX idx_ibge_pam_municipio ON tabular.ibge_pam (id_municipio);
CREATE INDEX idx_ibge_pam_cultura_ano ON tabular.ibge_pam (id_cultura, ano);
CREATE UNIQUE INDEX uq_ibge_pam ON tabular.ibge_pam (id_municipio, id_cultura, ano, variavel);

CREATE TABLE tabular.ibge_lspa (
    id           bigserial PRIMARY KEY,
    id_estado    varchar(2) REFERENCES dim.estados(id_estado),
    id_cultura   smallint REFERENCES dim.cultura(id_cultura),
    ano          int NOT NULL,
    mes          int NOT NULL CHECK (mes BETWEEN 1 AND 12),
    variavel     text NOT NULL,     -- area_plantada, area_colhida, producao, rendimento_medio
    valor        numeric,
    unidade      text,
    id_fonte     smallint REFERENCES dim.fontes(id_fonte),
    importado_em date
);
CREATE INDEX idx_ibge_lspa_estado ON tabular.ibge_lspa (id_estado);
CREATE UNIQUE INDEX uq_ibge_lspa ON tabular.ibge_lspa (id_estado, id_cultura, ano, mes, variavel);

CREATE TABLE tabular.mapbiomas_cobertura (
    id           bigserial PRIMARY KEY,
    id_municipio varchar(7) REFERENCES dim.municipios(id_municipio),
    id_cultura   smallint REFERENCES dim.cultura(id_cultura),  -- sempre aponta pro grupo (citros)
    ano          int NOT NULL,
    area_ha      numeric,
    id_fonte     smallint REFERENCES dim.fontes(id_fonte),
    importado_em date
);
CREATE INDEX idx_mapbiomas_municipio ON tabular.mapbiomas_cobertura (id_municipio);
CREATE UNIQUE INDEX uq_mapbiomas ON tabular.mapbiomas_cobertura (id_municipio, id_cultura, ano);

CREATE TABLE tabular.receita_federal_cnpj (
    cnpj                        varchar(14) PRIMARY KEY,
    cnpj_basico                 varchar(8),
    razao_social                text,
    nome_fantasia                text,
    id_municipio                varchar(7) REFERENCES dim.municipios(id_municipio),
    id_cultura                  smallint REFERENCES dim.cultura(id_cultura),
    cnae_fiscal_principal        varchar(7),
    data_inicio_atividade        date,
    situacao_cadastral           text,
    capital_social                numeric,
    porte                        text,
    identificador_matriz_filial  text,
    id_fonte                     smallint REFERENCES dim.fontes(id_fonte),
    importado_em                 date
);
CREATE INDEX idx_cnpj_municipio ON tabular.receita_federal_cnpj (id_municipio);
CREATE INDEX idx_cnpj_data_inicio ON tabular.receita_federal_cnpj (data_inicio_atividade);

-- ============================================================
-- RESULTADOS  (calculado por nós, não importado pronto)
-- ============================================================

CREATE TABLE resultados.expansao_regional (
    id                          bigserial PRIMARY KEY,
    municipio_semente            varchar(7) REFERENCES dim.municipios(id_municipio),
    raio_km                      numeric NOT NULL,
    id_municipio                 varchar(7) REFERENCES dim.municipios(id_municipio),
    eh_semente                   boolean NOT NULL,
    distancia_km                 numeric,
    pam_area_colhida_ha_2015      numeric,
    pam_area_colhida_ha_2024      numeric,
    mapbiomas_area_ha_2015        numeric,
    mapbiomas_area_ha_2024        numeric,
    novos_cnpjs_2024_2026         int,
    calculado_em                  date
);
CREATE INDEX idx_expansao_semente ON resultados.expansao_regional (municipio_semente);

-- ============================================================
-- CATALOGO
-- ============================================================

CREATE TABLE catalogo.datasets (
    id               serial PRIMARY KEY,
    nome             text NOT NULL,
    tipo             text NOT NULL CHECK (tipo IN ('vetor','raster','tabular')),
    id_fonte         smallint REFERENCES dim.fontes(id_fonte),
    schema_tabela    text,
    caminho_arquivo  text,
    cobertura        geometry(Geometry, 4674),
    ano_referencia   int,
    data_importacao  date,
    licenca          text,
    observacoes      text
);
