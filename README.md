# framework-dados-cultivos

[![License: MIT](https://img.shields.io/github/license/PDS23/framework-dados-cultivos)](LICENSE)
[![CI](https://github.com/PDS23/framework-dados-cultivos/actions/workflows/ci.yml/badge.svg)](https://github.com/PDS23/framework-dados-cultivos/actions/workflows/ci.yml)

🇺🇸 English | [🇧🇷 Português](README.pt-BR.md)

Python + PostGIS framework to analyze the spatial evolution of any Brazilian
agricultural crop by cross-referencing public, nationwide data sources:

- **IBGE / SIDRA** — Municipal Agricultural Production (PAM, tables 1612/1613,
  by municipality, since 1974) and the monthly Systematic Survey of
  Agricultural Production (LSPA, table 6588, by state). Fetched **directly
  from the SIDRA API** — no manual download.
- **MapBiomas** — satellite land-cover classification (Collection 11, by
  municipality, since 1985), only where the crop's class has any record.
- **Receita Federal (CNPJ)** — new establishments by CNAE, a leading indicator
  of where a crop is attracting investment (citrus study only, for now).

Born out of a complete case study on **Brazilian citrus growing** (orange,
lemon and tangerine) — see `examples/citros/`. The code is config-driven, so
other crops are a few lines in `config/culturas.yaml`.

## How it works

```
SIDRA API ──► PostGIS (tabular.*) ──► CSV export ──► maps & range reports
MapBiomas xlsx (manual, for now) ──► CSV ──► maps & range reports
```

Everything lands in a PostGIS database whose layout follows one convention
(`db/schema.sql`): `dim` (sources, states, municipalities with geometry,
crops), `tabular` (one table per source, keyed by IBGE code), `resultados`
(what we compute, e.g. spatial buffers) and `catalogo` (dataset registry).
Geometry lives only in the dimensions and is joined by IBGE code.

Crops are modelled as a hierarchy (`dim.cultura`): MapBiomas has a single
"Citrus" class, so the group `citros` sits above the IBGE species
`laranja`/`limao`/`tangerina`.

## Methodology: two windows, two geographic scales

| | Historical window | Recent window (2015-2024) |
|---|---|---|
| **Scale** | National (as far back as each source allows) | Regional (where the crop actually concentrates) |
| **IBGE** | Since 1974, all of Brazil | Configurable state-level cutout |
| **MapBiomas** | Since 1985, states with the class | Same cutout, detected automatically |

The longest series of each source is used at national scale for context; the
fine-grained comparison (per variable, per municipality, with "new
producer"/"exited" categories) is done only in the recent window and only
where production exists, so maps aren't cluttered with a greyed-out country.

## Repository structure

```
config/culturas.yaml   — crop registry (SIDRA name, MapBiomas class, regional cutout)
db/                    — schema.sql, dimension/fact loaders, spatial results (SQL)
src/comum/             — config, DB access, SIDRA API client, IPCA deflator, range classification
src/ibge/              — IBGE pipeline: 01 ingest (API→PostGIS), 02 export, 03-06 maps/reports
src/mapbiomas/         — MapBiomas pipeline 01..05
estudos/citros/        — scripts specific to the citrus study (CNPJ map, expansion regions, LSPA gpkg)
relatorios/            — build_docx.js (range-classification tables → .docx)
docs/                  — guide for adapting to a new crop
examples/citros/       — final output of the citrus study (maps + report + slide deck)
docker-compose.yml     — local PostGIS
data/                  — not version-controlled; filled when the pipeline runs
```

## How to run

```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# 1. PostGIS (any PostGIS works; this one is the quickest)
export PGPASSWORD=choose_a_password                # PowerShell: $env:PGPASSWORD = "..."
docker compose up -d                               # creates the database and db/schema.sql

# 2. IBGE meshes, extracted into data/geo/ (Geociências > Malhas territoriais):
#      malha_municipios_brasil.shp   (municipalities)    BR_UF_2025.shp   (states)
python db/01_popular_dimensoes.py

# 3. Full pipeline for 1 crop: SIDRA API -> PostGIS -> maps/reports
python executar_pipeline.py laranja
```

The IBGE stages need nothing downloaded by hand. The MapBiomas stages still
need the municipal statistics spreadsheet at
`data/mapbiomas/brutos/MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx`
(from [brasil.mapbiomas.org/downloads/estatisticas](https://brasil.mapbiomas.org/downloads/estatisticas/));
automating it is next. Use `--so-ibge` to skip them. Connection settings come
from `PGPASSWORD` (required) and optionally `PGHOST`, `PGPORT`, `PGUSER`,
`PGDATABASE`.

`.docx` range reports (optional):

```bash
cd relatorios && npm install
node build_docx.js ../data/ibge/relatorios/laranja/faixas_2015_2024.json "Percent change — Orange"
```

## Adapting to another crop

See [`docs/ADAPT_NEW_CROP.md`](docs/ADAPT_NEW_CROP.md): register the crop in
`config/culturas.yaml` and run the pipeline. Permanent crops (table 1613) and
temporary crops (table 1612) are both supported by the ingestion; the map
stages were validated for citrus, and temporary crops report "planted area"
where citrus has "area destined for harvest" (see the guide).

## Known limitations

- The sources measure different things (declared vs. satellite-detected): not
  comparable in absolute value, only in the direction/intensity of the trend.
- MapBiomas doesn't have a class for every crop; several fall into aggregated
  classes ("Other Temporary/Perennial Crops").
- Before 2001, IBGE expressed fruit production in thousand fruits (not
  tonnes) although the API labels it as tonnes; crops declaring
  `quebra_unidade_quantidade_ate` in `culturas.yaml` get the correct unit
  stored in `tabular.ibge_pam.unidade`. Monetary values also change currency
  over the series (stored per row too) — use the IPCA deflator only for 2015+.
- The IBGE municipal mesh changes over time; the framework uses the most
  recent one for all years.
- LSPA is preliminary and revised monthly; PAM is the final annual figure.
- CNPJ data comes from Base dos Dados (BigQuery); its free tier covers
  snapshots up to a cutoff date, later ones are paid.

## Case study: Brazilian citrus growing

`examples/citros/` holds the final material of the original study (maps, slide
deck, consolidated report). `estudos/citros/` has the second-round analyses
built on the database: new-company map by municipality, expansion regions
around chosen seed municipalities (PostGIS `ST_DWithin`), LSPA by state. The
study also drew on **Fundecitrus** (citrus-tree inventory for SP/MG), out of
scope for this generic framework.

## License

MIT — see [`LICENSE`](LICENSE).
