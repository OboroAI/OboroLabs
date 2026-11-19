"""CSV column order and timing conventions for exported reports."""

RECORD_FIELDS = (
    "id",
    "profile",
    "case_id",
    "phase",
    "checkpoint",
    "steps",
    "prompt",
    "seed",
    "width",
    "height",
    "cache_condition",
    "latency_s",
    "image_fetch_s",
    "png",
    "png_sha256",
)
TIMING_FIELDS = ("phase", "profile", "width", "height", "n", "median_s", "p95_s", "images_per_min")
SCORE_FIELDS = ("job_id", "metric", "value", "evaluator", "revision")
SCORE_GROUP_FIELDS = ("profile", "width", "height", "metric", "evaluator", "revision")
QUALITY_FIELDS = (*SCORE_GROUP_FIELDS, "n_scored", "n_generated", "mean")
PAIR_FIELDS = (
    *SCORE_GROUP_FIELDS,
    "reference",
    "n_pairs",
    "n_scored",
    "reference_n_scored",
    "mean_delta",
    "median_s",
    "reference_median_s",
    "speed_ratio",
)

TAIL_PERCENTILE = 0.95
SECONDS_PER_MINUTE = 60
