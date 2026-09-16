# framework-dados-cultivos

[![License: MIT](https://img.shields.io/github/license/PDS23/framework-dados-cultivos)](LICENSE)
[![CI](https://github.com/PDS23/framework-dados-cultivos/actions/workflows/ci.yml/badge.svg)](https://github.com/PDS23/framework-dados-cultivos/actions/workflows/ci.yml)

🇧🇷 Português | [🇺🇸 English](README.md)

Framework em Python para analisar a evolução espacial de qualquer cultura
agrícola brasileira cruzando duas fontes públicas de cobertura nacional:

- **IBGE** (SIDRA, Tabela 1613 — Produção Agrícola Municipal): levantamento
  declarado, por município, com série histórica desde 1974.
- **MapBiomas** (Coleção de uso e cobertura da terra): classificação por
  imagem de satélite, por município, com série desde 1985 — mas só nos
  estados onde a classe da cultura tem registro.

Nasceu de um estudo de caso completo sobre **citricultura** (laranja, limão
e tangerina) — ver `examples/citros/` para o resultado final (mapas,
tabelas e relatório consolidado). O código foi generalizado depois para
poder ser aplicado a qualquer outra cultura com cobertura nas duas fontes.

## Metodologia: duas janelas, duas escalas geográficas

| | Janela histórica | Janela recente (2015-2024) |
|---|---|---|
| **Escala** | Nacional (ou tão ampla quanto a fonte cobre) | Regional (onde a cultura se concentra) |
| **IBGE** | Desde 1974, Brasil inteiro | Recorte configurável por UF |
| **MapBiomas** | Desde 1985, estados com a classe | Mesmo recorte automático |

A ideia central: a série mais longa disponível em cada fonte é usada em
escala nacional, para dar contexto histórico; a comparação fina (por
variável, por município, com categorias de "novo produtor"/"saiu") é feita
só na janela recente e só na região onde a produção de fato existe — assim
os mapas não ficam poluídos com o país inteiro em cinza.

Cada produto de mapa segue o mesmo padrão visual: gráfico de linha indexado
a 100% no primeiro ano da janela, tabela de valores absolutos, e mapa(s)
coropléticos com escala de cor divergente (fria = queda, quente = alta).

## Estrutura do repositório

```
config/culturas.yaml       — cadastro de culturas (nome no SIDRA, classe MapBiomas, recorte regional)
src/comum/                 — utilitários compartilhados (paths, deflator IPCA, classificação em faixas)
src/ibge/01..06            — pipeline IBGE, na ordem
src/mapbiomas/01..05       — pipeline MapBiomas, na ordem
relatorios/build_docx.js   — gera .docx a partir das tabelas de faixas
docs/                      — guia de adaptação para nova cultura
examples/citros/           — resultado final do estudo de caso citros (mapas + relatório + apresentação)
data/                      — não versionado; populado localmente ao rodar o pipeline
```

## Como rodar (exemplo: reproduzir citros)

```bash
python -m venv .venv && source .venv/bin/activate   # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt

# 1. Baixe os dados brutos (ver docs/COMO_ADAPTAR_NOVA_CULTURA.md, seções 1-2)
#    e coloque em:
#      data/brutos/ibge/<slug-da-cultura>/*.xlsx   (ex.: laranja — o slug é a chave em config/culturas.yaml)
#      data/mapbiomas/brutos/MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx
#    Baixe também o shapefile de municípios do IBGE e coloque em:
#      data/geo/malha_municipios_brasil.shp

# 2. Rode o pipeline completo pra 1 cultura
python executar_pipeline.py laranja

# 3. (opcional) gere os .docx das tabelas de faixas
cd relatorios && npm install
node build_docx.js ../data/ibge/relatorios/laranja/faixas_2015_2024.json "Variação percentual — Laranja"
```

Saídas ficam em `data/ibge/mapas/laranja/`, `data/mapbiomas/mapas/laranja/`
e nos `relatorios/` correspondentes.

## Adaptar para outra cultura

Veja [`docs/COMO_ADAPTAR_NOVA_CULTURA.md`](docs/COMO_ADAPTAR_NOVA_CULTURA.md)
— passo a passo completo: achar a tabela certa no SIDRA, achar a classe
certa no MapBiomas, cadastrar em `config/culturas.yaml`, rodar. `culturas.yaml`
já vem com entradas de exemplo prontas para café, soja, cana-de-açúcar,
milho e algodão (config pronta; dados brutos não incluídos neste repositório).

## Limitações conhecidas

- As duas fontes medem coisas conceitualmente diferentes (declarado vs.
  detectado por satélite) — não são comparáveis em valor absoluto, só em
  direção/intensidade de tendência.
- O MapBiomas não garante classe própria para toda cultura — várias culturas
  anuais menores caem em classes agregadas ("Outras Lavouras Temporárias/
  Perenes"). Ver `docs/COMO_ADAPTAR_NOVA_CULTURA.md`.
- A malha municipal do IBGE muda ao longo do tempo (criação/fusão de
  municípios); o framework usa a malha mais recente para todos os anos, o
  que é uma simplificação comum nesse tipo de análise mas vale documentar.
- Valores monetários (IBGE) são deflacionados pelo IPCA (`src/comum/deflator_ipca.py`);
  a série pronta cobre 2015-2024 — estenda-a para outras janelas se precisar.

## Estudo de caso: citricultura brasileira

`examples/citros/` traz o material final do estudo original — mapas
selecionados, apresentação (`.pptx`) e relatório consolidado (`.docx`) — como
referência do que o pipeline produz e de como a síntese narrativa (etapa
manual, ver seção 6 do guia de adaptação) pode ser construída em cima dele.

O estudo também usou uma terceira fonte, o **Fundecitrus** (inventário de
árvores citrícolas, específico de laranja em SP/MG) — fora do escopo deste
framework genérico por não ter equivalente para outras culturas, mas
documentada no relatório do estudo de caso como enriquecimento opcional.

## Licença

MIT — ver [`LICENSE`](LICENSE).
