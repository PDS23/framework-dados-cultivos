// Gera um .docx com as tabelas de faixas de variação percentual a partir do
// JSON produzido por src/ibge/06_relatorio_faixas.py ou
// src/mapbiomas/05_relatorio_faixas.py. Aceita os dois formatos:
//   - IBGE:      { titulo_recorte, ufs, faixas, variaveis: [...] }  (1 variável por vez, já filtrado por cultura)
//   - MapBiomas: { titulo_recorte, ufs, faixas, variavel: {...} }   (1 variável só)
//
// Uso: node build_docx.js <caminho-do-json> <titulo-do-relatorio>
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, BorderStyle, PageOrientation, VerticalAlign,
} = require("docx");

const [, , jsonPathArg, tituloArg] = process.argv;
if (!jsonPathArg) {
  console.error("Uso: node build_docx.js <caminho-do-json> [titulo-do-relatorio]");
  process.exit(1);
}
const JSON_PATH = path.resolve(jsonPathArg);
const OUT_PATH = JSON_PATH.replace(/\.json$/, ".docx");
const TITULO = tituloArg || "Variação percentual 2015 → 2024";

const dados = JSON.parse(fs.readFileSync(JSON_PATH, "utf-8"));
const variaveis = dados.variaveis || [dados.variavel]; // normaliza os 2 formatos pra uma lista só

const FAIXAS_ABREV = {
  "Saiu (-100%)": "Saiu",
  "Queda >50%": "Queda\n>50%",
  "Queda 20-50%": "Queda\n20-50%",
  "Queda <20%": "Queda\n<20%",
  "Estável (±5%)": "Estável\n(±5%)",
  "Alta <20%": "Alta\n<20%",
  "Alta 20-50%": "Alta\n20-50%",
  "Alta >50%": "Alta\n>50%",
  "Novo produtor": "Novo\nprodutor",
};

const COR_CABECALHO = "2F5597";
const COR_TOTAL = "EDEDED";

function celula(texto, { header = false, bold = false, shading = null, width, align = AlignmentType.CENTER } = {}) {
  const linhas = String(texto).split("\n");
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: shading ? { type: ShadingType.CLEAR, color: "auto", fill: shading } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 60, right: 60 },
    children: linhas.map(
      (linha) => new Paragraph({
        alignment: align,
        spacing: { after: 0 },
        children: [new TextRun({ text: linha, bold: bold || header, color: header ? "FFFFFF" : undefined, size: 15 })],
      })
    ),
  });
}

function tabelaFaixas(linhasDados, faixas) {
  const larguraUf = 900, larguraFaixa = 1230, larguraTotal = 950;
  const colWidths = [larguraUf, ...faixas.map(() => larguraFaixa), larguraTotal];

  const headerRow = new TableRow({
    tableHeader: true,
    children: [
      celula("UF", { header: true, width: larguraUf, shading: COR_CABECALHO }),
      ...faixas.map((f) => celula(FAIXAS_ABREV[f] || f, { header: true, width: larguraFaixa, shading: COR_CABECALHO })),
      celula("Total", { header: true, width: larguraTotal, shading: COR_CABECALHO }),
    ],
  });

  const bodyRows = linhasDados.map((linha) => {
    const total = linha.contagens.reduce((a, b) => a + b, 0);
    return new TableRow({
      children: [
        celula(linha.uf, { width: larguraUf, bold: true, align: AlignmentType.LEFT }),
        ...linha.contagens.map((c) => celula(c, { width: larguraFaixa })),
        celula(total, { width: larguraTotal, bold: true, shading: COR_TOTAL }),
      ],
    });
  });

  const totaisColuna = faixas.map((_, i) => linhasDados.reduce((soma, l) => soma + l.contagens[i], 0));
  const totalGeral = totaisColuna.reduce((a, b) => a + b, 0);
  const totalRow = new TableRow({
    children: [
      celula("Total", { width: larguraUf, bold: true, align: AlignmentType.LEFT, shading: COR_TOTAL }),
      ...totaisColuna.map((c) => celula(c, { width: larguraFaixa, bold: true, shading: COR_TOTAL })),
      celula(totalGeral, { width: larguraTotal, bold: true, shading: COR_TOTAL }),
    ],
  });

  return new Table({
    width: { size: colWidths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [headerRow, ...bodyRows, totalRow],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: "999999" },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: "999999" },
      left: { style: BorderStyle.SINGLE, size: 2, color: "999999" },
      right: { style: BorderStyle.SINGLE, size: 2, color: "999999" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "CCCCCC" },
      insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "CCCCCC" },
    },
  });
}

const children = [
  new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun({ text: TITULO, bold: true })] }),
  new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({
      text: `Municípios agrupados por faixa de variação percentual entre 2015 e 2024, por UF. Recorte: ${dados.titulo_recorte}. `
        + `Município sem valor em nenhum dos dois anos fica fora da contagem.`,
      italics: true, size: 20,
    })],
  }),
  new Paragraph({
    spacing: { after: 300 },
    children: [new TextRun({
      text: "Definição das faixas: \"Saiu\" = tinha valor em 2015 e zerou em 2024 (-100%). \"Novo produtor\" = não tinha "
        + "valor em 2015 e passou a ter em 2024 (% indefinido). As demais faixas usam (2024-2015)/2015 × 100 para "
        + "quem teve valor nos dois anos.",
      size: 20,
    })],
  }),
];

for (const v of variaveis) {
  children.push(
    new Paragraph({
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 200, after: 100 },
      children: [new TextRun({ text: `${v.titulo} (${v.unidade})` })],
    }),
    tabelaFaixas(v.linhas, dados.faixas)
  );
}

const doc = new Document({
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840, orientation: PageOrientation.LANDSCAPE },
        margin: { top: 720, bottom: 720, left: 720, right: 720 },
      },
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT_PATH, buffer);
  console.log("DOCX salvo em:", OUT_PATH);
});
