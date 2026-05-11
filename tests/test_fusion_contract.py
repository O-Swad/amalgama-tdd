import csv
from datetime import datetime, timezone
from pathlib import Path

from ship_fusion.fusion import evaluate_against_ground_truth, fuse_tracks, write_fusion_result


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
AIS_CSV = DATA_DIR / "ais_readings.csv"
RADAR_CSV = DATA_DIR / "radar_readings.csv"
GROUND_TRUTH_CSV = DATA_DIR / "ground_truth.csv"

SIMULATOR_SCHEMA = [
    "timestamp_utc",
    "vessel_id",
    "latitude_deg",
    "longitude_deg",
    "sog_mps",
    "cog_deg",
    "source_count",
    "covariance_x_m2",
    "covariance_y_m2",
]


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_fusion_returns_simulator_ready_rows_at_ground_truth_cadence():
    rows = fuse_tracks(
        AIS_CSV,
        RADAR_CSV,
        vessel_id="VESSEL-001",
        output_interval_seconds=10,
    )

    assert len(rows) == 31
    assert list(rows[0].keys()) == SIMULATOR_SCHEMA
    assert {row["vessel_id"] for row in rows} == {"VESSEL-001"}
    assert [parse_timestamp(row["timestamp_utc"]) for row in rows] == sorted(
        parse_timestamp(row["timestamp_utc"]) for row in rows
    )
    assert all(int(row["source_count"]) >= 1 for row in rows)
    assert all(float(row["covariance_x_m2"]) > 0 for row in rows)
    assert all(float(row["covariance_y_m2"]) > 0 for row in rows)


def test_fusion_result_can_be_written_as_simulator_input_csv(tmp_path):
    rows = fuse_tracks(
        AIS_CSV,
        RADAR_CSV,
        vessel_id="VESSEL-001",
        output_interval_seconds=10,
    )
    output_csv = tmp_path / "fusion_result.csv"

    write_fusion_result(rows, output_csv)

    with output_csv.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        written_rows = list(reader)

    assert reader.fieldnames == SIMULATOR_SCHEMA
    assert written_rows == rows


def test_fusion_quality_is_good_enough_for_simulator_comparison(tmp_path):
    rows = fuse_tracks(
        AIS_CSV,
        RADAR_CSV,
        vessel_id="VESSEL-001",
        output_interval_seconds=10,
    )
    output_csv = tmp_path / "fusion_result.csv"
    write_fusion_result(rows, output_csv)

    metrics = evaluate_against_ground_truth(output_csv, GROUND_TRUTH_CSV)

    assert metrics["matched_points"] == 31
    assert metrics["rmse_m"] <= 20
    assert metrics["max_error_m"] <= 40
    assert metrics["mean_error_m"] <= 16
