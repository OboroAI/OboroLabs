"""JSON workflow values and image results returned by ComfyUI."""

from dataclasses import dataclass
from typing import TypeAlias

JSONValue: TypeAlias = dict[str, "JSONValue"] | list["JSONValue"] | str | int | float | bool | None
Workflow: TypeAlias = dict[str, JSONValue]


@dataclass(frozen=True)
class ImageResult:
    """Image bytes and the two independent HTTP measurements."""

    png: bytes
    latency_s: float
    image_fetch_s: float
