"""Only standard-library imports: no model, media or native runtime loading."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "budget", Path(__file__).resolve().parents[1] / "src/roadpulse/budget.py"
)
budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget)


class BudgetTests(unittest.TestCase):
    def test_rest_ratio_and_short_sleeps(self):
        now, pauses = [0.0], []

        def sleep(seconds):
            pauses.append(seconds)
            now[0] += seconds

        self.assertTrue(budget.rest_after(0.5, lambda: False, clock=lambda: now[0], sleep=sleep))
        self.assertAlmostEqual(now[0], 2.0)
        self.assertTrue(all(0 < p <= 0.25 for p in pauses))

    def test_immediate_cancel(self):
        self.assertFalse(budget.rest_after(10, lambda: True, sleep=lambda _: self.fail("slept")))

    def test_cancel_during_rest(self):
        now = [0.0]

        def sleep(seconds):
            now[0] += seconds

        self.assertFalse(budget.rest_after(
            10, lambda: now[0] >= 0.5, clock=lambda: now[0], sleep=sleep
        ))
        self.assertEqual(now[0], 0.5)

    def test_zero_work_does_not_sleep(self):
        self.assertTrue(budget.rest_after(0, lambda: False, sleep=lambda _: self.fail("slept")))


if __name__ == "__main__":
    unittest.main()
