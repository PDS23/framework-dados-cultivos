# -*- coding: utf-8 -*-
"""
Orquestrador: roda o pipeline completo (IBGE e/ou MapBiomas) para 1 cultura,
na ordem correta. Equivalente a chamar cada estágio manualmente, na ordem
numerada dentro de src/ibge/ e src/mapbiomas/.

Uso:
    python executar_pipeline.py laranja                  # IBGE + MapBiomas
    python executar_pipeline.py laranja --so-ibge         # só IBGE
    python executar_pipeline.py laranja --so-mapbiomas    # só MapBiomas (precisa da malha já gerada por algum IBGE antes)

O estágio IBGE 01 busca os dados direto da API do SIDRA e grava no PostGIS
(precisa de PGPASSWORD no ambiente e do schema de db/schema.sql já criado);
o 02 reexporta do banco os CSVs que os mapas usam.

Cada estágio imprime o que está fazendo; se um estágio falhar, o script para
e mostra o erro — corrija e rode de novo (a ingestão é idempotente).
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "comum"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "ibge"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "mapbiomas"))


def roda_ibge(cultura_slug):
    import importlib
    print(f"\n=== IBGE — {cultura_slug} ===")
    etapas = [
        ("01_ingerir_pam", "ingere"),
        ("01b_ingerir_lspa", "ingere"),
        ("02_exportar_do_banco", "exporta"),
        ("03_gerar_geojson", "gera_geojsons"),
        ("04_mapa_evolucao_historica", "gera_mapa"),
        ("05_mapa_divergencia_regional", "gera_mapa"),
        ("06_relatorio_faixas", "gera_relatorio"),
    ]
    for modulo, funcao in etapas:
        print(f"\n--- {modulo} ---")
        mod = importlib.import_module(modulo)
        getattr(mod, funcao)(cultura_slug)


def roda_mapbiomas(cultura_slug):
    import importlib
    print(f"\n=== MapBiomas — {cultura_slug} ===")
    etapas = [
        ("01_extrair_classe", "extrai"),
        ("02_gerar_geojson", "gera_geojson"),
        ("03_mapa_evolucao_historica", "gera_mapa"),
        ("04_mapa_divergencia", "gera_mapa"),
        ("05_relatorio_faixas", "gera_relatorio"),
    ]
    for modulo, funcao in etapas:
        print(f"\n--- {modulo} ---")
        mod = importlib.import_module(modulo)
        getattr(mod, funcao)(cultura_slug)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Roda o pipeline completo para 1 cultura.")
    parser.add_argument("cultura", help="slug da cultura em config/culturas.yaml (ex.: laranja)")
    parser.add_argument("--so-ibge", action="store_true", help="roda só o pipeline IBGE")
    parser.add_argument("--so-mapbiomas", action="store_true", help="roda só o pipeline MapBiomas")
    args = parser.parse_args()

    if args.so_mapbiomas:
        roda_mapbiomas(args.cultura)
    elif args.so_ibge:
        roda_ibge(args.cultura)
    else:
        roda_ibge(args.cultura)
        roda_mapbiomas(args.cultura)

    print(f"\nPipeline concluído para '{args.cultura}'. Saídas em data/ibge/ e data/mapbiomas/.")
