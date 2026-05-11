import csv
from datetime import datetime, timezone
from pathlib import Path

from geographiclib.geodesic import Geodesic

from ship_fusion.fusion import evaluate_against_ground_truth, fuse_tracks, write_fusion_result


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures"

AIS_CSV = DATA_DIR / "ais_readings.csv"
RADAR_CSV = DATA_DIR / "radar_readings.csv"
GROUND_TRUTH_CSV = DATA_DIR / "ground_truth.csv"

KNOWN_AIS_CSV = FIXTURE_DIR / "known_correlation_ais.csv"
KNOWN_RADAR_CSV = FIXTURE_DIR / "known_correlation_radar.csv"
EXPECTED_CORRELATIONS_CSV = FIXTURE_DIR / "expected_correlations.csv"
EXPECTED_FUSION_RESULT_CSV = FIXTURE_DIR / "expected_fusion_result.csv"

MAX_CORRELATION_DISTANCE_M = 130.0
MAX_CORRELATION_TIME_DELTA_SECONDS = 20.0
MAX_GROUND_TRUTH_RMSE_M = 35.0
MAX_GROUND_TRUTH_ERROR_M = 50.0
MAX_GROUND_TRUTH_MEAN_ERROR_M = 30.0

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


def geodesic_distance_m(a: dict[str, str], b: dict[str, str]) -> float:
    return Geodesic.WGS84.Inverse(
        float(a["latitude_deg"]),
        float(a["longitude_deg"]),
        float(b["latitude_deg"]),
        float(b["longitude_deg"]),
    )["s12"]


def timestamp_delta_seconds(a: dict[str, str], b: dict[str, str]) -> float:
    return abs((parse_timestamp(a["timestamp_utc"]) - parse_timestamp(b["timestamp_utc"])).total_seconds())


def row_by_key(rows: list[dict[str, str]], *fields: str) -> dict[tuple[str, ...], dict[str, str]]:
    return {tuple(row[field] for field in fields): row for row in rows}


def find_enrichment_source(fused_row: dict[str, str], ais_rows: list[dict[str, str]]) -> dict[str, str]:
    matches = [
        row
        for row in ais_rows
        if row["mmsi"] == fused_row["mmsi"]
        and row["sog_mps"] == fused_row["sog_mps"]
        and row["cog_deg"] == fused_row["cog_deg"]
        and row["heading_deg"] == fused_row["heading_deg"]
        and row["navigation_status"] == fused_row["navigation_status"]
        and row["position_accuracy"] == fused_row["position_accuracy"]
    ]
    assert matches, "Fused row must be enriched from an AIS row in the input file"
    return min(matches, key=lambda row: timestamp_delta_seconds(row, fused_row))


def fused_rows() -> list[dict[str, str]]:
    return fuse_tracks(
        AIS_CSV,
        RADAR_CSV,
        vessel_id="VESSEL-001",
        output_interval_seconds=10,
    )


def known_fused_rows() -> list[dict[str, str]]:
    return fuse_tracks(
        KNOWN_AIS_CSV,
        KNOWN_RADAR_CSV,
        vessel_id="RADAR-ALPHA",
        output_interval_seconds=10,
    )


def test_known_correlation_fixture_is_internally_consistent():
    ais_rows = read_csv(KNOWN_AIS_CSV)
    radar_rows = read_csv(KNOWN_RADAR_CSV)
    expected_correlations = read_csv(EXPECTED_CORRELATIONS_CSV)

    radar_by_key = row_by_key(radar_rows, "timestamp_utc", "radar_id", "track_id")
    ais_by_key = row_by_key(ais_rows, "timestamp_utc", "mmsi")

    for expected in expected_correlations:
        radar = radar_by_key[(
            expected["radar_timestamp_utc"],
            expected["radar_id"],
            expected["track_id"],
        )]
        ais = ais_by_key[(
            expected["expected_ais_timestamp_utc"],
            expected["expected_mmsi"],
        )]

        assert timestamp_delta_seconds(ais, radar) <= float(expected["max_time_delta_seconds"])
        assert geodesic_distance_m(ais, radar) <= float(expected["max_geodesic_distance_m"])



def test_known_correlation_examples_match_expected_results():
    rows = known_fused_rows()
    ais_rows = read_csv(KNOWN_AIS_CSV)
    radar_rows = read_csv(KNOWN_RADAR_CSV)
    expected_correlations = read_csv(EXPECTED_CORRELATIONS_CSV)

    actual_by_radar = row_by_key(rows, "timestamp_utc", "radar_id", "track_id")
    radar_by_key = row_by_key(radar_rows, "timestamp_utc", "radar_id", "track_id")
    ais_by_key = row_by_key(ais_rows, "timestamp_utc", "mmsi")

    assert len(rows) == len(expected_correlations)

    for expected in expected_correlations:
        radar_key = (
            expected["radar_timestamp_utc"],
            expected["radar_id"],
            expected["track_id"],
        )
        ais_key = (
            expected["expected_ais_timestamp_utc"],
            expected["expected_mmsi"],
        )
        actual = actual_by_radar[radar_key]
        radar = radar_by_key[radar_key]
        expected_ais = ais_by_key[ais_key]

        assert actual["mmsi"] == expected["expected_mmsi"]
        assert timestamp_delta_seconds(expected_ais, radar) <= float(expected["max_time_delta_seconds"])
        assert geodesic_distance_m(expected_ais, radar) <= float(expected["max_geodesic_distance_m"])


def test_known_fusion_result_matches_expected_golden_csv():
    rows = known_fused_rows()
    expected_rows = read_csv(EXPECTED_FUSION_RESULT_CSV)

    assert rows == expected_rows


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
    ais_row = find_enrichment_source(fused_row, ais_rows)

    assert fused_row["timestamp_utc"] == radar_row["timestamp_utc"]
    assert fused_row["latitude_deg"] == radar_row["latitude_deg"]
    assert fused_row["longitude_deg"] == radar_row["longitude_deg"]
    assert fused_row["latitude_deg"] != ais_row["latitude_deg"]
    assert fused_row["longitude_deg"] != ais_row["longitude_deg"]


def test_radar_rows_are_enriched_with_ais_inside_correlation_thresholds():
    rows = fused_rows()
    radar_rows = read_csv(RADAR_CSV)
    ais_rows = read_csv(AIS_CSV)

    for fused_row, radar_row in zip(rows, radar_rows):
        ais_row = find_enrichment_source(fused_row, ais_rows)

        assert fused_row["radar_id"] == radar_row["radar_id"]
        assert fused_row["track_id"] == radar_row["track_id"]
        assert fused_row["range_m"] == radar_row["range_m"]
        assert fused_row["bearing_deg"] == radar_row["bearing_deg"]
        assert fused_row["range_rate_mps"] == radar_row["range_rate_mps"]
        assert timestamp_delta_seconds(ais_row, radar_row) <= MAX_CORRELATION_TIME_DELTA_SECONDS
        assert geodesic_distance_m(ais_row, radar_row) <= MAX_CORRELATION_DISTANCE_M


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
    assert metrics["rmse_m"] <= MAX_GROUND_TRUTH_RMSE_M
    assert metrics["max_error_m"] <= MAX_GROUND_TRUTH_ERROR_M
    assert metrics["mean_error_m"] <= MAX_GROUND_TRUTH_MEAN_ERROR_M
