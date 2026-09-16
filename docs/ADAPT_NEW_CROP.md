# How to adapt the framework to a new crop

[🇧🇷 Português](COMO_ADAPTAR_NOVA_CULTURA.md) | 🇺🇸 English

This guide assumes you've already run the framework for citrus (the ready
example in `examples/citros/`) and want to apply it to another crop —
soybeans, coffee, sugarcane, corn, cotton, or any agricultural product
covered by IBGE/SIDRA.

## 1. Confirm the crop exists in SIDRA (IBGE)

1. Go to [SIDRA Table 1613](https://sidra.ibge.gov.br/tabela/1613) —
   Municipal Agricultural Production (Permanent and Temporary Crops).
2. Under "Produto das lavouras permanentes/temporárias" (crop product),
   check the exact name of the crop (e.g. "Café (em grão) Total", not just
   "Café").
3. Build the query with:
   - **Variables**: the 8 standard ones (Area destined for harvest,
     Harvested area, Quantity produced, Average yield, Production value —
     with and without percentage of the total).
   - **Territorial level**: Brazil + State (UF) + Municipality (all 3
     together in one export per level, or split them if SIDRA complains
     about the size).
   - **Crop product**: only the crop you want.
   - **Year**: the whole available period (1974 onward).
4. Export as xlsx ("Salvar" → planilha). If the full period doesn't fit in
   one export, download it in chunks (e.g. 20 years at a time) — stage 1 of
   the pipeline merges multiple files automatically.
5. Save the file(s) at `data/brutos/ibge/<crop-slug>/`.

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

# municipal mesh (runs once, shared across all crops — see README)
# runs automatically inside IBGE's first stage, 03

python executar_pipeline.py soja
```

Or stage by stage (useful for debugging a specific problem):

```bash
python src/ibge/01_consolidar.py soja
python src/ibge/02_dividir_csv.py soja
python src/ibge/03_gerar_geojson.py soja
python src/ibge/04_mapa_evolucao_historica.py soja
python src/ibge/05_mapa_divergencia_regional.py soja
python src/ibge/06_relatorio_faixas.py soja

python src/mapbiomas/01_extrair_classe.py soja
python src/mapbiomas/02_gerar_geojson.py soja
python src/mapbiomas/03_mapa_evolucao_historica.py soja
python src/mapbiomas/04_mapa_divergencia.py soja
python src/mapbiomas/05_relatorio_faixas.py soja
```

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
