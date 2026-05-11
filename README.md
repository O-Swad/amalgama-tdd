# Ship Fusion Simulator

Starter project for evaluating a maritime positioning data-fusion module.

## Sample Data

The CSV files in `data/` describe a single correlatable vessel with `vessel_id=VESSEL-001`:

- `ground_truth.csv`: ground-truth positions every 10 seconds between `2026-05-07T10:00:00Z` and `2026-05-07T10:05:00Z`.
- `ais_readings.csv`: AIS readings every 30 seconds with small position error.
- `radar_readings.csv`: Radar readings every 10 seconds, offset by 5 seconds from ground truth, with larger position error.

## Fusion Result Contract

The simulator expects a CSV file with this header:

```csv
timestamp_utc,vessel_id,latitude_deg,longitude_deg,sog_mps,cog_deg,source_count,covariance_x_m2,covariance_y_m2
```

## TDD Tests

Install the development dependencies in a local virtual environment and run the tests:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The tests in `tests/test_dataset_quality.py` validate that the datasets are coherent. The tests in
`tests/test_fusion_contract.py` define the behavior that the fusion module must implement in
`src/ship_fusion/fusion.py`.
