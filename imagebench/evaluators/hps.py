"""Score generated images with the HPS v2.0 checkpoint used by Oboro Blink."""

import math
from collections import defaultdict
from hashlib import file_digest
from importlib import import_module
from importlib.metadata import version
from pathlib import Path

from imagebench.constants.evaluators import HPS_CHECKPOINT_REVISION, HPS_CHECKPOINT_SHA256, HPS_MODEL_VERSION, HPS_SCALE
from imagebench.constants.report import SCORE_FIELDS
from imagebench.evaluators.records import warm_records
from imagebench.storage import csv_file, writer
from imagebench.types.benchmark import Record
from imagebench.types.evaluators import ScoreRow


def evaluate_hps(directory: Path, checkpoint: Path, output: Path) -> None:
    """Run the optional HPS scorer on verified warm images and export its scores."""
    try:
        scorer = import_module("hpsv2.img_score")
    except ImportError as exc:
        raise RuntimeError(f"HPS needs its optional dependencies from requirements-hps.txt: {exc}") from exc

    with checkpoint.open("rb") as stream:
        if file_digest(stream, "sha256").hexdigest() != HPS_CHECKPOINT_SHA256:
            raise ValueError("checkpoint SHA-256 differs from the pinned HPS v2.0 weights")

    scores: list[ScoreRow] = []
    revision = f"hpsv2 {version('hpsv2')} / {HPS_MODEL_VERSION} / {HPS_CHECKPOINT_REVISION}"
    with writer(directory):
        by_prompt: dict[str, list[Record]] = defaultdict(list)
        for record in warm_records(directory):
            by_prompt[record["prompt"]].append(record)
        if not by_prompt:
            raise ValueError("no completed warm jobs for HPS")

        # The upstream scorer loads its checkpoint once per call and shares one prompt.
        for prompt, records in by_prompt.items():
            images = [str(directory / record["png"]) for record in records]
            values = scorer.score(images, prompt, cp=str(checkpoint), hps_version=HPS_MODEL_VERSION)
            if len(values) != len(records):
                raise ValueError("HPS returned a different number of scores than images")
            for record, score in zip(records, values, strict=True):
                value = float(score) * HPS_SCALE
                if not math.isfinite(value):
                    raise ValueError(f"HPS score must be finite: {record['id']}")
                scores.append(
                    {
                        "job_id": record["id"],
                        "metric": "hps_v2_0_x100",
                        "value": value,
                        "evaluator": "hpsv2",
                        "revision": revision,
                    }
                )

        csv_file(output, SCORE_FIELDS, scores)
