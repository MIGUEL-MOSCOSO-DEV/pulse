import tempfile
import unittest
from pathlib import Path

from pulse.metrics import Alerts, History, sample


class MetricsTests(unittest.TestCase):
    def test_alert_thresholds_and_cooldown(self):
        alerts = Alerts(cooldown=10)
        item = {"cpu": 95, "ram": 20}
        self.assertEqual(len(alerts.evaluate(item, {"cpu": 90}, now=0)), 1)
        self.assertEqual(alerts.evaluate(item, {"cpu": 90}, now=5), [])
        self.assertEqual(len(alerts.evaluate(item, {"cpu": 90}, now=10)), 1)

    def test_independent_metrics_do_not_suppress_each_other(self):
        alerts = Alerts()
        self.assertEqual(
            len(alerts.evaluate({"cpu": 95, "ram": 95}, {"cpu": 90, "ram": 90}, now=0)), 2
        )

    def test_below_threshold_produces_no_alert(self):
        self.assertEqual(Alerts().evaluate({"cpu": 20}, {"cpu": 90}), [])

    def test_invalid_threshold_rejected(self):
        with self.assertRaises(ValueError):
            Alerts().evaluate({"cpu": 20}, {"cpu": 101})

    def test_history_persists_and_returns_chronological_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.sqlite"
            history = History(path)
            for number in range(4):
                history.add({"time": number, "cpu": number * 10, "ram": 50, "disk": 60})
            rows = History(path).rows(2)
            self.assertEqual([row[0] for row in rows], [2, 3])

    def test_duplicate_sample_time_is_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            history = History(Path(directory) / "history.sqlite")
            history.add({"time": 1, "cpu": 10, "ram": 50, "disk": 60})
            history.add({"time": 1, "cpu": 20, "ram": 50, "disk": 60})
            self.assertEqual(len(history.rows()), 1)
            self.assertEqual(history.rows()[0][1], 20)

    def test_real_sampler_returns_bounded_metrics(self):
        result = sample()
        for metric in ["cpu", "ram", "disk"]:
            self.assertGreaterEqual(result[metric], 0)
            self.assertLessEqual(result[metric], 100)
        self.assertLessEqual(len(result["processes"]), 12)
        memory = [row[2] for row in result["processes"]]
        self.assertEqual(memory, sorted(memory, reverse=True))
