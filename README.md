# Ship Fusion Simulator

Executable TDD specification for evaluating a maritime positioning data-fusion module. This project intentionally keeps the fusion functions as stubs: the algorithm is expected to be implemented by another project or package that satisfies the tests.

## Sample Data

The CSV files in `data/` describe a single correlatable vessel with `vessel_id=VESSEL-001`:

- `ground_truth.csv`: ground-truth positions every 10 seconds between `2026-05-07T10:00:00Z` and `2026-05-07T10:05:00Z`.
- `ais_readings.csv`: AIS readings every 30 seconds with small position error and vessel attributes.
- `radar_readings.csv`: Radar readings every 10 seconds, offset by 5 seconds from ground truth, with larger position error.

## Fusion Requirements

The tests encode these requirements:

- Radar has priority over AIS for estimated position.
- The estimated `latitude_deg` and `longitude_deg` must be copied from the correlated Radar measurement.
- Radar and AIS measurements must be correlated to identify readings that belong to the same physical vessel.
- Correlation must not rely solely on sensor identifiers such as `vessel_id`, because AIS and Radar may use different ids for the same vessel and matching ids may still describe different objects.
- Correlation must use temporal and geometric consistency, or an equivalent non-id-only association strategy.
- Geometric correlation is validated with the standard GeographicLib WGS84 geodesic distance, which accounts for Earth oblateness.
- A correlated AIS/Radar pair must stay within `x = 130 m` and `20 s` in the provided scenarios.
- AIS data enriches the Radar-based estimate with vessel attributes such as `mmsi`, `sog_mps`, `cog_deg`, `heading_deg`, `navigation_status`, and `position_accuracy`.
- AIS readings from other vessels must not enrich the selected Radar track.

## Known Examples

The TDD contract includes golden CSV fixtures in `tests/fixtures/`:

- `known_correlation_ais.csv`: AIS readings with realistic ids, a close valid candidate, and a misleading id match.
- `known_correlation_radar.csv`: Radar readings to be correlated.
- `expected_correlations.csv`: known valid AIS/Radar association results, including max time and WGS84 geodesic distance thresholds.
- `expected_fusion_result.csv`: known valid final fusion output for the fixture inputs.

Implementations should pass these examples exactly before being evaluated against the larger sample dataset.

## Fusion Result Contract

The simulator expects a CSV file with this header:

```csv
timestamp_utc,vessel_id,latitude_deg,longitude_deg,sog_mps,cog_deg,heading_deg,mmsi,navigation_status,position_accuracy,radar_id,track_id,range_m,bearing_deg,range_rate_mps,source_count,covariance_x_m2,covariance_y_m2
```

For this sample dataset, the fused output is expected to contain one row per Radar measurement. Therefore, the output timestamps must match the Radar timestamps.

## TDD Tests

Install the development dependencies in a local virtual environment and run the tests:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The tests in `tests/test_dataset_quality.py` validate that the datasets are coherent. The tests in `tests/test_fusion_contract.py` define the behavior that an external fusion implementation must satisfy through the public functions in `src/ship_fusion/fusion.py`.

The expected starting point is red-green TDD: dataset tests pass, while fusion-contract tests fail until the fusion module is implemented. The fused trajectory is also validated against ground truth with `y` thresholds: RMSE <= 35 m, max error <= 50 m, and mean error <= 30 m.
