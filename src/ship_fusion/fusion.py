"""Public contract for the ship sensor-fusion module.

The tests define the expected behavior for these functions. Implement them
incrementally using TDD.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def fuse_tracks(
    ais_csv: str | Path,
    radar_csv: str | Path,
    *,
    vessel_id: str,
    output_interval_seconds: int = 10,
) -> list[dict[str, Any]]:
    """Fuse AIS and Radar readings into an estimated trajectory.

    The returned rows must be ready to serialize as simulator input.
    """
    raise NotImplementedError("Implement the fusion algorithm using the TDD tests.")


def write_fusion_result(rows: list[dict[str, Any]], output_csv: str | Path) -> None:
    """Write fused rows to CSV using the simulator contract schema."""
    raise NotImplementedError("Implement CSV serialization for fused trajectories.")


def evaluate_against_ground_truth(
    fused_csv: str | Path,
    ground_truth_csv: str | Path,
) -> dict[str, float]:
    """Compare estimated positions with ground truth and return error metrics."""
    raise NotImplementedError("Implement trajectory evaluation metrics.")
