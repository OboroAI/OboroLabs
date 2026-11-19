"""Local mock HTTP server. Images and evaluator values here are test fixtures."""

import csv
import json
import subprocess
import sys
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from typing import Any

from tests.fixtures import pixel_png


@contextmanager
def fake_server(*, busy: bool = False) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Serve completed jobs immediately and capture their submitted workflows."""
    submitted_workflows: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass

        def reply(self, data: object) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(data if isinstance(data, bytes) else json.dumps(data).encode())

        def do_POST(self) -> None:
            graph = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["prompt"]
            submitted_workflows.append(graph)
            self.reply({"prompt_id": str(len(submitted_workflows))})

        def do_GET(self) -> None:
            if self.path == "/queue":
                self.reply({"queue_running": [[0, "existing-job"]] if busy else [], "queue_pending": []})
            elif self.path.startswith("/history/"):
                prompt_id = self.path.rsplit("/", 1)[1]
                self.reply(
                    {
                        prompt_id: {
                            "status": {"status_str": "success", "completed": True},
                            "outputs": {"8": {"images": [{"filename": "example.png", "type": "output"}]}},
                        }
                    }
                )
            else:
                latent = submitted_workflows[-1]["5"]["inputs"]
                self.reply(pixel_png(latent["width"], latent["height"]))

    server = ThreadingHTTPServer(("localhost", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://localhost:{server.server_port}", submitted_workflows
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class BenchmarkTest(unittest.TestCase):
    """Exercise the CLI against the fixture HTTP server and a real run directory."""

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.config = self.project_root / "examples/config.json"
        self.output = self.directory / "run"

    def invoke(self, *args: str | Path, ok: bool = True) -> subprocess.CompletedProcess[str]:
        """Run the benchmark as a subprocess from the project root."""
        result = subprocess.run(
            [sys.executable, "-m", "imagebench", *map(str, args)],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_run_resume_and_import_scores(self) -> None:
        """Verify the lifecycle of a warm run with a cold sample and scores."""
        with fake_server() as (server, requests):
            output = self.output
            base = ("run", self.config, output, "--server", server)
            self.invoke(*base)
            # Each warm profile starts with the same seed outside the case set.
            seeds = [graph["3"]["inputs"]["seed"] for graph in requests]
            self.assertEqual(seeds, [0, 41, 42, 0, 41, 42])
            self.invoke(*base)
            self.assertEqual(len(requests), 6)

            cold = (*base, "--phase", "cold", "--profile", "reference", "--case", "cube")
            self.assertNotEqual(self.invoke(*cold, ok=False).returncode, 0)
            self.invoke(*cold, "--fresh-server")
            self.assertEqual(len(requests), 7)
            self.assertEqual(len(list((output / "images").glob("*.png"))), 5)

            path = self.directory / "fixture-scores.csv"
            path.write_text(
                "job_id,metric,value,evaluator,revision\n"
                "candidate__cube__warm,fixture,3,test,v1\n"
                "reference__cube__warm,fixture,2,test,v1\n"
                "candidate__boats__warm,fixture,9,test,v1\n"
                "reference__boats__warm,fixture,8,test,v2\n",
                encoding="utf-8",
            )
            self.invoke("report", output, "--scores", path, "--reference", "reference")
            with (output / "report/pairs.csv").open() as stream:
                (row,) = csv.DictReader(stream)
            self.assertEqual(row["n_pairs"], "1")
            self.assertEqual(row["mean_delta"], "1.0")
            # Coverage includes unpaired cases scored with the same revision.
            self.assertEqual(row["n_scored"], "2")
            self.assertEqual(row["reference_n_scored"], "1")
            self.assertIn("Warm jobs complete: 4/4", (output / "report/summary.md").read_text())
            (output / "images/candidate__cube__warm.png").write_bytes(b"broken fixture")
            self.assertIn("missing or changed PNG", self.invoke(*base, ok=False).stderr)
            self.assertEqual(len(requests), 7)

    def test_partial_resume_only_primes_sizes_with_pending_jobs(self) -> None:
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["cases"][1].update(width=320, height=256, seed=0)
        config["workflow"] = str(self.config.parent / config["workflow"])
        config_path = self.directory / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        with fake_server() as (server, requests):
            command = ("run", config_path, self.output, "--server", server, "--profile", "candidate")
            self.invoke(*command, "--case", "cube")
            resumed = self.invoke(*command)

        self.assertIn("1 complete jobs reused", resumed.stdout)
        # The first run completed the 512px group. Resume primes only the 320px group.
        sizes_and_seeds = [(graph["5"]["inputs"]["width"], graph["3"]["inputs"]["seed"]) for graph in requests]
        self.assertEqual(sizes_and_seeds, [(512, 1), (512, 41), (320, 1), (320, 0)])

    def test_busy_server_rejects_submission_before_primer(self) -> None:
        with fake_server(busy=True) as (server, requests):
            failed = self.invoke("run", self.config, self.output, "--server", server, ok=False)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("ComfyUI queue is busy", failed.stderr)
        self.assertEqual(requests, [])
        self.assertEqual(list((self.output / "records").glob("*.json")), [])

    def test_resume_rejects_modified_saved_workflow(self) -> None:
        with fake_server() as (server, requests):
            command = ("run", self.config, self.output, "--server", server, "--profile", "candidate", "--case", "cube")
            self.invoke(*command)
            (self.output / "workflow.api.json").write_text("{}", encoding="utf-8")
            failed = self.invoke(*command, ok=False)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("saved workflow differs", failed.stderr)
        self.assertEqual(len(requests), 2)

    def test_report_requires_scores_when_reference_is_set(self) -> None:
        failed = self.invoke("report", self.output, "--reference", "reference", ok=False)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("--reference requires --scores", failed.stderr)
