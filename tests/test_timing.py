"""Verify percentile interpolation and per-group timing summaries."""

import unittest

from imagebench.constants.benchmark import COLD, WARM
from imagebench.timing import percentile, summarize_timing
from tests.fixtures import job_for, record_for


class TimingTest(unittest.TestCase):
    def test_interpolates_percentile_across_sorted_samples(self) -> None:
        samples = [8.0, 2.0, 4.0]

        self.assertEqual(percentile(samples, 0), 2.0)
        self.assertEqual(percentile(samples, 0.5), 4.0)
        self.assertAlmostEqual(percentile(samples, 0.95), 7.6)
        self.assertEqual(percentile(samples, 1), 8.0)

    def test_groups_by_phase_profile_and_size(self) -> None:
        records = [
            record_for(job_for("candidate", "boats"), 3.0),
            record_for(job_for("reference", "cube"), 5.0),
            record_for(job_for("candidate", "river", width=32), 2.0),
            record_for(job_for("candidate", "cube", phase=COLD), 6.0),
            record_for(job_for("candidate", "cube"), 1.0),
        ]

        cold, small, candidate, reference = summarize_timing(records)
        self.assertEqual((cold["phase"], cold["n"], cold["p95_s"]), (COLD, 1, None))
        self.assertEqual((small["width"], small["height"], small["p95_s"]), (32, 64, None))
        self.assertEqual((candidate["phase"], candidate["n"], candidate["median_s"]), (WARM, 2, 2))
        assert candidate["p95_s"] is not None
        self.assertAlmostEqual(candidate["p95_s"], 2.9)
        self.assertEqual(candidate["images_per_min"], 30)
        self.assertEqual((reference["profile"], reference["median_s"]), ("reference", 5))
