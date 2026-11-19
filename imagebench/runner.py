"""Coordinate job selection, warm-up, and resumable benchmark execution."""

from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from imagebench.comfy import Comfy
from imagebench.constants.benchmark import COLD, WARM
from imagebench.plan import make_jobs, primer_seed
from imagebench.storage import json_bytes, load_record, prepare_run, save_record, sha, validate_png, writer
from imagebench.types.benchmark import Job, Phase, Plan, RunManifest
from imagebench.types.comfy import Workflow

__all__ = ["run"]


def _pending_groups(directory: Path, jobs: Sequence[Job]) -> list[list[Job]]:
    groups: dict[tuple[str, int, int], list[Job]] = defaultdict(list)
    # Verify all selected records before sending any new work to the server.
    for job in jobs:
        if load_record(directory, job) is None:
            group = (job["profile"], job["width"], job["height"])
            groups[group].append(job)
    return list(groups.values())


def _prime(backend: Comfy, job: Job, seed: int) -> None:
    primer: Job = {**job, "seed": seed}
    image = backend.render(primer)
    validate_png(image.png, primer["width"], primer["height"])


def run(
    plan: Plan,
    template: Workflow,
    directory: Path,
    server: str,
    phase: Phase,
    profile: str | None,
    case: str | None,
    timeout: int,
) -> None:
    """Resume verified jobs and generate each remaining profile and size group."""
    backend = Comfy(server, template, plan["output_node"], timeout=timeout)
    workflow = json_bytes(template)
    manifest: RunManifest = {
        **plan,
        "workflow_sha256": sha(workflow),
        "backend": "comfyui_http",
        "server_sha256": sha(backend.server.encode("utf-8")),
        "poll_interval_s": backend.poll,
    }
    jobs = list(make_jobs(plan, phase, profile, case))
    if phase == COLD and len(jobs) != 1:
        raise ValueError("a process-cold sample needs exactly one profile and case")

    with writer(directory):
        prepare_run(directory, manifest, workflow)
        groups = _pending_groups(directory, jobs)
        warm_seed = primer_seed(plan) if phase == WARM and groups else None
        for group in groups:
            if warm_seed is not None:
                # Warm up each pending profile and size, even on partial resume.
                _prime(backend, group[0], warm_seed)
            for job in group:
                result = backend.render(job)
                save_record(directory, job, result)
                print(f"{job['id']} {result.latency_s:.3f} s", flush=True)

        reused = len(jobs) - sum(len(group) for group in groups)
        print(f"{reused} complete jobs reused")
