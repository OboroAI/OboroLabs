"""Evaluator protocols and artifact formats."""

OCR_REFERENCE_FIELDS = ("case_id", "language", "text")
OCR_ENGINE_MODE = "1"
OCR_PAGE_MODE = "7"
OCR_TIMEOUT_S = 60
OCR_PROTOCOL = "single-line-v1"

COMPBENCH_REVISION = "4aa404212eb5d06e5adbcd9cee696c750d0d25a5"
COMPBENCH_INDEX = "jobs.csv"
COMPBENCH_INDEX_FIELDS = ("question_id", "job_id")
COMPBENCH_METRIC = "non_spatial_clipscore"

HPS_MODEL_VERSION = "v2.0"
HPS_CHECKPOINT_REVISION = "697403c78157020a1ae59d23f111aa58ced35b0a"
HPS_CHECKPOINT_SHA256 = "07cb0d20626232204ca3a6ec53ff5984e7e53212a8a7b0e0ec2bac1bdaf125a1"
HPS_SCALE = 100
