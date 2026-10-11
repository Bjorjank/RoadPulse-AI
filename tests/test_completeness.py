"""Small regression checks without loading OpenCV or the inference runtime."""

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "completeness", Path(__file__).resolve().parents[1] / "src/roadpulse/video/completeness.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CompletenessTests(unittest.TestCase):
    def test_exact(self):
        self.assertIsNone(module.decode_warning(465, 465))

    def test_underestimated_metadata(self):
        self.assertIsNone(module.decode_warning(466, 465))

    def test_reported_regression(self):
        warning = module.decode_warning(462, 465)
        self.assertIn("462/465", warning)
        self.assertIn("decoded frames only", warning)

    def test_large_gap(self):
        with self.assertRaisesRegex(ValueError, "ended early"):
            module.decode_warning(460, 465)

    def test_small_clip_proportion(self):
        with self.assertRaises(ValueError):
            module.decode_warning(7, 10)

    def test_empty(self):
        with self.assertRaisesRegex(ValueError, "no readable frames"):
            module.decode_warning(0, 465)


if __name__ == "__main__":
    unittest.main()
