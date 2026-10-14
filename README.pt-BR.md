# framework-dados-cultivos

[![License: MIT](https://img.shields.io/github/license/PDS23/framework-dados-cultivos)](LICENSE)
[![CI](https://github.com/PDS23/framework-dados-cultivos/actions/workflows/ci.yml/badge.svg)](https://github.com/PDS23/framework-dados-cultivos/actions/workflows/ci.yml)

🇧🇷 Português | [🇺🇸 English](README.md)

Framework em Python + PostGIS para analisar a evolução espacial de qualquer
cultura agrícola brasileira cruzando fontes públicas de cobertura nacional:

- **IBGE / SIDRA** — Produção Agrícola Municipal (PAM, tabelas 1612/1613, por
  município, desde 1974) e Levantamento Sistemático da Produção Agrícola
  (LSPA, tabela 6588, mensal, por UF). Buscados **direto da API do SIDRA**,
  sem download manual.
- **MapBiomas** — classificação de uso e cobertura da terra por satélite
  (Coleção 11, por município, desde 1985), só nos estados onde a classe da
  cultura tem registro.
- **Receita Federal (CNPJ)** — novos estabelecimentos por CNAE, indicador
  antecedente de onde uma cultura está atraindo investimento (por enquanto só
  no estudo de citros).

Nasceu de um estudo de caso completo sobre **citricultura** (laranja, limão e
tangerina) — ver `examples/citros/`. O código é guiado por configuração: outra
cultura são algumas linhas em `config/culturas.yaml`.

## Como funciona

```
API do SIDRA ──► PostGIS (tabular.*) ──► export CSV ──► mapas e relatórios de faixas
xlsx do MapBiomas (manual, por enquanto) ──► CSV ──► mapas e relatórios de faixas
```

Tudo cai num banco PostGIS com um padrão único (`db/schema.sql`): `dim` (fontes,
estados, municípios com geometria, culturas), `tabular` (uma tabela por fonte,
chaveada pelo código IBGE), `resultados` (o que a gente calcula, ex.: buffers
espaciais) e `catalogo` (registro dos datasets). A geometria fica só nas
dimensões e entra pelo código IBGE.

As culturas formam uma hierarquia (`dim.cultura`): o MapBiomas tem uma única
classe "Citrus", então o grupo `citros` fica acima das espécies do IBGE
`laranja`/`limao`/`tangerina`.

## Metodologia: duas janelas, duas escalas geográficas

| | Janela histórica | Janela recente (2015-2024) |
|---|---|---|
| **Escala** | Nacional (tão longe quanto cada fonte permite) | Regional (onde a cultura se concentra) |
| **IBGE** | Desde 1974, Brasil inteiro | Recorte configurável por UF |
| **MapBiomas** | Desde 1985, estados com a classe | Mesmo recorte, detectado automaticamente |

A série mais longa de cada fonte é usada em escala nacional, para dar
contexto; a comparação fina (por variável, por município, com categorias de
"novo produtor"/"saiu") é feita só na janela recente e só onde a produção
existe, para os mapas não ficarem com o país inteiro em cinza.

## Estrutura do repositório

```
config/culturas.yaml   — cadastro de culturas (nome no SIDRA, classe MapBiomas, recorte regional)
db/                    — schema.sql, carregadores de dimensões/fatos, resultados espaciais (SQL)
src/comum/             — config, acesso ao banco, cliente da API do SIDRA, deflator IPCA, classificação em faixas
src/ibge/              — pipeline IBGE: 01 ingestão (API→PostGIS), 02 exportação, 03-06 mapas/relatórios
src/mapbiomas/         — pipeline MapBiomas 01..05
estudos/citros/        — scripts do estudo de citros (mapa de CNPJs, regiões de expansão, gpkg da LSPA)
relatorios/            — build_docx.js (tabelas de faixas → .docx)
docs/                  — guia de adaptação para nova cultura
examples/citros/       — resultado final do estudo de citros (mapas + relatório + apresentação)
docker-compose.yml     — PostGIS local
data/                  — não versionado; populado ao rodar o pipeline
```

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate   # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt

# 1. PostGIS (qualquer PostGIS serve; este é o mais rápido)
export PGPASSWORD=escolha_uma_senha                # PowerShell: $env:PGPASSWORD = "..."
docker compose up -d                               # cria o banco e o db/schema.sql

# 2. Coleta dos dados do IBGE - nada para baixar à mão
python db/01_popular_dimensoes.py --sem-geometria  # códigos e nomes de UFs/municípios, pela API do IBGE
python src/ibge/01_ingerir_pam.py laranja          # PAM, de 1974 ao último ano     -> tabular.ibge_pam
python src/ibge/01b_ingerir_lspa.py laranja        # LSPA, mensal por UF            -> tabular.ibge_lspa
```

Só isso reproduz a coleta do SIDRA. Rodar de novo é seguro (upsert);
`--anos 2024,2025` e `--desde 202501` atualizam só os dados recentes. A cultura
vem de `config/culturas.yaml`.

Para mapas, relatórios e consultas espaciais é preciso também a geometria:

```bash
# 3. Malhas do IBGE extraídas em data/geo/ (Geociências > Malhas territoriais):
#      malha_municipios_brasil.shp   (municípios)    BR_UF_2025.shp   (UFs)
python db/01_popular_dimensoes.py                  # o mesmo comando, sem a flag: adiciona a geometria
python executar_pipeline.py laranja --so-ibge      # SIDRA -> PostGIS -> mapas/relatórios
python executar_pipeline.py laranja                # idem, mais o MapBiomas
```

Os estágios do MapBiomas ainda precisam da planilha de estatísticas municipais em
`data/mapbiomas/brutos/MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx`
(de [brasil.mapbiomas.org/downloads/estatisticas](https://brasil.mapbiomas.org/downloads/estatisticas/));
automatizar isso é o próximo passo. A conexão vem de `PGPASSWORD` (obrigatória)
e, opcionalmente, `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`. Se a porta 5432
estiver ocupada, use `PG_HOST_PORT` no `docker compose` e `PGPORT` nos scripts.

Relatórios `.docx` de faixas (opcional):

```bash
cd relatorios && npm install
node build_docx.js ../data/ibge/relatorios/laranja/faixas_2015_2024.json "Variação percentual — Laranja"
```

## Adaptar para outra cultura

Veja [`docs/COMO_ADAPTAR_NOVA_CULTURA.md`](docs/COMO_ADAPTAR_NOVA_CULTURA.md):
cadastre a cultura em `config/culturas.yaml` e rode o pipeline. A ingestão
aceita lavouras permanentes (tabela 1613) e temporárias (tabela 1612); os
estágios de mapa foram validados para citros, e as temporárias trazem "área
plantada" onde citros tem "área destinada à colheita" (ver o guia).

## Limitações conhecidas

- As fontes medem coisas diferentes (declarado vs. detectado por satélite):
  não são comparáveis em valor absoluto, só em direção/intensidade de tendência.
- O MapBiomas não tem classe para toda cultura; várias caem em classes
  agregadas ("Outras Lavouras Temporárias/Perenes").
- Antes de 2001 o IBGE expressava a produção de frutíferas em mil frutos (não
  toneladas), embora a API rotule como toneladas; culturas que declaram
  `quebra_unidade_quantidade_ate` no `culturas.yaml` ganham a unidade correta
  em `tabular.ibge_pam.unidade`. Valores monetários também mudam de moeda ao
  longo da série (guardada por linha) — use o deflator IPCA só de 2015 em diante.
- A malha municipal do IBGE muda ao longo do tempo; o framework usa a mais
  recente para todos os anos.
- O LSPA é preliminar e revisado todo mês; o PAM é o fechamento anual.
- Os dados de CNPJ vêm da Base dos Dados (BigQuery); a cobertura gratuita vai
  até uma data de corte, as fotografias seguintes são pagas.

## Estudo de caso: citricultura brasileira

`examples/citros/` traz o material final do estudo original (mapas,
apresentação, relatório consolidado). `estudos/citros/` tem as análises da
segunda rodada, feitas em cima do banco: mapa de novas empresas por município,
regiões de expansão ao redor de municípios-semente (`ST_DWithin` no PostGIS),
LSPA por UF. O estudo também usou o **Fundecitrus** (inventário de árvores
citrícolas de SP/MG), fora do escopo deste framework genérico.

## Licença

MIT — ver [`LICENSE`](LICENSE).
