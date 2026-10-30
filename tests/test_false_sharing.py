"""Counter correctness and workload-aware metrics, using real spawned workers."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "false_sharing.py"
spec = importlib.util.spec_from_file_location("false_sharing", MODULE_PATH)
false_sharing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(false_sharing)
# Spawn must be able to import the same module by name in a fresh interpreter.
import sys
sys.path.insert(0, str(MODULE_PATH.parent))
sys.modules["false_sharing"] = false_sharing


class FalseSharingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = tempfile.TemporaryDirectory()
        cls.library, _ = false_sharing.build_native_library(Path(cls.cache.name))

    @classmethod
    def tearDownClass(cls):
        cls.cache.cleanup()

    def test_real_workers_preserve_all_counts(self):
        for variant in ("unpadded", "padded", "privatized", "padded_64"):
            with self.subTest(variant=variant):
                result = false_sharing.run_trial(variant, 2, 10_003, 128, self.library)
                self.assertEqual(result["counts"], [10_003, 10_003])
                self.assertTrue(result["counts_verified"])
                self.assertGreater(result["seconds"], 0)
                self.assertEqual(result["total_increments"], 20_006)
                if variant == "padded":
                    self.assertEqual(result["stride_bytes"], 128)
                    self.assertEqual(result["counter_offset_within_cache_line"], [0, 0])
                if variant == "padded_64":
                    self.assertEqual(result["counter_offset_within_cache_line"], [0, 64])

    def test_ideal_weak_scaling_requested_metric_is_one(self):
        result = false_sharing.scaling_metrics(2.0, 2.0, 8)
        self.assertEqual(result["requested_speedup_t1_over_tp"], 1)
        self.assertAlmostEqual(result["karp_flatt_requested"], 1)
        self.assertEqual(result["throughput_speedup"], 8)
        self.assertIsNone(false_sharing.scaling_metrics(2.0, 2.0, 1)["karp_flatt_requested"])

    def test_negative_requested_speedup_is_reported_without_clamping(self):
        result = false_sharing.scaling_metrics(1.0, 4.0, 4)
        self.assertEqual(result["requested_speedup_t1_over_tp"], 0.25)
        self.assertEqual(result["karp_flatt_requested"], 5)
        self.assertEqual(result["throughput_speedup"], 1)

    def test_padding_respects_hardware_line_and_keeps_assignment_variant(self):
        self.assertEqual(false_sharing.variants_for_cache_line(128)["padded"], 128)
        self.assertEqual(false_sharing.variants_for_cache_line(128)["padded_64"], 64)
        self.assertNotIn("padded_64", false_sharing.variants_for_cache_line(64))
        with self.assertRaises(ValueError):
            false_sharing.variants_for_cache_line(65)


if __name__ == "__main__":
    unittest.main()
