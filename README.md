# framework-dados-cultivos

[![License: MIT](https://img.shields.io/github/license/PDS23/framework-dados-cultivos)](LICENSE)
[![CI](https://github.com/PDS23/framework-dados-cultivos/actions/workflows/ci.yml/badge.svg)](https://github.com/PDS23/framework-dados-cultivos/actions/workflows/ci.yml)

🇺🇸 English | [🇧🇷 Português](README.pt-BR.md)

Python framework for analyzing the spatial evolution of any Brazilian
agricultural crop by cross-referencing two public, nationwide data sources:

- **IBGE** (SIDRA, Table 1613 — Municipal Agricultural Production): declared
  survey data, by municipality, with a historical series back to 1974.
- **MapBiomas** (land use and land cover collection): satellite-imagery
  classification, by municipality, with a series back to 1985 — but only in
  the states where the crop's class has any record.

Born out of a complete case study on **Brazilian citrus growing** (orange,
lemon and tangerine) — see `examples/citros/` for the final output (maps,
tables, and consolidated report). The code was later generalized so it can
be applied to any other crop covered by both sources.

## Methodology: two windows, two geographic scales

| | Historical window | Recent window (2015-2024) |
|---|---|---|
| **Scale** | National (as far back as each source allows) | Regional (where the crop actually concentrates) |
| **IBGE** | Since 1974, all of Brazil | Configurable state-level cutout |
| **MapBiomas** | Since 1985, states with the class | Same cutout, detected automatically |

Core idea: the longest series available in each source is used at national
scale, to give historical context; the fine-grained comparison (per
variable, per municipality, with "new producer"/"exited" categories) is only
done in the recent window and only in the region where production actually
exists — so the maps aren't cluttered with the whole country greyed out.

Every map product follows the same visual pattern: a line chart indexed to
100% at the first year of the window, a table of absolute values, and
choropleth map(s) with a diverging color scale (cool = decline, warm =
growth).

## Repository structure

```
config/culturas.yaml       — crop registry (SIDRA name, MapBiomas class, regional cutout)
src/comum/                 — shared utilities (paths, IPCA deflator, range classification)
src/ibge/01..06            — IBGE pipeline, in order
src/mapbiomas/01..05       — MapBiomas pipeline, in order
relatorios/build_docx.js   — generates .docx from the range-classification tables
docs/                      — guide for adapting the framework to a new crop
examples/citros/           — final output of the citrus case study (maps + report + slide deck)
data/                      — not version-controlled; populated locally when the pipeline runs
```

## How to run it (example: reproducing the citrus study)

```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# 1. Download the raw data (see docs/COMO_ADAPTAR_NOVA_CULTURA.md, sections 1-2,
#    currently in Portuguese) and place it at:
#      data/brutos/ibge/laranja/*.xlsx
#      data/mapbiomas/brutos/MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx
#    Also download the IBGE municipal shapefile and place it at:
#      data/geo/malha_municipios_brasil.shp

# 2. Run the full pipeline for 1 crop
python executar_pipeline.py laranja

# 3. (optional) generate the .docx range-classification reports
cd relatorios && npm install
node build_docx.js ../data/ibge/relatorios/laranja/faixas_2015_2024.json "Percent change — Orange"
```

Outputs land in `data/ibge/mapas/laranja/`, `data/mapbiomas/mapas/laranja/`,
and the corresponding `relatorios/` folders.

## Adapting to another crop

See [`docs/COMO_ADAPTAR_NOVA_CULTURA.md`](docs/COMO_ADAPTAR_NOVA_CULTURA.md)
(currently Portuguese-only) for the full walkthrough: finding the right
SIDRA table, finding the right MapBiomas class, registering it in
`config/culturas.yaml`, and running the pipeline. `culturas.yaml` already
ships with ready-made example entries for coffee, soybeans, sugarcane, corn
and cotton (config only; raw data not included in this repository).

## Known limitations

- The two sources measure conceptually different things (declared vs.
  satellite-detected) — not comparable in absolute value, only in the
  direction/intensity of the trend.
- MapBiomas doesn't guarantee a dedicated class for every crop — several
  smaller annual crops fall into aggregated classes ("Other Temporary/
  Perennial Crops"). See the adaptation guide.
- The IBGE municipal mesh changes over time (municipalities are created or
  merged); the framework uses the most recent mesh for all years, a common
  simplification in this kind of analysis but worth documenting.
- Monetary values (IBGE) are deflated using IPCA (`src/comum/deflator_ipca.py`);
  the ready-made series covers 2015-2024 — extend it for other windows if needed.

## Case study: Brazilian citrus growing

`examples/citros/` contains the final material from the original study —
selected maps, a slide deck (`.pptx`), and a consolidated report (`.docx`) —
as a reference for what the pipeline produces and how the narrative synthesis
(a manual step, see section 6 of the adaptation guide) can be built on top of it.

The study also drew on a third source, **Fundecitrus** (a citrus-tree
inventory specific to orange growing in SP/MG) — out of scope for this
generic framework since it has no equivalent for other crops, but documented
in the case-study report as an optional enrichment.

## License

MIT — see [`LICENSE`](LICENSE).
