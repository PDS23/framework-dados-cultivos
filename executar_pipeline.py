# -*- coding: utf-8 -*-
"""
Orquestrador: roda o pipeline completo (IBGE e/ou MapBiomas) para 1 cultura,
na ordem correta. Equivalente a chamar cada estágio manualmente, na ordem
numerada dentro de src/ibge/ e src/mapbiomas/.

Uso:
    python executar_pipeline.py laranja                  # IBGE + MapBiomas
    python executar_pipeline.py laranja --so-ibge         # só IBGE
    python executar_pipeline.py laranja --so-mapbiomas    # só MapBiomas (precisa da malha já gerada por algum IBGE antes)

Cada estágio imprime o que está fazendo; se um estágio falhar (ex.: dado
bruto faltando), o script para e mostra o erro — rode o estágio anterior
que falta antes de tentar de novo.
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
        ("01_consolidar", "consolida"),
        ("02_dividir_csv", "divide"),
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
