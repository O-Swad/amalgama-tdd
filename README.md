# Ship Fusion Simulator

Proyecto base para evaluar un modulo de fusion de datos de posicionamiento maritimo.

## Datos de ejemplo

Los CSV de `data/` describen un unico barco correlacionable con `vessel_id=VESSEL-001`:

- `ground_truth.csv`: verdad terreno cada 10 segundos entre `2026-05-07T10:00:00Z` y `2026-05-07T10:05:00Z`.
- `ais_readings.csv`: lecturas AIS cada 30 segundos con error pequeno de posicion.
- `radar_readings.csv`: lecturas Radar cada 10 segundos, desplazadas 5 segundos respecto a verdad terreno, con error mayor.

## Contrato del resultado de fusion

El simulador espera un CSV con esta cabecera:

```csv
timestamp_utc,vessel_id,latitude_deg,longitude_deg,sog_mps,cog_deg,source_count,covariance_x_m2,covariance_y_m2
```

## Pruebas TDD

Instala las dependencias de desarrollo en un entorno virtual local y ejecuta las pruebas:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

Las pruebas de `tests/test_dataset_quality.py` validan que los datasets son coherentes. Las pruebas de
`tests/test_fusion_contract.py` fijan el comportamiento que debe implementar el modulo de fusion en
`src/ship_fusion/fusion.py`.
