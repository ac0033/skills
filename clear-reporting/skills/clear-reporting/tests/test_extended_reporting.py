"""Independent adversarial CLI checks; synthetic fixtures only, stdlib only."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

DEFAULT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reporting.py"
SCRIPT = Path(os.environ.get("REPORTING_SCRIPT", str(DEFAULT_SCRIPT)))
spec = importlib.util.spec_from_file_location("reporting_extended", SCRIPT)
reporting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporting)


class ExtendedReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="clear-reporting-adversarial-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        reporting.init(self.root, "synthetic")
        (self.root / "source.txt").write_text("One sample took 8 seconds.\n", encoding="utf-8")
        (self.root / "report.md").write_text("One sample took 8 seconds; this does not establish general speed.\n", encoding="utf-8")
        def file_ref(name):
            return {"path": name, "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}
        self.bundle = {
            "schema_version": "1.0", "project_id": "synthetic", "request_id": "test",
            "question": "What was measured?", "audience": {"goal": "Understand scope", "known_concepts": []},
            "evidence": [{"id": "e", "claim": "8 seconds", "source": dict(file_ref("source.txt"), locator="line 1"),
                          "scope": "one synthetic sample", "verification": "verified", "limitations": ["one sample"]}],
            "knowledge": [{"id": "k", "question": "How long?", "claim": "8 seconds", "evidence_ids": ["e"],
                           "kind": "observation", "reasoning": "Read the measurement", "limitations": ["one sample"], "status": "supported"}],
            "vocabulary": [{"id": "v", "name": "waiting time", "aliases": [], "meaning": "seconds spent waiting",
                            "example": "8 seconds after pressing a button", "prerequisite_ids": [], "state": "explained", "feedback_ref": None}],
            "sections": [{"id": "s", "question": "What happened?", "answer": "8 seconds", "knowledge_ids": ["k"],
                          "concept_ids": ["v"], "context": "one measurement", "example": "One button press", "limits": ["one sample"]}],
            "report": file_ref("report.md"), "reader_questions": ["Can we generalize from one sample?"],
            "checks": {"fact_review": "pending", "reader_review": "unavailable", "reader_independent": False,
                       "user_understanding": "unconfirmed", "feedback_ref": None}}
        self.bundle_path = self.root / "bundle.json"
        self.save()

    def save(self):
        self.bundle_path.write_text(json.dumps(self.bundle, ensure_ascii=False), encoding="utf-8")

    def cli(self, command="check", *extra, expected=0):
        args = [sys.executable, str(SCRIPT), command, "--project", str(self.root)]
        if command != "init":
            args += ["--bundle", str(self.bundle_path)]
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        run = subprocess.run(args + list(extra), capture_output=True, encoding="utf-8", env=env, timeout=20)
        self.assertEqual(run.returncode, expected, (args, run.stdout, run.stderr))
        self.assertNotIn("Traceback", run.stderr)
        result = json.loads(run.stdout)
        if expected == 1:
            self.assertEqual(result["mechanical_status"], "failed")
            self.assertTrue(result["errors"])
        return result

    def test_cli_valid_preserves_pending_review(self):
        result = self.cli()
        self.assertEqual(result["mechanical_status"], "passed")
        self.assertEqual(result["review_states"]["fact_review"], "pending")
        self.assertEqual(result["review_states"]["user_understanding"], "unconfirmed")
        self.assertTrue(result["semantic_limitations"])

    def test_cli_init_collision_is_non_destructive(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.cli("init", "--project-id", "replacement", expected=1)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_cli_init_new_project_creates_no_assertions(self):
        fresh = self.root / "fresh"
        run = subprocess.run([sys.executable, str(SCRIPT), "init", "--project", str(fresh), "--project-id", "new"], capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        config = json.loads((fresh / "reporting/project.json").read_text(encoding="utf-8"))
        self.assertEqual(config["project_id"], "new")
        for name in ("evidence", "knowledge", "vocabulary", "sections"):
            self.assertEqual(json.loads((fresh / "reporting" / (name + ".json")).read_text()), [])

    def test_cli_corrupt_bundle_and_encoding(self):
        for raw in (b"{broken", b"\xff\xfe\x00", b"null", b"[]", b"42", b'"string"'):
            with self.subTest(raw=raw):
                self.bundle_path.write_bytes(raw)
                self.cli(expected=1)

    def test_cli_utf8_bom_bundle_accepted(self):
        self.bundle_path.write_text(json.dumps(self.bundle), encoding="utf-8-sig")
        self.cli()

    def test_cli_invalid_report_encoding_rejected(self):
        (self.root / "report.md").write_bytes(b"\xff\xfe\x00\x80")
        self.bundle["report"]["sha256"] = hashlib.sha256((self.root / "report.md").read_bytes()).hexdigest()
        self.save()
        self.cli(expected=1)

    def test_cli_invalid_config(self):
        for raw in (b"{broken", b"\xff", b"[]", b"null"):
            with self.subTest(raw=raw):
                (self.root / "reporting/project.json").write_bytes(raw)
                self.cli(expected=1)

    def test_cli_wrong_project_id_blocks_export(self):
        self.bundle["project_id"] = "different-project"
        self.save()
        output = self.root / "reader.json"
        self.cli("reader-pack", "--output", str(output), expected=1)
        self.assertFalse(output.exists())

    def test_cli_source_scope_and_empty_scope(self):
        config = self.root / "reporting/project.json"
        for roots in (["allowed"], [], None, ["../outside"], ["C:\\outside"], [False], "allowed"):
            with self.subTest(roots=roots):
                config.write_text(json.dumps({"schema_version": "1.0", "project_id": "synthetic", "source_roots": roots}), encoding="utf-8")
                self.cli(expected=1)

    def test_disallowed_source_is_not_read(self):
        cfg = self.root / "reporting/project.json"
        data = json.loads(cfg.read_text())
        data["source_roots"] = ["allowed"]
        cfg.write_text(json.dumps(data))
        reads = []
        original = Path.read_bytes
        def spy(path):
            reads.append(path.resolve())
            return original(path)
        with patch.object(Path, "read_bytes", spy):
            result = reporting.check(self.bundle, self.root)
        self.assertEqual(result["mechanical_status"], "failed")
        self.assertNotIn((self.root / "source.txt").resolve(), reads)

    def test_corrupt_config_fails_closed_before_source_read(self):
        bad_configs = [b"{broken", b"\xff", b"[]", b"null"]
        for cfg in (
            {"schema_version": "2.0", "project_id": "synthetic", "source_roots": ["."]},
            {"schema_version": "1.0", "project_id": "other", "source_roots": ["."]},
            {"schema_version": "1.0", "project_id": "synthetic", "source_roots": [".", None]},
        ):
            bad_configs.append(json.dumps(cfg).encode("utf-8"))
        for raw in bad_configs:
            with self.subTest(config=raw):
                (self.root / "reporting/project.json").write_bytes(raw)
                reads = []
                original = Path.read_bytes
                def spy(path):
                    reads.append(path.resolve())
                    return original(path)
                with patch.object(Path, "read_bytes", spy):
                    result = reporting.check(self.bundle, self.root)
                self.assertEqual(result["mechanical_status"], "failed")
                self.assertNotIn((self.root / "source.txt").resolve(), reads)

    def test_cli_unknown_references_block_export(self):
        for collection, field in (("knowledge", "evidence_ids"), ("vocabulary", "prerequisite_ids"), ("sections", "knowledge_ids"), ("sections", "concept_ids")):
            with self.subTest(collection=collection, field=field):
                changed = copy.deepcopy(self.bundle)
                changed[collection][0][field] = ["missing"]
                self.bundle_path.write_text(json.dumps(changed), encoding="utf-8")
                output = self.root / "reader.json"
                self.cli("reader-pack", "--output", str(output), expected=1)
                self.assertFalse(output.exists())

    def test_cli_export_does_not_overwrite_any_existing_file(self):
        for name in ("reader.json", "report.md", "source.txt", "bundle.json"):
            with self.subTest(name=name):
                output = self.root / name
                if not output.exists():
                    output.write_bytes(b"preserve me")
                before = output.read_bytes()
                self.cli("reader-pack", "--output", str(output), expected=1)
                self.assertEqual(output.read_bytes(), before)

    def test_cli_export_includes_only_allowed_fields(self):
        self.bundle["private_prompt"] = "PRIVATE_X"
        self.bundle["knowledge"][0]["claim"] = "PRIVATE_K"
        self.bundle["evidence"][0]["claim"] = "PRIVATE_E"
        self.bundle["audience"]["known_concepts"] = ["PRIVATE_A"]
        self.save()
        output = self.root / "reader.json"
        self.cli("reader-pack", "--output", str(output))
        pack = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(set(pack), {"schema_version", "report", "audience", "reader_questions"})
        self.assertEqual(pack["report"], (self.root / "report.md").read_bytes().decode("utf-8-sig"))
        self.assertEqual(pack["audience"], {"goal": self.bundle["audience"]["goal"]})
        self.assertNotIn("PRIVATE_", output.read_text())

    def test_cli_changed_report_and_source_block_export(self):
        for name in ("source.txt", "report.md"):
            with self.subTest(name=name):
                path = self.root / name
                before = path.read_bytes()
                path.write_bytes(before + b"changed")
                output = self.root / "reader.json"
                self.cli("reader-pack", "--output", str(output), expected=1)
                self.assertFalse(output.exists())
                path.write_bytes(before)

    def test_top_level_field_types_never_raise_or_pass(self):
        for key in self.bundle:
            for value in (None, 7, False):
                with self.subTest(key=key, value=value):
                    bundle = copy.deepcopy(self.bundle)
                    bundle[key] = value
                    self.assertEqual(reporting.check(bundle, self.root)["mechanical_status"], "failed")

    def test_nested_field_types_never_raise_or_pass(self):
        for group in ("evidence", "knowledge", "vocabulary", "sections"):
            for key in self.bundle[group][0]:
                with self.subTest(group=group, key=key):
                    bundle = copy.deepcopy(self.bundle)
                    bundle[group][0][key] = 42
                    self.assertEqual(reporting.check(bundle, self.root)["mechanical_status"], "failed")

    def test_standard_library_only(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8-sig"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported)
        self.assertTrue(imported <= sys.stdlib_module_names, imported - sys.stdlib_module_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)

