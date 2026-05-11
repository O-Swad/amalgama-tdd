import csv
import math
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
AIS_CSV = DATA_DIR / "ais_readings.csv"
RADAR_CSV = DATA_DIR / "radar_readings.csv"
GROUND_TRUTH_CSV = DATA_DIR / "ground_truth.csv"


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


def nearest_truth(truth_rows: list[dict[str, str]], timestamp: datetime) -> dict[str, str]:
    return min(truth_rows, key=lambda row: abs((parse_timestamp(row["timestamp_utc"]) - timestamp).total_seconds()))


def assert_strictly_increasing_timestamps(rows: list[dict[str, str]]) -> None:
    timestamps = [parse_timestamp(row["timestamp_utc"]) for row in rows]
    assert timestamps == sorted(timestamps)
    assert len(timestamps) == len(set(timestamps))


def test_dataset_files_exist_and_have_expected_schemas():
    assert set(DATA_DIR.iterdir()) >= {AIS_CSV, RADAR_CSV, GROUND_TRUTH_CSV}

    assert read_csv(GROUND_TRUTH_CSV)[0].keys() == {
        "timestamp_utc",
        "vessel_id",
        "latitude_deg",
        "longitude_deg",
        "sog_mps",
        "cog_deg",
        "heading_deg",
    }
    assert read_csv(AIS_CSV)[0].keys() == {
        "timestamp_utc",
        "mmsi",
        "vessel_id",
        "latitude_deg",
        "longitude_deg",
        "sog_mps",
        "cog_deg",
        "heading_deg",
        "navigation_status",
        "position_accuracy",
    }
    assert read_csv(RADAR_CSV)[0].keys() == {
        "timestamp_utc",
        "radar_id",
        "track_id",
        "vessel_id",
        "range_m",
        "bearing_deg",
        "range_rate_mps",
        "latitude_deg",
        "longitude_deg",
        "measurement_std_m",
    }


def test_sensor_and_truth_timestamps_are_correlatable():
    truth = read_csv(GROUND_TRUTH_CSV)
    ais = read_csv(AIS_CSV)
    radar = read_csv(RADAR_CSV)

    for rows in (truth, ais, radar):
        assert_strictly_increasing_timestamps(rows)
        assert {row["vessel_id"] for row in rows} == {"VESSEL-001"}

    truth_times = [parse_timestamp(row["timestamp_utc"]) for row in truth]
    ais_times = [parse_timestamp(row["timestamp_utc"]) for row in ais]
    radar_times = [parse_timestamp(row["timestamp_utc"]) for row in radar]

    assert (truth_times[1] - truth_times[0]).total_seconds() == 10
    assert (ais_times[1] - ais_times[0]).total_seconds() == 30
    assert (radar_times[1] - radar_times[0]).total_seconds() == 10
    assert (radar_times[0] - truth_times[0]).total_seconds() == 5
    assert min(ais_times) >= min(truth_times)
    assert max(ais_times) <= max(truth_times)
    assert min(radar_times) >= min(truth_times)
    assert max(radar_times) <= max(truth_times)


def test_sensor_measurements_are_close_to_ground_truth_but_not_identical():
    truth = read_csv(GROUND_TRUTH_CSV)

    ais_errors = [
        distance_m(row, nearest_truth(truth, parse_timestamp(row["timestamp_utc"])))
        for row in read_csv(AIS_CSV)
    ]
    radar_errors = [
        distance_m(row, nearest_truth(truth, parse_timestamp(row["timestamp_utc"])))
        for row in read_csv(RADAR_CSV)
    ]

    assert 0 < sum(ais_errors) / len(ais_errors) < 8
    assert 5 < sum(radar_errors) / len(radar_errors) < 45
    assert max(ais_errors) < 10
    assert max(radar_errors) < 50
