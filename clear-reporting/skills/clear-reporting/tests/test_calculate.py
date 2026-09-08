"""Portable Decimal calculator regression tests with synthetic inputs."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

DEFAULT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/reporting.py"
if not DEFAULT_SCRIPT.exists():
    DEFAULT_SCRIPT = Path(__file__).resolve().parent / "reporting_fixed.py"
SCRIPT = Path(os.environ.get("REPORTING_SCRIPT", str(DEFAULT_SCRIPT)))
spec = importlib.util.spec_from_file_location("reporting_calculate", SCRIPT)
reporting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporting)


class CalculationTests(unittest.TestCase):
    def compute(self, operation, operands, decimals=2):
        request = {"operation": operation, "operands": operands, "decimals": decimals}
        result = reporting.calculate(request)
        self.assertEqual(result["status"], "calculated")
        self.assertEqual(result["operands"], operands)
        self.assertEqual(result["operation"], operation)
        self.assertEqual(result["decimals"], decimals)
        return result["result"]

    def test_all_operations(self):
        for operation, operands, expected in (
            ("sum", ["0.1", "0.2"], "0.30"),
            ("mean", ["12", "16"], "14.00"),
            ("difference", ["12", "7"], "5.00"),
            ("difference", ["16", "9"], "7.00"),
            ("ratio", ["7", "12"], "0.58"),
            ("percent_change", ["12", "7"], "-41.67"),
            ("percent_change", ["100", "125"], "25.00"),
        ):
            with self.subTest(operation=operation, operands=operands):
                self.assertEqual(self.compute(operation, operands), expected)

    def test_decimal_half_up_and_signed_zero(self):
        for operand, expected in (("1.005", "1.01"), ("-1.005", "-1.01"), ("-0.001", "0.00")):
            self.assertEqual(self.compute("sum", [operand]), expected)
        self.assertEqual(self.compute("ratio", ["1", "3"], 12), "0.333333333333")
        self.assertEqual(self.compute("sum", ["2.5"], 0), "3")

    def test_sum_empty_and_mean_empty(self):
        self.assertEqual(self.compute("sum", []), "0.00")
        with self.assertRaises(ValueError):
            self.compute("mean", [])

    def test_large_bounded_arithmetic(self):
        self.assertEqual(self.compute("ratio", ["1e100", "1e-100"], 0), "1" + "0" * 200)
        self.assertEqual(self.compute("sum", ["1"] * 10000, 0), "10000")

    def test_invalid_operands(self):
        for operand in (True, False, 1, 1.5, None, {}, [], "NaN", "sNaN", "Infinity", "-Infinity", "1_000", " 1", "1 ", "", "1e101", "1e-101", "0e999999", "9" * 101, "1e9999999999999999999999999999999999999", "__import__('os').system('echo BAD')"):
            with self.subTest(operand=operand):
                with self.assertRaises(ValueError):
                    self.compute("sum", [operand])

    def test_invalid_requests(self):
        invalid = [None, [], "sum", 42, True, {},
            {"operation": "sum", "operands": [], "decimals": True},
            {"operation": [], "operands": [], "decimals": 2},
            {"operation": "sum", "operands": "1", "decimals": 2},
            {"operation": "sum", "operands": ["1"] * 10001, "decimals": 2}]
        for decimals in (-1, 13, 2.0, "2", None):
            invalid.append({"operation": "sum", "operands": ["1"], "decimals": decimals})
        for request in invalid:
            with self.subTest(request=str(request)[:100]):
                with self.assertRaises(ValueError):
                    reporting.calculate(request)

    def test_binary_arity_and_zero_division(self):
        for operation in ("difference", "ratio", "percent_change"):
            for operands in ([], ["1"], ["1", "2", "3"]):
                with self.subTest(operation=operation, operands=operands):
                    with self.assertRaises(ValueError):
                        self.compute(operation, operands)
        for operation, operands in (("ratio", ["1", "-0"]), ("percent_change", ["0", "5"])):
            with self.assertRaises(ValueError):
                self.compute(operation, operands)

    def test_cli_success_and_error_exit(self):
        with tempfile.TemporaryDirectory(prefix="reporting-calc-") as tmp:
            source = Path(tmp) / "input.json"
            for request, expected_exit in (({"operation": "difference", "operands": ["16", "9"], "decimals": 0}, 0), ([], 1), ({"operation": "ratio", "operands": ["1", "0"], "decimals": 2}, 1)):
                source.write_text(json.dumps(request), encoding="utf-8")
                run = subprocess.run([sys.executable, str(SCRIPT), "calculate", "--input", str(source)], capture_output=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=20)
                self.assertEqual(run.returncode, expected_exit, run.stderr)
                self.assertNotIn("Traceback", run.stderr)
                result = json.loads(run.stdout)
                if expected_exit == 0:
                    self.assertEqual(result["result"], "7")
                else:
                    self.assertEqual(result["mechanical_status"], "failed")
                    self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
