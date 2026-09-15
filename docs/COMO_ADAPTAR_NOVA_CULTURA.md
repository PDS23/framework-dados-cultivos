# Como adaptar o framework para uma nova cultura

Este guia parte do princípio de que você já rodou o framework para citros (o
exemplo pronto em `examples/citros/`) e quer aplicá-lo a outra cultura —
soja, café, cana, milho, algodão, ou qualquer produto agrícola coberto pelo
IBGE/SIDRA.

## 1. Confirme que a cultura existe no SIDRA (IBGE)

1. Acesse a [Tabela 1613 do SIDRA](https://sidra.ibge.gov.br/tabela/1613) —
   Produção Agrícola Municipal (Lavoura Permanente e Temporária).
2. Em "Produto das lavouras permanentes/temporárias", confira o nome exato
   da cultura (ex.: "Café (em grão) Total", não só "Café").
3. Monte a consulta com:
   - **Variáveis**: as 8 padrão (Área destinada à colheita, Área colhida,
     Quantidade produzida, Rendimento médio, Valor da produção — com e sem
     percentual do total).
   - **Nível territorial**: Brasil + Unidade da Federação + Município (as 3
     juntas, numa exportação por nível, ou separe se o SIDRA reclamar do
     tamanho).
   - **Produto das lavouras**: só a cultura desejada.
   - **Ano**: todo o período disponível (1974 em diante).
4. Exporte em xlsx ("Salvar" → planilha). Se o período completo não couber
   numa exportação só, baixe em pedaços (por ex. de 20 em 20 anos) — o
   estágio 1 do pipeline funde múltiplos arquivos automaticamente.
5. Salve o(s) arquivo(s) em `data/brutos/ibge/<slug-da-cultura>/`.

## 2. Confirme a classe correspondente no MapBiomas (opcional)

1. Veja a [legenda de classes da Coleção usada](https://mapbiomas.org/codigos-de-legenda)
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
   baixado em [mapbiomas.org/download](https://mapbiomas.org/download)) já
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

# malha municipal (1x só, compartilhada por todas as culturas — ver README)
# roda automaticamente dentro do primeiro estágio 03 do IBGE

python executar_pipeline.py soja
```

Ou estágio por estágio (útil para depurar um problema específico):

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
