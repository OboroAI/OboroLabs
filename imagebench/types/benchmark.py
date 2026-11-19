"""The validated plan and the run schemas shared by execution and reporting."""

from typing import Literal, TypeAlias, TypedDict

Phase: TypeAlias = Literal["warm", "cold"]


class Profile(TypedDict):
    """One checkpoint and sampler setting."""

    id: str
    checkpoint: str
    steps: int


class Case(TypedDict):
    """An input shared by every selected profile."""

    id: str
    prompt: str
    seed: int
    width: int
    height: int


class Plan(TypedDict):
    """Configuration preserved in the run manifest."""

    schema: int
    runtime: str
    output_node: str
    profiles: list[Profile]
    cases: list[Case]


class Job(TypedDict):
    """A single planned generation and its stable record ID."""

    id: str
    profile: str
    case_id: str
    phase: Phase
    checkpoint: str
    steps: int
    prompt: str
    seed: int
    width: int
    height: int


class RunManifest(Plan):
    """The plan plus the workflow and backend identity used for resume."""

    workflow_sha256: str
    backend: str
    server_sha256: str
    poll_interval_s: float


class Record(Job):
    """A completed job with timing and image integrity metadata."""

    cache_condition: str
    latency_s: float
    image_fetch_s: float
    png: str
    png_sha256: str
