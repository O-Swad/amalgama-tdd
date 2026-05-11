import csv
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

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
    "heading_deg",
    "mmsi",
    "navigation_status",
    "position_accuracy",
    "radar_id",
    "track_id",
    "range_m",
    "bearing_deg",
    "range_rate_mps",
    "source_count",
    "covariance_x_m2",
    "covariance_y_m2",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def distance_m(a: dict[str, str], b: dict[str, str]) -> float:
    lat1 = math.radians(float(a["latitude_deg"]))
    lat2 = math.radians(float(b["latitude_deg"]))
    dlat = lat2 - lat1
    dlon = math.radians(float(b["longitude_deg"]) - float(a["longitude_deg"]))
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))


def correlated_ais_row(ais_rows: list[dict[str, str]], radar_row: dict[str, str]) -> dict[str, str]:
    radar_time = parse_timestamp(radar_row["timestamp_utc"])
    candidates = [
        row
        for row in ais_rows
        if abs((parse_timestamp(row["timestamp_utc"]) - radar_time).total_seconds()) <= 20
    ]
    return min(
        candidates,
        key=lambda row: (
            distance_m(row, radar_row),
            abs((parse_timestamp(row["timestamp_utc"]) - radar_time).total_seconds()),
        ),
    )


def fused_rows() -> list[dict[str, str]]:
    return fuse_tracks(
        AIS_CSV,
        RADAR_CSV,
        vessel_id="VESSEL-001",
        output_interval_seconds=10,
    )


def test_fusion_outputs_one_simulator_row_per_radar_measurement():
    rows = fused_rows()
    radar_rows = read_csv(RADAR_CSV)

    assert len(rows) == len(radar_rows)
    assert list(rows[0].keys()) == SIMULATOR_SCHEMA
    assert [row["timestamp_utc"] for row in rows] == [row["timestamp_utc"] for row in radar_rows]
    assert {row["vessel_id"] for row in rows} == {"VESSEL-001"}
    assert all(int(row["source_count"]) == 2 for row in rows)
    assert all(float(row["covariance_x_m2"]) > 0 for row in rows)
    assert all(float(row["covariance_y_m2"]) > 0 for row in rows)


def test_radar_position_has_priority_over_ais_position():
    rows = fused_rows()
    radar_rows = read_csv(RADAR_CSV)
    ais_rows = read_csv(AIS_CSV)

    fused_row = rows[0]
    radar_row = radar_rows[0]
    ais_row = correlated_ais_row(ais_rows, radar_row)

    assert fused_row["timestamp_utc"] == radar_row["timestamp_utc"]
    assert float(fused_row["latitude_deg"]) == pytest.approx(float(radar_row["latitude_deg"]), abs=0.000001)
    assert float(fused_row["longitude_deg"]) == pytest.approx(float(radar_row["longitude_deg"]), abs=0.000001)
    assert float(fused_row["latitude_deg"]) != pytest.approx(float(ais_row["latitude_deg"]), abs=0.000001)
    assert float(fused_row["longitude_deg"]) != pytest.approx(float(ais_row["longitude_deg"]), abs=0.000001)


def test_radar_measurements_are_enriched_with_geometrically_correlated_ais_attributes():
    rows = fused_rows()
    radar_rows = read_csv(RADAR_CSV)
    ais_rows = read_csv(AIS_CSV)

    for fused_row, radar_row in zip(rows, radar_rows):
        ais_row = correlated_ais_row(ais_rows, radar_row)

        assert fused_row["mmsi"] == ais_row["mmsi"]
        assert fused_row["sog_mps"] == ais_row["sog_mps"]
        assert fused_row["cog_deg"] == ais_row["cog_deg"]
        assert fused_row["heading_deg"] == ais_row["heading_deg"]
        assert fused_row["navigation_status"] == ais_row["navigation_status"]
        assert fused_row["position_accuracy"] == ais_row["position_accuracy"]
        assert fused_row["radar_id"] == radar_row["radar_id"]
        assert fused_row["track_id"] == radar_row["track_id"]
        assert fused_row["range_m"] == radar_row["range_m"]
        assert fused_row["bearing_deg"] == radar_row["bearing_deg"]
        assert fused_row["range_rate_mps"] == radar_row["range_rate_mps"]


def test_correlation_uses_temporal_and_geometric_proximity_not_sensor_ids():
    rows = fused_rows()

    row_at_100025 = next(row for row in rows if row["timestamp_utc"] == "2026-05-07T10:00:25Z")

    assert row_at_100025["mmsi"] == "224123456"
    assert row_at_100025["sog_mps"] == "6.16"
    assert row_at_100025["cog_deg"] == "61.7"
    assert row_at_100025["heading_deg"] == "62.7"


def test_correlation_accepts_ais_and_radar_tracks_with_different_ids(tmp_path):
    ais_rows = read_csv(AIS_CSV)
    for row in ais_rows:
        row["vessel_id"] = "AIS-TRACK-ALPHA"

    ais_with_different_ids = tmp_path / "ais_with_different_ids.csv"
    with ais_with_different_ids.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(ais_rows[0].keys()))
        writer.writeheader()
        writer.writerows(ais_rows)

    rows = fuse_tracks(
        ais_with_different_ids,
        RADAR_CSV,
        vessel_id="VESSEL-001",
        output_interval_seconds=10,
    )

    assert rows[0]["mmsi"] == "224123456"
    assert rows[0]["navigation_status"] == "under_way_using_engine"
    assert rows[0]["position_accuracy"] == "high"


def test_correlation_rejects_id_match_when_geometry_is_implausible(tmp_path):
    ais_rows = read_csv(AIS_CSV)
    radar_rows = read_csv(RADAR_CSV)
    misleading_ais_row = dict(ais_rows[0])
    misleading_ais_row.update(
        {
            "timestamp_utc": radar_rows[0]["timestamp_utc"],
            "vessel_id": radar_rows[0]["vessel_id"],
            "mmsi": "999999999",
            "latitude_deg": "36.900000",
            "longitude_deg": "-6.900000",
            "sog_mps": "0.00",
            "cog_deg": "0.0",
            "heading_deg": "0.0",
            "navigation_status": "moored",
            "position_accuracy": "low",
        }
    )
    ais_with_misleading_id = tmp_path / "ais_with_misleading_id.csv"
    with ais_with_misleading_id.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(ais_rows[0].keys()))
        writer.writeheader()
        writer.writerows([misleading_ais_row, *ais_rows])

    rows = fuse_tracks(
        ais_with_misleading_id,
        RADAR_CSV,
        vessel_id="VESSEL-001",
        output_interval_seconds=10,
    )

    assert rows[0]["mmsi"] == "224123456"
    assert rows[0]["navigation_status"] == "under_way_using_engine"
    assert rows[0]["position_accuracy"] == "high"


def test_fusion_result_can_be_written_as_simulator_input_csv(tmp_path):
    rows = fused_rows()
    output_csv = tmp_path / "fusion_result.csv"

    write_fusion_result(rows, output_csv)

    with output_csv.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        written_rows = list(reader)

    assert reader.fieldnames == SIMULATOR_SCHEMA
    assert written_rows == rows


def test_fusion_quality_is_good_enough_for_simulator_comparison(tmp_path):
    rows = fused_rows()
    output_csv = tmp_path / "fusion_result.csv"
    write_fusion_result(rows, output_csv)

    metrics = evaluate_against_ground_truth(output_csv, GROUND_TRUTH_CSV)

    assert metrics["matched_points"] == 30
    assert metrics["rmse_m"] <= 35
    assert metrics["max_error_m"] <= 50
    assert metrics["mean_error_m"] <= 30
