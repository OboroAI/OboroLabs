"""Plan limits and persisted run identifiers."""

import re
from typing import Final

WARM: Final = "warm"
COLD: Final = "cold"
SCHEMA_VERSION = 1
MAX_SEED = 2**64 - 1
MAX_DIMENSION = 32768
MAX_STEPS = 10000
ITEM_ID_PATTERN = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
SHA256_PATTERN = re.compile(r"[a-f0-9]{64}")

MANIFEST_NAME = "manifest.json"
WORKFLOW_NAME = "workflow.api.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
