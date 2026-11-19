"""Validate ComfyUI workflow placeholders and bind a job to the graph."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from imagebench.constants.comfy import WORKFLOW_TOKENS
from imagebench.types.benchmark import Job
from imagebench.types.comfy import JSONValue, Workflow

__all__ = ["bind_workflow", "load_workflow", "substitute"]


def load_workflow(path: Path, output_node: str) -> Workflow:
    """Read the API graph and check the requested output and bindable values."""
    graph: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or output_node not in graph:
        raise ValueError("output_node must name a node in the API workflow")

    template = cast(Workflow, graph)
    seen: set[str] = set()

    def record_token(token: str) -> str:
        name = token[1:]
        if name not in WORKFLOW_TOKENS:
            raise ValueError(f"unknown workflow placeholder {token}")
        seen.add(name)
        return token

    # Check the same whole-string placeholders that binding will replace.
    substitute(template, record_token)
    if missing := WORKFLOW_TOKENS - seen:
        raise ValueError(f"workflow is missing placeholders: {', '.join(sorted(missing))}")
    return template


def substitute(value: JSONValue, replace: Callable[[str], JSONValue]) -> JSONValue:
    """Replace whole-string placeholders while retaining JSON value types."""
    if isinstance(value, dict):
        return {key: substitute(entry, replace) for key, entry in value.items()}
    if isinstance(value, list):
        return [substitute(entry, replace) for entry in value]
    if isinstance(value, str) and value.startswith("$"):
        return replace(value)
    return value


def bind_workflow(template: Workflow, job: Job, filename: str) -> Workflow:
    """Build a fresh graph for a submission without changing the saved template."""
    # ComfyUI expects numeric inputs to stay numeric after binding.
    values: dict[str, JSONValue] = {**cast(dict[str, JSONValue], job), "filename": filename}
    return {node: substitute(value, lambda token: values[token[1:]]) for node, value in template.items()}
