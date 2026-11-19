"""Persist run state with atomic writes and one writer per output folder."""

import csv
import fcntl
import hashlib
import io
import json
import math
import struct
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from imagebench.constants.benchmark import COLD, MANIFEST_NAME, PNG_SIGNATURE, WORKFLOW_NAME
from imagebench.types.benchmark import Job, Record, RunManifest
from imagebench.types.comfy import ImageResult

__all__ = [
    "atomic",
    "csv_file",
    "json_bytes",
    "load_manifest",
    "load_record",
    "prepare_run",
    "read_json",
    "save_record",
    "sha",
    "validate_png",
    "writer",
]


def sha(data: bytes) -> str:
    """Return the lowercase SHA-256 digest of the given bytes."""
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    """Serialize JSON deterministically for hashing and resume checks."""
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def read_json(path: Path) -> object:
    """Read JSON from a run file."""
    value: object = json.loads(path.read_bytes())
    return value


def atomic(path: Path, data: bytes) -> None:
    """Replace one complete file while the run's writer lock is held."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(data)
    partial.replace(path)


def csv_file(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    """Write a CSV with a stable header, including when its rows are empty."""
    buffer = io.StringIO(newline="")
    table = csv.DictWriter(buffer, fields)
    table.writeheader()
    table.writerows(rows)
    atomic(path, buffer.getvalue().encode("utf-8"))


@contextmanager
def writer(directory: Path) -> Iterator[None]:
    """Lock the output folder for a run or report, failing if it is busy."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another command is writing this run") from exc
        yield


def load_manifest(directory: Path) -> RunManifest:
    """Read the saved plan and backend identity for a run."""
    return cast(RunManifest, read_json(directory / MANIFEST_NAME))


def prepare_run(directory: Path, manifest: RunManifest, workflow: bytes) -> None:
    """Initialize the run or verify that its manifest and workflow still match."""
    manifest_path = directory / MANIFEST_NAME
    workflow_path = directory / WORKFLOW_NAME
    if not manifest_path.exists():
        atomic(workflow_path, workflow)
        atomic(manifest_path, json_bytes(manifest))
        return

    if load_manifest(directory) != manifest:
        raise ValueError("run manifest differs. Use the original config or a new directory.")
    if workflow_path.read_bytes() != workflow:
        raise ValueError("saved workflow differs from the run manifest")


def validate_png(data: bytes, width: int, height: int) -> None:
    """Check the PNG signature, expected dimensions, and final chunk."""
    if len(data) < 45 or not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        raise ValueError("backend did not return a PNG")
    if struct.unpack(">II", data[16:24]) != (width, height) or data[-8:-4] != b"IEND":
        raise ValueError("PNG dimensions or final chunk do not match the job")


def load_record(directory: Path, job: Job) -> Record | None:
    """Verify a completed record and its PNG before reuse or reporting."""
    job_id = job["id"]
    path = directory / "records" / f"{job_id}.json"
    if not path.is_file():
        return None

    png_name = f"images/{job_id}.png"
    record = cast(Record, read_json(path))
    if any(record.get(key) != value for key, value in job.items()) or record.get("png") != png_name:
        raise ValueError(f"record differs from plan: {job_id}")
    latency = record.get("latency_s")
    if not isinstance(latency, (int, float)) or not math.isfinite(latency) or latency <= 0:
        raise ValueError(f"invalid measured latency: {job_id}")
    image = directory / png_name
    if not image.is_file() or sha(image.read_bytes()) != record.get("png_sha256"):
        raise ValueError(f"missing or changed PNG: {job_id}")
    return record


def save_record(directory: Path, job: Job, result: ImageResult) -> None:
    """Commit a completed job only after its validated PNG is in place."""
    validate_png(result.png, job["width"], job["height"])
    png = f"images/{job['id']}.png"
    record: Record = {
        **job,
        "cache_condition": "operator_fresh_server" if job["phase"] == COLD else "primed",
        "latency_s": result.latency_s,
        "image_fetch_s": result.image_fetch_s,
        "png": png,
        "png_sha256": sha(result.png),
    }

    # The JSON record is the commit marker. A retry can replace an orphaned PNG.
    atomic(directory / png, result.png)
    atomic(directory / "records" / f"{job['id']}.json", json_bytes(record))
