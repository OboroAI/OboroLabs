"""Read external evaluator scores and compare matched warm cases."""

import csv
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean, median

from imagebench.constants.benchmark import WARM
from imagebench.constants.report import PAIR_FIELDS, QUALITY_FIELDS, SCORE_FIELDS
from imagebench.types.benchmark import Record
from imagebench.types.report import CaseScore, ScoreGroup, ScoreGroups, ScoreSummaryRow

__all__ = ["PAIR_FIELDS", "QUALITY_FIELDS", "load_scores", "summarize"]


def _parse_score(
    row: Mapping[str, str | None],
    warm_jobs: Mapping[str, Record],
    line: int,
) -> tuple[ScoreGroup, str, CaseScore]:
    job = warm_jobs.get(row["job_id"] or "")
    if job is None:
        raise ValueError(f"score line {line}: unknown completed warm job")

    metric = (row["metric"] or "").strip()
    evaluator = (row["evaluator"] or "").strip()
    revision = (row["revision"] or "").strip()
    if not (metric and evaluator and revision):
        raise ValueError(f"score line {line}: missing metric, evaluator or revision")

    value = float(row["value"] or "nan")
    if not math.isfinite(value):
        raise ValueError(f"score line {line}: score must be finite")

    group = ScoreGroup(job["profile"], job["width"], job["height"], metric, evaluator, revision)
    return group, job["case_id"], CaseScore(value, job["latency_s"])


def load_scores(path: Path, records: Sequence[Record]) -> ScoreGroups:
    """Load one finite score per completed warm case and evaluator version."""
    warm_jobs = {record["id"]: record for record in records if record["phase"] == WARM}
    grouped: ScoreGroups = defaultdict(dict)

    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not set(SCORE_FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("scores CSV needs " + ", ".join(SCORE_FIELDS))

        for line, row in enumerate(reader, start=2):
            group, case_id, score = _parse_score(row, warm_jobs, line)
            case_scores = grouped[group]
            if case_id in case_scores:
                raise ValueError(f"score line {line}: duplicate score")
            case_scores[case_id] = score
    return grouped


def _compare_cases(
    group: ScoreGroup,
    candidate: Mapping[str, CaseScore],
    reference: str,
    baseline: Mapping[str, CaseScore],
) -> ScoreSummaryRow | None:
    # Use the same paired case set for both score differences and latency medians.
    shared_cases = sorted(candidate.keys() & baseline.keys())
    if not shared_cases:
        return None

    candidate_latency = median(candidate[case_id].latency_s for case_id in shared_cases)
    reference_latency = median(baseline[case_id].latency_s for case_id in shared_cases)
    return {
        **group._asdict(),
        "reference": reference,
        "n_pairs": len(shared_cases),
        "n_scored": len(candidate),
        "reference_n_scored": len(baseline),
        "mean_delta": mean(candidate[case_id].value - baseline[case_id].value for case_id in shared_cases),
        "median_s": candidate_latency,
        "reference_median_s": reference_latency,
        "speed_ratio": reference_latency / candidate_latency,
    }


def summarize(
    scores: ScoreGroups, records: Sequence[Record], reference: str | None = None
) -> tuple[list[ScoreSummaryRow], list[ScoreSummaryRow]]:
    """Summarize coverage and compare only matching sizes, metrics, and revisions."""
    generated = Counter(
        (record["profile"], record["width"], record["height"]) for record in records if record["phase"] == WARM
    )
    quality: list[ScoreSummaryRow] = []
    pairs: list[ScoreSummaryRow] = []

    for group, case_scores in sorted(scores.items()):
        quality.append(
            {
                **group._asdict(),
                "n_scored": len(case_scores),
                "n_generated": generated[group.profile, group.width, group.height],
                "mean": mean(score.value for score in case_scores.values()),
            }
        )
        if reference is None or group.profile == reference:
            continue

        reference_scores = scores.get(group._replace(profile=reference), {})
        pair = _compare_cases(group, case_scores, reference, reference_scores)
        if pair is not None:
            pairs.append(pair)
    return quality, pairs
