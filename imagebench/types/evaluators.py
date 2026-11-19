"""Inputs and per-image output shared by evaluator adapters."""

from typing import NamedTuple, TypedDict


class OCRReference(NamedTuple):
    """Expected single line and its Tesseract language code."""

    language: str
    text: str


class ScoreRow(TypedDict):
    """One evaluator result in the portable scores CSV format."""

    job_id: str
    metric: str
    value: float
    evaluator: str
    revision: str
