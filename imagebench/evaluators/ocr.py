"""Score single-line text rendering with Tesseract and character error rate."""

import csv
import subprocess
import unicodedata
from pathlib import Path

from imagebench.constants.evaluators import (
    OCR_ENGINE_MODE,
    OCR_PAGE_MODE,
    OCR_PROTOCOL,
    OCR_REFERENCE_FIELDS,
    OCR_TIMEOUT_S,
)
from imagebench.constants.report import SCORE_FIELDS
from imagebench.evaluators.records import warm_records
from imagebench.storage import atomic, csv_file, json_bytes, writer
from imagebench.types.evaluators import OCRReference, ScoreRow


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _edit_distance(expected: str, observed: str) -> int:
    # Two rows suffice because each edit only depends on adjacent prefixes.
    previous = list(range(len(observed) + 1))
    for index, reference_char in enumerate(expected, start=1):
        current = [index]
        for offset, recognized_char in enumerate(observed, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[offset] + 1,
                    previous[offset - 1] + (reference_char != recognized_char),
                )
            )
        previous = current
    return previous[-1]


def _load_references(path: Path) -> dict[str, OCRReference]:
    references: dict[str, OCRReference] = {}
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not set(OCR_REFERENCE_FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("OCR references CSV needs " + ", ".join(OCR_REFERENCE_FIELDS))

        for line, row in enumerate(reader, start=2):
            case_id = (row["case_id"] or "").strip()
            language = (row["language"] or "").strip()
            text = _normalize(row["text"] or "")
            if not (case_id and language and text):
                raise ValueError(f"OCR reference line {line}: case ID, language and text are required")
            if case_id in references:
                raise ValueError(f"OCR reference line {line}: duplicate case {case_id}")
            references[case_id] = OCRReference(language, row["text"])

    if not references:
        raise ValueError("OCR references CSV is empty")
    return references


def _tesseract(*args: str) -> str:
    try:
        result = subprocess.run(
            ["tesseract", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=OCR_TIMEOUT_S,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Tesseract is required for OCR. Install it and add it to PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Tesseract timed out") from exc
    if result.returncode:
        raise RuntimeError(f"Tesseract failed: {result.stderr.strip()}")
    return result.stdout


def evaluate_ocr(directory: Path, references_path: Path, output: Path) -> None:
    """Score completed warm jobs and keep the raw recognition for each image."""
    references = _load_references(references_path)
    scores: list[ScoreRow] = []
    evidence: list[dict[str, object]] = []

    with writer(directory):
        records = warm_records(directory)
        missing = references.keys() - {record["case_id"] for record in records}
        if missing:
            raise ValueError(f"no completed warm job for OCR cases: {', '.join(sorted(missing))}")

        engine_version = _tesseract("--version").partition("\n")[0].strip()
        if not engine_version:
            raise RuntimeError("Tesseract returned no version")
        revision = f"{engine_version} / {OCR_PROTOCOL}"
        for record in records:
            reference = references.get(record["case_id"])
            if reference is None:
                continue
            recognized = _tesseract(
                str((directory / record["png"]).resolve()),
                "stdout",
                "-l",
                reference.language,
                "--oem",
                OCR_ENGINE_MODE,
                "--psm",
                OCR_PAGE_MODE,
            )
            expected = _normalize(reference.text)
            observed = _normalize(recognized)
            for metric, value in (
                ("ocr_exact", float(observed == expected)),
                ("ocr_cer", _edit_distance(expected, observed) / len(expected)),
            ):
                scores.append(
                    {
                        "job_id": record["id"],
                        "metric": metric,
                        "value": value,
                        "evaluator": "tesseract",
                        "revision": revision,
                    }
                )
            evidence.append(
                {
                    "job_id": record["id"],
                    "language": reference.language,
                    "expected": reference.text,
                    "recognized": recognized,
                }
            )

        raw_path = output.with_name(output.name + ".raw.json")
        atomic(
            raw_path, json_bytes({"revision": revision, "oem": OCR_ENGINE_MODE, "psm": OCR_PAGE_MODE, "rows": evidence})
        )
        csv_file(output, SCORE_FIELDS, scores)
