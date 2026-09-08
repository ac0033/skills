import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reporting.py"
spec = importlib.util.spec_from_file_location("reporting", SCRIPT)
reporting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporting)


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        reporting.init(self.root, "example")
        (self.root / "source.txt").write_text("measured 8 seconds", encoding="utf-8")
        (self.root / "report.md").write_text("A request took 8 seconds.", encoding="utf-8")
        def source(path):
            return {"path": path, "sha256": hashlib.sha256((self.root / path).read_bytes()).hexdigest()}
        self.bundle = {
            "schema_version": "1.0", "project_id": "example", "request_id": "one",
            "question": "How long?", "audience": {"goal": "Understand request time", "known_concepts": []},
            "evidence": [{"id": "e1", "claim": "8 seconds", "source": dict(source("source.txt"), locator="line 1"),
                          "scope": "one request", "verification": "verified", "limitations": ["one measurement"]}],
            "knowledge": [{"id": "k1", "question": "How long?", "claim": "8 seconds", "evidence_ids": ["e1"],
                           "kind": "observation", "reasoning": "Direct measurement", "limitations": [], "status": "supported"}],
            "vocabulary": [{"id": "v1", "name": "request time", "aliases": ["latency"], "meaning": "Seconds waiting",
                            "example": "Wait 8 seconds", "prerequisite_ids": [], "state": "explained", "feedback_ref": None}],
            "sections": [{"id": "s1", "question": "How long?", "answer": "8 seconds", "knowledge_ids": ["k1"],
                          "concept_ids": ["v1"], "context": "One request was measured", "example": "Press a button and wait", "limits": []}],
            "report": source("report.md"),
            "checks": {"fact_review": "pending", "reader_review": "unavailable", "reader_independent": False,
                       "user_understanding": "unconfirmed", "feedback_ref": None},
            "reader_questions": ["What can this measurement tell us?"]}

    def result(self):
        return reporting.check(self.bundle, self.root)

    def test_valid_does_not_claim_semantic_pass(self):
        result = self.result()
        self.assertEqual(result["mechanical_status"], "passed")
        self.assertEqual(result["review_states"]["fact_review"], "pending")
        self.assertTrue(result["semantic_limitations"])
        self.assertTrue(result["warnings"])

    def test_missing_and_malformed_fields_are_diagnostics(self):
        for value in (None, [], {}, {"schema_version": "1.0", "sections": [1]}, {"checks": []}):
            with self.subTest(value=value):
                self.assertEqual(reporting.check(value, self.root)["mechanical_status"], "failed")
        for group, key in (("knowledge", "evidence_ids"), ("vocabulary", "state"), ("evidence", "verification")):
            broken = copy.deepcopy(self.bundle)
            broken[group][0][key] = {"bad": True}
            self.assertEqual(reporting.check(broken, self.root)["mechanical_status"], "failed")

    def test_changed_source_detected(self):
        (self.root / "source.txt").write_text("measured 9 seconds", encoding="utf-8")
        self.assertTrue(any("SHA-256 mismatch" in e for e in self.result()["errors"]))

    def test_path_escape_cross_platform(self):
        for value in ("../outside.txt", "..\\outside.txt", "/outside.txt", "C:\\outside.txt", "C:outside.txt", "\\\\host\\file"):
            with self.subTest(path=value):
                self.bundle["evidence"][0]["source"]["path"] = value
                self.assertEqual(self.result()["mechanical_status"], "failed")

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "secret.txt"
            path.write_text("private", encoding="utf-8")
            try:
                (self.root / "link").symlink_to(path)
            except OSError:
                self.skipTest("OS does not permit symlink creation")
            self.bundle["evidence"][0]["source"]["path"] = "link"
            self.assertTrue(any("escapes" in e for e in self.result()["errors"]))

    def test_unknown_duplicate_and_cyclic_references(self):
        self.bundle["knowledge"][0]["evidence_ids"] = ["missing"]
        self.bundle["vocabulary"][0]["prerequisite_ids"] = ["v1"]
        self.bundle["sections"][0]["id"] = "e1"
        text = " ".join(self.result()["errors"])
        for expected in ("unknown reference", "cycle", "duplicate ID"):
            self.assertIn(expected, text)

    def test_unsupported_unverified_and_false_confirmation(self):
        self.bundle["evidence"][0]["verification"] = "unverified"
        self.bundle["checks"].update(reader_review="passed", user_understanding="confirmed")
        self.bundle["vocabulary"][0]["state"] = "user_confirmed"
        errors = " ".join(self.result()["errors"])
        for expected in ("unverified", "reader_independent", "feedback_ref"):
            self.assertIn(expected, errors)
        self.bundle["knowledge"][0]["evidence_ids"] = []
        self.assertTrue(any("requires evidence" in e for e in self.result()["errors"]))

    def test_same_agent_review_has_actionable_status_guidance(self):
        self.bundle["checks"].update(reader_review="passed", reader_independent=False)
        errors = " ".join(self.result()["errors"])
        self.assertIn("reader_independent=true", errors)
        self.assertIn("same-agent self-review", errors)
        self.assertIn("reader_review='unavailable'", errors)

    def test_project_identity_and_schema(self):
        self.bundle.update(project_id="wrong", schema_version="2.0")
        errors = " ".join(self.result()["errors"])
        self.assertIn("does not match", errors)
        self.assertIn("unsupported", errors)

    def test_reader_pack_excludes_private_layers_and_never_overwrites(self):
        self.bundle["knowledge"][0]["claim"] = "SECRET EXPECTED ANSWER"
        self.bundle["evidence"][0]["claim"] = "SECRET EVIDENCE"
        self.bundle["expected_answers"] = ["ANOTHER SECRET"]
        source = self.root / "bundle.json"
        source.write_text(json.dumps(self.bundle), encoding="utf-8")
        target = self.root / "reader.json"
        reporting.reader_pack(source, self.root, target)
        text = target.read_text(encoding="utf-8")
        self.assertNotIn("SECRET", text)
        self.assertEqual(json.loads(text)["report"], (self.root / "report.md").read_text(encoding="utf-8"))
        self.assertEqual(set(json.loads(text)), {"schema_version", "report", "audience", "reader_questions"})
        with self.assertRaises(FileExistsError):
            reporting.reader_pack(source, self.root, target)

    def test_init_refuses_overwrite(self):
        before = (self.root / "reporting/project.json").read_bytes()
        with self.assertRaises(ValueError):
            reporting.init(self.root, "replacement")
        self.assertEqual(before, (self.root / "reporting/project.json").read_bytes())

    def test_source_roots_enforced_before_read(self):
        cfg = self.root / "reporting/project.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["source_roots"] = ["allowed"]
        cfg.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(any("source_roots" in e for e in self.result()["errors"]))
        for roots in ([], "allowed", ["../outside"], [None]):
            data["source_roots"] = roots
            cfg.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(self.result()["mechanical_status"], "failed")

    def test_empty_report_sections_and_questions_rejected(self):
        (self.root / "report.md").write_text("", encoding="utf-8")
        self.bundle["report"]["sha256"] = hashlib.sha256(b"").hexdigest()
        self.bundle["sections"] = []
        self.bundle["reader_questions"] = []
        errors = " ".join(self.result()["errors"])
        for expected in ("report must not be empty", "explanation section", "reader question"):
            self.assertIn(expected, errors)

    def test_report_change_blocks_reader_export(self):
        source = self.root / "bundle.json"
        source.write_text(json.dumps(self.bundle), encoding="utf-8")
        (self.root / "report.md").write_text("Changed report", encoding="utf-8")
        with self.assertRaises(ValueError):
            reporting.reader_pack(source, self.root, self.root / "reader.json")
        self.assertFalse((self.root / "reader.json").exists())


if __name__ == "__main__":
    unittest.main()
