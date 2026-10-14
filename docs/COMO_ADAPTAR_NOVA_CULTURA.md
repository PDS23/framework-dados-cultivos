# Como adaptar o framework para uma nova cultura

🇧🇷 Português | [🇺🇸 English](ADAPT_NEW_CROP.md)

Este guia parte do princípio de que você já rodou o framework para citros (o
exemplo pronto em `examples/citros/`) e quer aplicá-lo a outra cultura —
soja, café, cana, milho, algodão, ou qualquer produto agrícola coberto pelo
IBGE/SIDRA.

## 1. Descubra o nome da cultura no SIDRA (IBGE)

Nada é baixado à mão: a ingestão busca os dados na API do SIDRA. Você só
precisa do **nome do produto**, e o framework acha a tabela e o código sozinho
consultando os metadados:

- **Lavouras permanentes** (citros, café, uva...): Tabela 1613.
- **Lavouras temporárias** (soja, milho, cana, algodão...): Tabela 1612.

Confira o nome exato em [sidra.ibge.gov.br/tabela/1613](https://sidra.ibge.gov.br/tabela/1613)
ou [/1612](https://sidra.ibge.gov.br/tabela/1612) (ex.: "Café (em grão) Total",
não só "Café"). A comparação ignora acento e caixa. Se o nome não existir, o
erro lista nomes parecidos.

Duas diferenças das temporárias: o IBGE chama a variável de área de "área
plantada" (em vez de "área destinada à colheita") e os estágios de mapa 04-06
foram validados para citros.

## 2. Confirme a classe correspondente no MapBiomas (opcional)

1. Veja a [legenda de classes da Coleção usada](https://brasil.mapbiomas.org/downloads/codigos-de-legenda/)
   (este framework foi construído com a Coleção 11).
2. Nem toda cultura tem classe própria — culturas anuais menores costumam
   cair em classes agregadas como "Outras Lavouras Temporárias" (41) ou
   "Outras Lavouras Perenes" (48), misturadas com outras culturas. Nesse
   caso, a parte MapBiomas do framework não separa sua cultura dentro da
   classe — rode só a parte IBGE, ou trate o resultado do MapBiomas como uma
   aproximação da classe agregada, não da cultura isolada.
3. Anote o código numérico da classe (ex.: 39 para soja, 46 para café, 20
   para cana, 47 para citros).
4. O arquivo bruto do MapBiomas (`MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx`,
   baixado em [brasil.mapbiomas.org/downloads/estatisticas](https://brasil.mapbiomas.org/downloads/estatisticas/)) já
   cobre **todas** as classes — o mesmo arquivo bruto serve para qualquer
   cultura, não precisa baixar de novo por cultura. Salve-o em
   `data/mapbiomas/brutos/`.

## 3. Cadastre a cultura em `config/culturas.yaml`

```yaml
culturas:
  soja:
    nome_sidra: "Soja (em grão)"
    mapbiomas_classe_codigo: 39
    mapbiomas_classe_nome: "Soja"
    uf_recorte: [MT, PR, RS, GO, MS, MG, BA]   # estados onde a produção se concentra
    ano_inicio_ibge: 1974                       # confira no SIDRA se a série começa antes/depois
```

`uf_recorte` é só usado na Parte 2 do framework (recorte regional recente,
IBGE) — escolha os estados que concentram a produção, para os mapas não
ficarem poluídos com o Brasil inteiro em cinza. Para o MapBiomas o recorte
é automático (estados onde a classe tem pelo menos 1 registro).

## 4. Rode o pipeline

```bash
pip install -r requirements.txt
export PGPASSWORD=sua_senha     # PostGIS no ar e dimensões populadas (ver README)

python executar_pipeline.py soja
```

Ou estágio por estágio (útil para depurar):

```bash
python src/ibge/01_ingerir_pam.py soja         # API do SIDRA -> PostGIS (tabular.ibge_pam)
python src/ibge/01b_ingerir_lspa.py soja       # LSPA mensal por UF, se a cultura existir lá
python src/ibge/02_exportar_do_banco.py soja   # CSVs que os mapas usam
python src/ibge/03_gerar_geojson.py soja
python src/ibge/04_mapa_evolucao_historica.py soja
python src/ibge/05_mapa_divergencia_regional.py soja
python src/ibge/06_relatorio_faixas.py soja

python src/mapbiomas/01_extrair_classe.py soja     # precisa da planilha do MapBiomas em data/mapbiomas/brutos/
python src/mapbiomas/02_gerar_geojson.py soja
python src/mapbiomas/03_mapa_evolucao_historica.py soja
python src/mapbiomas/04_mapa_divergencia.py soja
python src/mapbiomas/05_relatorio_faixas.py soja
```

A ingestão é idempotente: rodar de novo atualiza os valores (o IBGE revisa o
ano anterior quando publica o novo) em vez de duplicar. Para refrescar só os
últimos anos: `python src/ibge/01_ingerir_pam.py soja --anos 2024,2025`.

## 5. Gere os relatórios em .docx (opcional)

```bash
cd relatorios
npm install
node build_docx.js ../data/ibge/relatorios/soja/faixas_2015_2024.json "Variação percentual 2015→2024 — Soja"
node build_docx.js ../data/mapbiomas/relatorios/soja/faixas_2015_2024.json "Variação percentual 2015→2024 — Soja (MapBiomas)"
```

## 6. Síntese narrativa (etapa manual)

O pipeline mecânico termina nos mapas + tabelas de faixas. Transformar isso
num relatório final com interpretação (como `examples/citros/` mostra) é uma
etapa manual — ler os números, decidir o que é notável, escrever a
narrativa. O estudo de citros neste repositório é o exemplo de como esse
produto final pode ficar.
