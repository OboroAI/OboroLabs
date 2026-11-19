"""Timing statistics grouped by run phase, profile, and image size."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from math import ceil, floor
from statistics import mean, median

from imagebench.constants.report import SECONDS_PER_MINUTE, TAIL_PERCENTILE
from imagebench.types.benchmark import Phase, Record
from imagebench.types.report import TimingRow

__all__ = ["percentile", "summarize_timing"]


def percentile(values: Sequence[float], q: float) -> float:
    """Compute a quantile by linearly interpolating adjacent sorted samples."""
    ordered = sorted(values)
    # Scale by n - 1 so quantiles 0 and 1 land on the first and last sample.
    position = q * (len(ordered) - 1)
    lower = floor(position)
    upper = ceil(position)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def summarize_timing(records: Iterable[Record]) -> list[TimingRow]:
    """Summarize measured latency for each group in stable report order."""
    groups: dict[tuple[Phase, str, int, int], list[float]] = defaultdict(list)
    for record in records:
        group = (record["phase"], record["profile"], record["width"], record["height"])
        groups[group].append(record["latency_s"])

    rows: list[TimingRow] = []
    for (phase, profile, width, height), latencies in sorted(groups.items()):
        sample_count = len(latencies)
        rows.append(
            {
                "phase": phase,
                "profile": profile,
                "width": width,
                "height": height,
                "n": sample_count,
                "median_s": median(latencies),
                # Leave the tail estimate blank for a single observation.
                "p95_s": percentile(latencies, TAIL_PERCENTILE) if sample_count > 1 else None,
                "images_per_min": SECONDS_PER_MINUTE / mean(latencies),
            }
        )
    return rows
