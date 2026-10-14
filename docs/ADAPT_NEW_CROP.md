# How to adapt the framework to a new crop

[🇧🇷 Português](COMO_ADAPTAR_NOVA_CULTURA.md) | 🇺🇸 English

This guide assumes you've already run the framework for citrus (the ready
example in `examples/citros/`) and want to apply it to another crop —
soybeans, coffee, sugarcane, corn, cotton, or any agricultural product
covered by IBGE/SIDRA.

## 1. Find the crop's name in SIDRA (IBGE)

Nothing is downloaded by hand: ingestion pulls the data from the SIDRA API. You
only need the **product name**; the framework finds the table and the product
code by itself from the table metadata:

- **Permanent crops** (citrus, coffee, grapes...): Table 1613.
- **Temporary crops** (soybeans, corn, sugarcane, cotton...): Table 1612.

Check the exact name at [sidra.ibge.gov.br/tabela/1613](https://sidra.ibge.gov.br/tabela/1613)
or [/1612](https://sidra.ibge.gov.br/tabela/1612) (e.g. "Café (em grão) Total",
not just "Café"). Matching ignores accents and case. If the name doesn't
exist, the error lists similar names.

Two differences for temporary crops: IBGE calls the area variable "planted
area" (instead of "area destined for harvest"), and map stages 04-06 were
validated for citrus.

## 2. Confirm the matching class in MapBiomas (optional)

1. Check the [legend of classes for the Collection you're using](https://brasil.mapbiomas.org/downloads/codigos-de-legenda/)
   (this framework was built with Collection 11).
2. Not every crop has its own class — smaller annual crops often fall into
   aggregated classes like "Other Temporary Crops" (41) or "Other Perennial
   Crops" (48), mixed in with other crops. In that case, the MapBiomas part
   of the framework won't separate your crop out of the class — either run
   the IBGE part only, or treat the MapBiomas result as an approximation of
   the aggregated class, not of the isolated crop.
3. Note the numeric class code (e.g. 39 for soybeans, 46 for coffee, 20 for
   sugarcane, 47 for citrus).
4. The MapBiomas raw file (`MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx`,
   downloaded from [brasil.mapbiomas.org/downloads/estatisticas](https://brasil.mapbiomas.org/downloads/estatisticas/))
   already covers **every** class — the same raw file works for any crop, no
   need to download it again per crop. Save it at `data/mapbiomas/brutos/`.

## 3. Register the crop in `config/culturas.yaml`

```yaml
culturas:
  soja:
    nome_sidra: "Soja (em grão)"
    mapbiomas_classe_codigo: 39
    mapbiomas_classe_nome: "Soja"
    uf_recorte: [MT, PR, RS, GO, MS, MG, BA]   # states where production concentrates
    ano_inicio_ibge: 1974                       # check SIDRA in case the series starts earlier/later
```

`uf_recorte` is only used in Part 2 of the framework (recent regional
cutout, IBGE) — pick the states where production concentrates, so the maps
aren't cluttered with all of Brazil greyed out. For MapBiomas the cutout is
automatic (states where the class has at least 1 record).

## 4. Run the pipeline

```bash
pip install -r requirements.txt
export PGPASSWORD=your_password     # PostGIS up and dimensions populated (see README)

python executar_pipeline.py soja
```

Or stage by stage (useful for debugging):

```bash
python src/ibge/01_ingerir_pam.py soja         # SIDRA API -> PostGIS (tabular.ibge_pam)
python src/ibge/01b_ingerir_lspa.py soja       # monthly LSPA by state, if the crop exists there
python src/ibge/02_exportar_do_banco.py soja   # CSVs the maps use
python src/ibge/03_gerar_geojson.py soja
python src/ibge/04_mapa_evolucao_historica.py soja
python src/ibge/05_mapa_divergencia_regional.py soja
python src/ibge/06_relatorio_faixas.py soja

python src/mapbiomas/01_extrair_classe.py soja     # needs the MapBiomas spreadsheet in data/mapbiomas/brutos/
python src/mapbiomas/02_gerar_geojson.py soja
python src/mapbiomas/03_mapa_evolucao_historica.py soja
python src/mapbiomas/04_mapa_divergencia.py soja
python src/mapbiomas/05_relatorio_faixas.py soja
```

Ingestion is idempotent: running again updates the values (IBGE revises the
previous year when it publishes a new one) instead of duplicating. To refresh
only the latest years: `python src/ibge/01_ingerir_pam.py soja --anos 2024,2025`.

## 5. Generate the .docx reports (optional)

```bash
cd relatorios
npm install
node build_docx.js ../data/ibge/relatorios/soja/faixas_2015_2024.json "Percent change 2015→2024 — Soybeans"
node build_docx.js ../data/mapbiomas/relatorios/soja/faixas_2015_2024.json "Percent change 2015→2024 — Soybeans (MapBiomas)"
```

## 6. Narrative synthesis (manual step)

The mechanical pipeline stops at the maps + range-classification tables.
Turning that into a final report with interpretation (like `examples/citros/`
shows) is a manual step — reading the numbers, deciding what's notable,
writing the narrative. The citrus study in this repository is the example
of what that final product can look like.
