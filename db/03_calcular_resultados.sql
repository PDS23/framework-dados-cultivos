-- Calcula resultados.expansao_regional via consulta espacial (ST_DWithin, em
-- geography, distâncias em metros): para cada município-semente, os municípios
-- dentro de raio_km, cruzando PAM (laranja, área colhida), MapBiomas (citros) e
-- novos CNPJs. Municípios-semente e raio ficam na CTE `sementes` abaixo.
-- Relatório/mapa: estudos/citros/relatorio_regioes_expansao.py

TRUNCATE resultados.expansao_regional;

WITH sementes (municipio_semente, raio_km) AS (
    VALUES
        ('2927002', 60.0),  -- Rio Real (BA)
        ('5210406', 60.0),  -- Itaberaí (GO)
        ('5209705', 60.0),  -- Hidrolândia (GO)
        ('5006309', 60.0)   -- Paranaíba (MS)
),
vizinhos AS (
    SELECT
        s.municipio_semente,
        s.raio_km,
        m.id_municipio,
        (m.id_municipio = s.municipio_semente) AS eh_semente,
        ROUND((ST_Distance(sem.geom::geography, m.geom::geography) / 1000)::numeric, 1) AS distancia_km
    FROM sementes s
    JOIN dim.municipios sem ON sem.id_municipio = s.municipio_semente
    JOIN dim.municipios m ON ST_DWithin(sem.geom::geography, m.geom::geography, s.raio_km * 1000)
),
pam AS (
    SELECT id_municipio,
           MAX(valor) FILTER (WHERE ano = 2015) AS pam_2015,
           MAX(valor) FILTER (WHERE ano = 2024) AS pam_2024
    FROM tabular.ibge_pam p
    JOIN dim.cultura c ON c.id_cultura = p.id_cultura
    WHERE c.slug = 'laranja' AND p.variavel = 'area_colhida' AND p.ano IN (2015, 2024)
    GROUP BY id_municipio
),
mb AS (
    SELECT id_municipio,
           MAX(area_ha) FILTER (WHERE ano = 2015) AS mb_2015,
           MAX(area_ha) FILTER (WHERE ano = 2024) AS mb_2024
    FROM tabular.mapbiomas_cobertura
    WHERE ano IN (2015, 2024)
    GROUP BY id_municipio
),
cnpj AS (
    SELECT id_municipio, COUNT(*) AS novos_cnpjs
    FROM tabular.receita_federal_cnpj
    GROUP BY id_municipio
)
INSERT INTO resultados.expansao_regional
    (municipio_semente, raio_km, id_municipio, eh_semente, distancia_km,
     pam_area_colhida_ha_2015, pam_area_colhida_ha_2024,
     mapbiomas_area_ha_2015, mapbiomas_area_ha_2024,
     novos_cnpjs_2024_2026, calculado_em)
SELECT
    v.municipio_semente, v.raio_km, v.id_municipio, v.eh_semente, v.distancia_km,
    COALESCE(pam.pam_2015, 0), COALESCE(pam.pam_2024, 0),
    COALESCE(mb.mb_2015, 0), COALESCE(mb.mb_2024, 0),
    COALESCE(cnpj.novos_cnpjs, 0), CURRENT_DATE
FROM vizinhos v
LEFT JOIN pam ON pam.id_municipio = v.id_municipio
LEFT JOIN mb ON mb.id_municipio = v.id_municipio
LEFT JOIN cnpj ON cnpj.id_municipio = v.id_municipio;

SELECT municipio_semente, COUNT(*) AS n_municipios, SUM(novos_cnpjs_2024_2026) AS total_cnpjs
FROM resultados.expansao_regional
GROUP BY municipio_semente
ORDER BY municipio_semente;
