"""Config validation, job expansion, and ComfyUI graph binding."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from imagebench.constants.benchmark import COLD
from imagebench.plan import load, make_jobs, primer_seed
from imagebench.workflow import bind_workflow


class PlanTest(unittest.TestCase):
    def setUp(self) -> None:
        examples = Path(__file__).resolve().parents[1] / "examples"
        directory = Path(self.enterContext(TemporaryDirectory()))
        self.config_path = directory / "config.json"
        self.workflow_path = directory / "workflow.api.json"
        self.config: dict[str, Any] = json.loads((examples / "config.json").read_text(encoding="utf-8"))
        self.graph: dict[str, Any] = json.loads((examples / "workflow.api.json").read_text(encoding="utf-8"))

    def write_inputs(self) -> None:
        """Save the config and graph after making test-specific changes."""
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.workflow_path.write_text(json.dumps(self.graph), encoding="utf-8")

    def test_expands_jobs_in_profile_and_case_order(self) -> None:
        self.write_inputs()
        plan, _ = load(self.config_path)

        self.assertEqual(
            [job["id"] for job in make_jobs(plan)],
            ["candidate__cube__warm", "candidate__boats__warm", "reference__cube__warm", "reference__boats__warm"],
        )
        (selected,) = make_jobs(plan, phase=COLD, profile="reference", case="boats")
        self.assertEqual(selected["id"], "reference__boats__cold")
        self.assertEqual(selected["steps"], self.config["profiles"][1]["steps"])
        self.assertEqual(selected["seed"], self.config["cases"][1]["seed"])

    def test_rejects_unknown_profile_or_case(self) -> None:
        self.write_inputs()
        plan, _ = load(self.config_path)
        for profile, case in (("unknown", "cube"), ("candidate", "unknown")):
            with self.subTest(profile=profile, case=case):
                with self.assertRaisesRegex(ValueError, "unknown profile or case"):
                    list(make_jobs(plan, profile=profile, case=case))

    def test_primer_seed_is_free_across_the_plan(self) -> None:
        self.config["cases"][0]["seed"] = 0
        self.config["cases"][1]["seed"] = 1
        self.write_inputs()
        plan, _ = load(self.config_path)
        self.assertEqual(primer_seed(plan), 2)

    def test_rejects_duplicate_case_inputs(self) -> None:
        self.config["cases"].append({**self.config["cases"][0], "id": "duplicate"})
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, "duplicate prompt, seed and size"):
            load(self.config_path)

    def test_rejects_duplicate_profile_ids(self) -> None:
        self.config["profiles"][1]["id"] = self.config["profiles"][0]["id"]
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, "profiles need unique lowercase ids"):
            load(self.config_path)

    def test_rejects_boolean_seed(self) -> None:
        self.config["cases"][0]["seed"] = True
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, "seed must be in"):
            load(self.config_path)

    def test_retains_checkpoint_metadata(self) -> None:
        self.config["profiles"][0].update(revision="fixture-v1", sha256="a" * 64)
        self.write_inputs()
        plan, _ = load(self.config_path)
        self.assertEqual(plan["profiles"][0], self.config["profiles"][0])

    def test_rejects_invalid_checkpoint_hash(self) -> None:
        self.config["profiles"][0]["sha256"] = "A" * 64
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, "invalid checkpoint SHA-256"):
            load(self.config_path)

    def test_rejects_unknown_workflow_output_node(self) -> None:
        self.config["output_node"] = "999"
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, "output_node must name a node"):
            load(self.config_path)

    def test_rejects_unknown_workflow_placeholder(self) -> None:
        self.graph["3"]["inputs"]["cfg"] = "$unknown"
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, r"unknown workflow placeholder \$unknown"):
            load(self.config_path)

    def test_rejects_missing_workflow_placeholder(self) -> None:
        self.graph["3"]["inputs"]["seed"] = 42
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, "workflow is missing placeholders: seed"):
            load(self.config_path)

    def test_binds_nested_placeholders_without_mutating_template(self) -> None:
        self.graph["fixture"] = ["$seed", {"steps": "$steps", "note": "keep $seed literal"}]
        self.write_inputs()
        plan, template = load(self.config_path)
        job = next(make_jobs(plan))

        graph = bind_workflow(template, job, "imagebench/fixture")
        self.assertEqual(graph["fixture"], [job["seed"], {"steps": job["steps"], "note": "keep $seed literal"}])
        self.assertEqual(
            graph["5"],
            {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": job["width"],
                    "height": job["height"],
                    "batch_size": 1,
                },
            },
        )
        self.assertEqual(template, self.graph)
