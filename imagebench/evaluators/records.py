"""Read verified warm inputs for offline scoring."""

from pathlib import Path

from imagebench.plan import make_jobs
from imagebench.storage import load_manifest, load_record
from imagebench.types.benchmark import Record


def warm_records(directory: Path) -> list[Record]:
    """Collect completed jobs while the caller holds the run lock."""
    plan = load_manifest(directory)
    return [record for job in make_jobs(plan) if (record := load_record(directory, job)) is not None]
