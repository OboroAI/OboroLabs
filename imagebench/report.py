"""Export verified run records, timing statistics, and evaluator comparisons."""

from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from imagebench.constants.benchmark import COLD, WARM
from imagebench.constants.report import PAIR_FIELDS, QUALITY_FIELDS, RECORD_FIELDS, TIMING_FIELDS
from imagebench.plan import make_jobs
from imagebench.quality import load_scores, summarize
from imagebench.storage import atomic, csv_file, load_manifest, load_record, writer
from imagebench.timing import percentile, summarize_timing
from imagebench.types.benchmark import Phase
from imagebench.types.report import ScoreSummaryRow, TimingRow

__all__ = ["csv_file", "percentile", "report"]


def _markdown(
    rows: Sequence[TimingRow],
    counts: Counter[Phase],
    expected_warm: int,
    *,
    has_quality: bool,
    has_pairs: bool,
) -> str:
    lines = [
        "# Image benchmark",
        "",
        f"Warm jobs complete: {counts[WARM]}/{expected_warm}. Cold samples: {counts[COLD]}.",
        "",
        "Timing uses HTTP wall seconds from submission through confirmed completion. "
        "Cold requires a fresh server declared by the operator.",
        "",
        "| Phase | Profile | Size | n | Median (s) | p95 (s) | Images/min |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        p95 = "—" if row["p95_s"] is None else f"{row['p95_s']:.3f}"
        lines.append(
            f"| {row['phase']} | {row['profile']} | {row['width']}×{row['height']} | {row['n']} | "
            f"{row['median_s']:.3f} | {p95} | {row['images_per_min']:.2f} |"
        )
    lines.extend(("", "[Records](records.csv) · [Timing](timing.csv)"))
    if has_quality:
        lines.extend(("", "[Quality by evaluator](quality.csv)"))
    if has_pairs:
        lines.extend(("", "[Matched quality and latency](pairs.csv)"))
    return "\n".join(lines) + "\n"


def report(directory: Path, scores: Path | None = None, reference: str | None = None) -> None:
    """Verify a saved run and write its CSV and Markdown reports."""
    # Share the runner's lock so exports see one consistent set of records.
    with writer(directory):
        plan = load_manifest(directory)
        if reference and reference not in {profile["id"] for profile in plan["profiles"]}:
            raise ValueError(f"unknown reference profile {reference}")

        warm_jobs = list(make_jobs(plan))
        jobs = warm_jobs + list(make_jobs(plan, COLD))
        records = [record for job in jobs if (record := load_record(directory, job)) is not None]
        timing = summarize_timing(records)

        quality: list[ScoreSummaryRow] = []
        pairs: list[ScoreSummaryRow] = []
        if scores is not None:
            quality, pairs = summarize(load_scores(scores, records), records, reference)

        destination = directory / "report"
        csv_file(destination / "records.csv", RECORD_FIELDS, records)
        csv_file(destination / "timing.csv", TIMING_FIELDS, timing)
        csv_file(destination / "quality.csv", QUALITY_FIELDS, quality)
        csv_file(destination / "pairs.csv", PAIR_FIELDS, pairs)

        counts = Counter(record["phase"] for record in records)
        summary = _markdown(timing, counts, len(warm_jobs), has_quality=bool(quality), has_pairs=bool(pairs))
        summary_path = destination / "summary.md"
        atomic(summary_path, summary.encode("utf-8"))
        print(summary_path)
