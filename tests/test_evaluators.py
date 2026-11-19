"""Exercise evaluator artifacts with verified run fixtures."""

import csv
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imagebench.constants.benchmark import COLD
from imagebench.evaluators.compbench import export_compbench, import_compbench
from imagebench.evaluators.hps import evaluate_hps
from imagebench.evaluators.ocr import evaluate_ocr
from imagebench.plan import load, make_jobs
from imagebench.quality import load_scores
from imagebench.storage import json_bytes, load_record, prepare_run, save_record, sha
from imagebench.types.benchmark import RunManifest
from imagebench.types.comfy import ImageResult
from tests.fixtures import pixel_png


class EvaluatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        example = Path(__file__).resolve().parents[1] / "examples" / "config.json"
        plan, template = load(example)
        for case in plan["cases"]:
            case["width"] = 64
            case["height"] = 64
        workflow = json_bytes(template)
        manifest: RunManifest = {
            **plan,
            "workflow_sha256": sha(workflow),
            "backend": "comfyui_http",
            "server_sha256": sha(b"fixture-server"),
            "poll_interval_s": 0.1,
        }
        prepare_run(self.directory, manifest, workflow)

        self.jobs = list(make_jobs(plan)) + list(make_jobs(plan, COLD, "candidate", "cube"))
        self.png = pixel_png(64, 64)
        for job in self.jobs:
            save_record(self.directory, job, ImageResult(self.png, 2.0, 0.25))
        self.references = self.directory / "references.csv"
        self.scores = self.directory / "scores.csv"
        self.prompts = self.directory / "prompts.txt"
        self.prompts.write_text(plan["cases"][0]["prompt"] + "\n", encoding="utf-8")
        self.bundle = self.directory / "compbench"

    def test_ocr_normalizes_text_and_preserves_original_recognition(self) -> None:
        self.references.write_text("case_id,language,text\ncube,rus,ЗЕЛЁНАЯ ДОЛИНА\n", encoding="utf-8")
        with patch("imagebench.evaluators.ocr.subprocess.run") as run:
            run.side_effect = [
                subprocess.CompletedProcess([], 0, "tesseract 5.3.4\n", ""),
                subprocess.CompletedProcess([], 0, "зелёная\u3000долина\n", ""),
                subprocess.CompletedProcess([], 0, "ЗЕЛЕНАЯ ДОЛИНА\n", ""),
            ]
            evaluate_ocr(self.directory, self.references, self.scores)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args_list[1].args[0][2:], ["stdout", "-l", "rus", "--oem", "1", "--psm", "7"])

        with self.scores.open(newline="", encoding="utf-8") as stream:
            values = {(row["job_id"], row["metric"]): float(row["value"]) for row in csv.DictReader(stream)}
        self.assertEqual(
            values,
            {
                ("candidate__cube__warm", "ocr_exact"): 1,
                ("candidate__cube__warm", "ocr_cer"): 0,
                ("reference__cube__warm", "ocr_exact"): 0,
                ("reference__cube__warm", "ocr_cer"): 1 / len("зелёная долина"),
            },
        )
        evidence = json.loads(self.scores.with_name("scores.csv.raw.json").read_bytes())
        self.assertEqual(evidence["revision"], "tesseract 5.3.4 / single-line-v1")
        self.assertEqual(evidence["rows"][0]["recognized"], "зелёная\u3000долина\n")

    def test_ocr_rejects_reference_without_completed_warm_case(self) -> None:
        self.references.write_text("case_id,language,text\nunknown,eng,LABEL\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no completed warm job for OCR cases: unknown"):
            evaluate_ocr(self.directory, self.references, self.scores)
        self.assertFalse(self.scores.exists())

    def test_compbench_maps_reordered_scores_to_verified_warm_jobs(self) -> None:
        export_compbench(self.directory, self.prompts, self.bundle)

        prompt = self.prompts.read_text(encoding="utf-8").strip()
        self.assertEqual(
            sorted(path.name for path in (self.bundle / "samples").iterdir()),
            [f"{prompt}_000000.png", f"{prompt}_000001.png"],
        )
        self.assertEqual((self.bundle / "samples" / f"{prompt}_000000.png").read_bytes(), self.png)
        result = self.bundle / "annotation_clip" / "vqa_result.json"
        result.parent.mkdir()
        result.write_bytes(
            json_bytes(
                [
                    {"question_id": 1, "answer": 0.23},
                    {"question_id": 0, "answer": 0.35},
                ]
            )
        )

        import_compbench(self.bundle, self.scores)
        records = [record for job in self.jobs if (record := load_record(self.directory, job)) is not None]
        scores = load_scores(self.scores, records)
        self.assertEqual(
            {group.profile: values["cube"].value for group, values in scores.items()},
            {"candidate": 0.35, "reference": 0.23},
        )
        self.assertEqual({group.metric for group in scores}, {"non_spatial_clipscore"})

    def test_compbench_rejects_incomplete_result(self) -> None:
        export_compbench(self.directory, self.prompts, self.bundle)
        result = self.bundle / "annotation_clip" / "vqa_result.json"
        result.parent.mkdir()
        result.write_bytes(json_bytes([{"question_id": 0, "answer": 0.35}]))
        with self.assertRaisesRegex(ValueError, "CompBench scores missing for question IDs: 1"):
            import_compbench(self.bundle, self.scores)
        self.assertFalse(self.scores.exists())

    def test_hps_passes_exact_prompts_and_scales_scores(self) -> None:
        checkpoint = self.directory / "HPS_v2_compressed.pt"
        checkpoint.write_bytes(b"fixture checkpoint")
        with (
            patch("imagebench.evaluators.hps.HPS_CHECKPOINT_SHA256", sha(checkpoint.read_bytes())),
            patch("imagebench.evaluators.hps.version", return_value="1.2.0"),
            patch("imagebench.evaluators.hps.import_module") as import_module,
        ):
            score = import_module.return_value.score
            score.side_effect = [[0.25, 0.5], [0.125, 0.25]]
            evaluate_hps(self.directory, checkpoint, self.scores)

        import_module.assert_called_once_with("hpsv2.img_score")
        self.assertEqual(score.call_count, 2)
        self.assertEqual(score.call_args_list[0].args[1], self.jobs[0]["prompt"])
        self.assertEqual(score.call_args_list[0].kwargs, {"cp": str(checkpoint), "hps_version": "v2.0"})
        with self.scores.open(newline="", encoding="utf-8") as stream:
            values = {row["job_id"]: float(row["value"]) for row in csv.DictReader(stream)}
        self.assertEqual(
            values,
            {
                "candidate__cube__warm": 25,
                "reference__cube__warm": 50,
                "candidate__boats__warm": 12.5,
                "reference__boats__warm": 25,
            },
        )

    def test_hps_rejects_unrecognized_checkpoint_before_scoring(self) -> None:
        checkpoint = self.directory / "HPS_v2_compressed.pt"
        checkpoint.write_bytes(b"different checkpoint")
        with patch("imagebench.evaluators.hps.import_module") as import_module:
            with self.assertRaisesRegex(ValueError, "checkpoint SHA-256 differs"):
                evaluate_hps(self.directory, checkpoint, self.scores)
            import_module.return_value.score.assert_not_called()
        self.assertFalse(self.scores.exists())
