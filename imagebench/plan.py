"""Validate benchmark configuration and expand profiles into paired jobs."""

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import cast

from imagebench.constants.benchmark import (
    ITEM_ID_PATTERN,
    MAX_DIMENSION,
    MAX_SEED,
    MAX_STEPS,
    SCHEMA_VERSION,
    SHA256_PATTERN,
    WARM,
)
from imagebench.types.benchmark import Case, Job, Phase, Plan, Profile
from imagebench.types.comfy import Workflow
from imagebench.workflow import load_workflow, substitute

__all__ = ["load", "make_jobs", "primer_seed", "substitute"]


def _config_items(config: Mapping[str, object], key: str) -> Iterator[dict[str, object]]:
    items = config.get(key)
    if not isinstance(items, list) or not items:
        raise ValueError(f"{key} must be a non-empty list")

    ids: set[str] = set()
    for item in items:
        name = item.get("id") if isinstance(item, dict) else None
        if not isinstance(name, str) or not ITEM_ID_PATTERN.fullmatch(name) or name in ids:
            raise ValueError(f"{key} need unique lowercase ids: {name!r}")
        ids.add(name)
    # Validate all IDs before reading fields so malformed lists get one clear error.
    yield from items


def _required_string(item: Mapping[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _bounded_integer(item: Mapping[str, object], key: str, minimum: int, maximum: int) -> int:
    value = item.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{item['id']}: {key} must be in [{minimum}, {maximum}]")
    return value


def _load_cases(config: Mapping[str, object]) -> list[Case]:
    cases = []
    seen: set[tuple[str, int, int, int]] = set()
    for case in _config_items(config, "cases"):
        inputs = (
            _required_string(case, "prompt"),
            _bounded_integer(case, "seed", 0, MAX_SEED),
            _bounded_integer(case, "width", 1, MAX_DIMENSION),
            _bounded_integer(case, "height", 1, MAX_DIMENSION),
        )
        if inputs in seen:
            raise ValueError(f"{case['id']}: duplicate prompt, seed and size")
        seen.add(inputs)
        cases.append(cast(Case, case))
    return cases


def _load_profiles(config: Mapping[str, object]) -> list[Profile]:
    profiles = []
    for profile in _config_items(config, "profiles"):
        _required_string(profile, "checkpoint")
        _bounded_integer(profile, "steps", 1, MAX_STEPS)
        if "sha256" in profile and not SHA256_PATTERN.fullmatch(str(profile["sha256"])):
            raise ValueError(f"{profile['id']}: invalid checkpoint SHA-256")
        # Keep optional metadata in the manifest for identity checks on resume.
        profiles.append(cast(Profile, profile))
    return profiles


def load(path: str | Path) -> tuple[Plan, Workflow]:
    """Load a validated plan and resolve its workflow relative to the config."""
    config_path = Path(path)
    config: object = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    cases = _load_cases(config)
    profiles = _load_profiles(config)
    workflow_path = config_path.parent / _required_string(config, "workflow")
    output_node = _required_string(config, "output_node")
    template = load_workflow(workflow_path, output_node)

    plan: Plan = {
        "schema": SCHEMA_VERSION,
        "runtime": _required_string(config, "runtime"),
        "output_node": output_node,
        "profiles": profiles,
        "cases": cases,
    }
    return plan, template


def make_jobs(
    plan: Plan,
    phase: Phase = WARM,
    profile: str | None = None,
    case: str | None = None,
) -> Iterator[Job]:
    """Yield jobs in profile order and case order, optionally filtering either."""
    profiles = [item for item in plan["profiles"] if profile is None or item["id"] == profile]
    cases = [item for item in plan["cases"] if case is None or item["id"] == case]
    if not profiles or not cases:
        raise ValueError("unknown profile or case")

    for selected_profile in profiles:
        profile_id = selected_profile["id"]
        for selected_case in cases:
            case_id = selected_case["id"]
            yield {
                "id": f"{profile_id}__{case_id}__{phase}",
                "profile": profile_id,
                "case_id": case_id,
                "phase": phase,
                "checkpoint": selected_profile["checkpoint"],
                "steps": selected_profile["steps"],
                "prompt": selected_case["prompt"],
                "seed": selected_case["seed"],
                "width": selected_case["width"],
                "height": selected_case["height"],
            }


def primer_seed(plan: Plan) -> int:
    """Pick a seed outside the entire case set to avoid priming a timed sample."""
    case_seeds = {case["seed"] for case in plan["cases"]}
    seed = 0
    while seed in case_seeds:
        seed += 1
    return seed
