"""Exchange verified images and non-spatial scores with upstream T2I-CompBench++."""

import csv
import math
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

from imagebench.constants.evaluators import (
    COMPBENCH_INDEX,
    COMPBENCH_INDEX_FIELDS,
    COMPBENCH_METRIC,
    COMPBENCH_REVISION,
)
from imagebench.constants.report import SCORE_FIELDS
from imagebench.evaluators.records import warm_records
from imagebench.storage import csv_file, read_json, writer
from imagebench.types.evaluators import ScoreRow


def export_compbench(directory: Path, prompts_path: Path, bundle: Path) -> None:
    """Stage warm images and a question-ID map for the upstream CLIP script."""
    prompts = set(prompts_path.read_text(encoding="utf-8").splitlines())
    with writer(directory):
        records = [record for record in warm_records(directory) if record["prompt"] in prompts]
        if not records:
            raise ValueError("no completed warm jobs match the CompBench prompt list")

        image_names = []
        for question_id, record in enumerate(records):
            prompt = record["prompt"]
            # Upstream splits at the first underscore and sorts by the numeric suffix.
            if not prompt or any(character in prompt for character in ("_", "/", "\\", "\0")):
                raise ValueError(f"prompt cannot be used as a CompBench filename: {prompt!r}")
            image_names.append(f"{prompt}_{question_id:06d}.png")

        if bundle.exists():
            raise FileExistsError(f"CompBench output directory already exists: {bundle}")
        bundle.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=bundle.parent) as temporary:
            staging = Path(temporary) / "bundle"
            samples = staging / "samples"
            samples.mkdir(parents=True)
            index = []
            for question_id, (record, name) in enumerate(zip(records, image_names, strict=True)):
                copyfile(directory / record["png"], samples / name)
                index.append({"question_id": question_id, "job_id": record["id"]})

            csv_file(staging / COMPBENCH_INDEX, COMPBENCH_INDEX_FIELDS, index)
            staging.rename(bundle)


def _read_index(bundle: Path) -> dict[int, str]:
    jobs = {}
    with (bundle / COMPBENCH_INDEX).open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            question_id = int(row["question_id"])
            if question_id in jobs:
                raise ValueError(f"duplicate CompBench index question ID {question_id}")
            jobs[question_id] = row["job_id"]
    if not jobs:
        raise ValueError("CompBench bundle has no indexed jobs")
    return jobs


def import_compbench(bundle: Path, output: Path) -> None:
    """Join full upstream per-image scores to job IDs and write an evaluator CSV."""
    jobs = _read_index(bundle)
    raw = read_json(bundle / "annotation_clip" / "vqa_result.json")
    if not isinstance(raw, list):
        raise ValueError("CompBench result must contain a list of question IDs and scores")

    scores: list[ScoreRow] = []
    seen: set[int] = set()
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("CompBench result entry must be an object")
        question_id = row.get("question_id")
        if type(question_id) is not int or question_id not in jobs or question_id in seen:
            raise ValueError(f"unexpected or duplicate CompBench question ID {question_id!r}")
        value = row.get("answer")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError(f"CompBench question {question_id} needs a finite score")
        seen.add(question_id)
        scores.append(
            {
                "job_id": jobs[question_id],
                "metric": COMPBENCH_METRIC,
                "value": value,
                "evaluator": "T2I-CompBench++",
                "revision": f"{COMPBENCH_REVISION} / ViT-B/32",
            }
        )

    if missing := jobs.keys() - seen:
        raise ValueError(f"CompBench scores missing for question IDs: {', '.join(map(str, sorted(missing)))}")

    csv_file(output, SCORE_FIELDS, scores)
