from pathlib import Path
import json
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "tools"))

from result_store import build_result, atomic_write_json
from render_paper import render_text


class StarterKitTests(unittest.TestCase):
    def test_build_result_requires_metrics(self):
        with self.assertRaises(ValueError):
            build_result(question="Q1", method="x", metrics={})

    def test_atomic_json_and_render(self):
        result = build_result(
            question="Q1",
            method="rf",
            metrics={"rmse": 0.123456, "r2": 0.87654},
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "result.json"
            atomic_write_json(p, result)
            loaded = json.loads(p.read_text(encoding="utf-8"))
            text = render_text(
                "RMSE={{metrics.rmse:.4f}}, R2={{metrics.r2:.3f}}",
                loaded,
            )
            self.assertEqual(text, "RMSE=0.1235, R2=0.877")

    def test_missing_placeholder_fails(self):
        with self.assertRaises(KeyError):
            render_text("x={{metrics.missing}}", {"metrics": {}})


if __name__ == "__main__":
    unittest.main()
