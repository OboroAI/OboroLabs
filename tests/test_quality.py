"""Verify evaluator CSV validation, coverage, and paired comparisons."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from imagebench.constants.benchmark import COLD
from imagebench.quality import load_scores, summarize
from imagebench.types.report import CaseScore, ScoreGroup
from tests.fixtures import job_for, record_for


class QualityTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(self.enterContext(TemporaryDirectory()))
        self.path = directory / "scores.csv"
        self.header = "job_id,metric,value,evaluator,revision\n"
        self.records = [
            record_for(job_for("candidate", "cube"), 2.0),
            record_for(job_for("reference", "cube", phase=COLD), 4.0),
        ]

    def write_scores(self, rows: str) -> None:
        """Write fixture rows using the documented CSV contract."""
        self.path.write_text(self.header + rows, encoding="utf-8")

    def test_reads_finite_scores_and_strips_evaluator_labels(self) -> None:
        self.write_scores("candidate__cube__warm, metric ,-1.25, tool , v1 \n")
        scores = load_scores(self.path, self.records)

        self.assertEqual(
            scores, {ScoreGroup("candidate", 64, 64, "metric", "tool", "v1"): {"cube": CaseScore(-1.25, 2)}}
        )

    def test_requires_all_score_columns(self) -> None:
        self.path.write_text("job_id,metric,value,evaluator\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "scores CSV needs"):
            load_scores(self.path, self.records)

    def test_rejects_scores_for_unknown_or_cold_jobs(self) -> None:
        for job_id in ("missing__cube__warm", "reference__cube__cold"):
            with self.subTest(job_id=job_id):
                self.write_scores(f"{job_id},metric,1,tool,v1\n")
                with self.assertRaisesRegex(ValueError, "score line 2: unknown completed warm job"):
                    load_scores(self.path, self.records)

    def test_rejects_blank_evaluator_revision(self) -> None:
        self.write_scores("candidate__cube__warm,metric,3,tool, \n")
        with self.assertRaisesRegex(ValueError, "score line 2: missing metric, evaluator or revision"):
            load_scores(self.path, self.records)

    def test_rejects_non_finite_scores(self) -> None:
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                self.write_scores(f"candidate__cube__warm,metric,{value},tool,v1\n")
                with self.assertRaisesRegex(ValueError, "score line 2: score must be finite"):
                    load_scores(self.path, self.records)

    def test_rejects_duplicate_scores_after_trimming_labels(self) -> None:
        self.write_scores("candidate__cube__warm,metric,3,tool,v1\ncandidate__cube__warm, metric ,4, tool , v1 \n")
        with self.assertRaisesRegex(ValueError, "score line 3: duplicate score"):
            load_scores(self.path, self.records)

    def test_compares_only_shared_cases_with_the_same_size_and_evaluator_revision(self) -> None:
        records = [
            record_for(job_for("candidate", "cube"), 2.0),
            record_for(job_for("reference", "cube"), 4.0),
            record_for(job_for("candidate", "boats"), 6.0),
            record_for(job_for("reference", "boats"), 10.0),
            record_for(job_for("candidate", "forest"), 100.0),
            record_for(job_for("reference", "forest"), 100.0),
            record_for(job_for("candidate", "river"), 100.0),
            record_for(job_for("reference", "river", width=32), 100.0),
            record_for(job_for("candidate", "unscored"), 1.0),
        ]
        self.write_scores(
            "candidate__cube__warm,metric,7,tool,v1\n"
            "reference__cube__warm,metric,4,tool,v1\n"
            "candidate__boats__warm,metric,5,tool,v1\n"
            "reference__boats__warm,metric,6,tool,v1\n"
            "candidate__forest__warm,metric,9,tool,v1\n"
            "reference__forest__warm,metric,1,tool,v2\n"
            "candidate__river__warm,metric,3,tool,v1\n"
            "reference__river__warm,metric,8,tool,v1\n"
        )
        scores = load_scores(self.path, records)
        quality, pairs = summarize(scores, records, reference="reference")

        self.assertEqual(len(quality), 4)
        candidate = quality[0]
        self.assertEqual((candidate["profile"], candidate["n_scored"], candidate["n_generated"]), ("candidate", 4, 5))
        self.assertEqual(candidate["mean"], 6)
        (pair,) = pairs
        self.assertEqual((pair["n_pairs"], pair["n_scored"], pair["reference_n_scored"]), (2, 4, 2))
        self.assertEqual(pair["mean_delta"], 1)
        self.assertEqual((pair["median_s"], pair["reference_median_s"], pair["speed_ratio"]), (4, 7, 1.75))
        self.assertEqual(summarize(scores, records), (quality, []))
