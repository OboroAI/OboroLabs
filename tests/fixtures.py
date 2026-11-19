"""Job, record, and PNG fixtures shared by benchmark tests."""

import struct
import zlib

from imagebench.constants.benchmark import WARM
from imagebench.types.benchmark import Job, Phase, Record


def job_for(profile: str, case_id: str, *, width: int = 64, phase: Phase = WARM) -> Job:
    """Build a job with a predictable ID, seed, and image size."""
    return {
        "id": f"{profile}__{case_id}__{phase}",
        "profile": profile,
        "case_id": case_id,
        "phase": phase,
        "checkpoint": f"{profile}.safetensors",
        "steps": 4,
        "prompt": f"Fixture prompt for {case_id}",
        "seed": 41,
        "width": width,
        "height": 64,
    }


def record_for(job: Job, latency_s: float) -> Record:
    """Build a record for report calculations that require no image on disk."""
    return {
        **job,
        "cache_condition": "primed" if job["phase"] == WARM else "operator_fresh_server",
        "latency_s": latency_s,
        "image_fetch_s": 0.05,
        "png": f"images/{job['id']}.png",
        "png_sha256": "0" * 64,
    }


def pixel_png(width: int, height: int) -> bytes:
    """Build a grayscale PNG with the dimensions requested by a fixture job."""

    def chunk(name: bytes, value: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(name + value))
        return struct.pack(">I", len(value)) + name + value + crc

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    # Each grayscale scanline starts with a filter byte before the pixel data.
    rows = bytes((width + 1) * height)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")
