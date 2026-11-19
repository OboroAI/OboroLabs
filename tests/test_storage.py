"""Verify run records, PNG checks, and writer locking."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from imagebench.constants.benchmark import COLD
from imagebench.storage import load_record, save_record, sha, writer
from imagebench.types.comfy import ImageResult
from tests.fixtures import job_for, pixel_png


class StorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.job = job_for("candidate", "cube")
        self.result = ImageResult(pixel_png(64, 64), latency_s=2.5, image_fetch_s=0.25)

    def test_round_trips_verified_record(self) -> None:
        save_record(self.directory, self.job, self.result)

        record = load_record(self.directory, self.job)
        assert record is not None
        self.assertEqual(record["latency_s"], 2.5)
        self.assertEqual(record["image_fetch_s"], 0.25)
        self.assertEqual(record["cache_condition"], "primed")
        self.assertEqual(record["png_sha256"], sha(self.result.png))
        self.assertEqual((self.directory / record["png"]).read_bytes(), self.result.png)

    def test_records_operator_declared_cold_sample(self) -> None:
        cold = job_for("candidate", "cube", phase=COLD)
        save_record(self.directory, cold, self.result)
        record = load_record(self.directory, cold)
        assert record is not None
        self.assertEqual(record["cache_condition"], "operator_fresh_server")

    def test_replaces_orphaned_png_on_retry(self) -> None:
        image = self.directory / "images" / f"{self.job['id']}.png"
        image.parent.mkdir()
        image.write_bytes(b"incomplete image from interrupted run")
        self.assertIsNone(load_record(self.directory, self.job))

        save_record(self.directory, self.job, self.result)
        self.assertEqual(image.read_bytes(), self.result.png)
        self.assertIsNotNone(load_record(self.directory, self.job))

    def test_rejects_wrong_png_dimensions_without_writing_a_record(self) -> None:
        result = ImageResult(pixel_png(32, 64), latency_s=2.5, image_fetch_s=0.25)
        with self.assertRaisesRegex(ValueError, "PNG dimensions"):
            save_record(self.directory, self.job, result)
        self.assertIsNone(load_record(self.directory, self.job))

    def test_rejects_record_when_job_inputs_change(self) -> None:
        save_record(self.directory, self.job, self.result)
        with self.assertRaisesRegex(ValueError, "record differs from plan"):
            load_record(self.directory, {**self.job, "seed": 42})

    def test_rejects_record_when_png_is_missing(self) -> None:
        save_record(self.directory, self.job, self.result)
        (self.directory / "images" / f"{self.job['id']}.png").unlink()
        with self.assertRaisesRegex(ValueError, "missing or changed PNG"):
            load_record(self.directory, self.job)

    def test_excludes_another_writer_until_lock_is_released(self) -> None:
        with writer(self.directory):
            with self.assertRaisesRegex(RuntimeError, "another command is writing this run"):
                with writer(self.directory):
                    self.fail("a second writer acquired the lock")
        with writer(self.directory):
            self.assertTrue((self.directory / ".lock").is_file())
