"""Grouping keys, measurements, and rows used by report calculations."""

from typing import NamedTuple, TypeAlias, TypedDict

from imagebench.types.benchmark import Phase


class ScoreGroup(NamedTuple):
    """Scores comparable within the same profile, size, and evaluator version."""

    profile: str
    width: int
    height: int
    metric: str
    evaluator: str
    revision: str


class CaseScore(NamedTuple):
    """One evaluator value paired with the generation latency for that case."""

    value: float
    latency_s: float


ScoreGroups: TypeAlias = dict[ScoreGroup, dict[str, CaseScore]]
ScoreSummaryRow: TypeAlias = dict[str, str | int | float]


class TimingRow(TypedDict):
    """Timing statistics for one phase, profile, and image size."""

    phase: Phase
    profile: str
    width: int
    height: int
    n: int
    median_s: float
    p95_s: float | None
    images_per_min: float
