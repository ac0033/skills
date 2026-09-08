#!/usr/bin/env python3
"""Portable reporting material checks. Python 3.10+, standard library only."""
import argparse
from decimal import Decimal, DecimalException, localcontext, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import sys


SEMANTIC_LIMITS = [
    "Mechanical checks do not establish that claims are true or evidence is sufficient.",
    "Mechanical checks do not establish clarity, independent review quality, or user understanding.",
    "Review states and feedback references are declarations, not independently authenticated approvals.",
]


def read_json(path):
    with Path(path).open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def safe_path(root, value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path must be a nonempty relative string")
    # Treat both OS separators as separators, even when running on another OS.
    normalized = value.replace("\\", "/")
    if Path(normalized).is_absolute() or PureWindowsPath(value).drive or ".." in normalized.split("/"):
        raise ValueError("absolute paths and traversal are forbidden")
    root = Path(root).resolve()
    target = (root / normalized).resolve()
    if not target.is_relative_to(root):
        raise ValueError("resolved path escapes project (including symlinks)")
    return target


def check(bundle, project):
    errors, warnings = [], []
    project = Path(project).resolve()
    def fail(where, message):
        errors.append(f"{where}: {message}")
    def string(obj, key, where, nullable=False):
        value = obj.get(key)
        if nullable and key in obj and value is None:
            return value
        if not isinstance(value, str) or not value.strip():
            fail(f"{where}.{key}", "required nonempty string" + (" or null" if nullable else ""))
            return None
        return value
    def array(obj, key, where, strings=False):
        value = obj.get(key)
        if not isinstance(value, list):
            fail(f"{where}.{key}", "required array")
            return []
        if strings:
            for i, item in enumerate(value):
                if not isinstance(item, str) or not item.strip():
                    fail(f"{where}.{key}[{i}]", "required nonempty string")
            return [x for x in value if isinstance(x, str) and x.strip()]
        return value
    def choice(obj, key, choices, where):
        value = obj.get(key)
        if not isinstance(value, str) or value not in choices:
            fail(f"{where}.{key}", "expected one of " + ", ".join(sorted(choices)))
            return None
        return value
    def obj_at(obj, key, where):
        value = obj.get(key)
        if not isinstance(value, dict):
            fail(f"{where}.{key}", "required object")
            return {}
        return value
    allowed_roots = [project]
    def file_hash(obj, where, is_source=False):
        path = string(obj, "path", where)
        digest = string(obj, "sha256", where)
        if digest and (len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest)):
            fail(where + ".sha256", "expected 64 hexadecimal characters")
        if path:
            try:
                target = safe_path(project, path)
                if is_source and not any(target.is_relative_to(root) for root in allowed_roots):
                    raise ValueError("source is outside configured source_roots")
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
                if digest and actual != digest.lower():
                    fail(where, "file SHA-256 mismatch; source/report changed")
            except (OSError, ValueError) as exc:
                fail(where, str(exc))
    if not isinstance(bundle, dict):
        return {"mechanical_status": "failed", "errors": ["bundle: required object"], "warnings": [], "review_states": {}, "semantic_limitations": SEMANTIC_LIMITS}
    if bundle.get("schema_version") != "1.0":
        fail("schema_version", "unsupported or missing schema; expected 1.0")
    pid = string(bundle, "project_id", "bundle")
    for key in ("request_id", "question"):
        string(bundle, key, "bundle")
    config = project / "reporting" / "project.json"
    if config.exists():
        # A present but invalid config must never widen evidence access.
        allowed_roots = []
        config_error_start = len(errors)
        try:
            config = safe_path(project, "reporting/project.json")
            cfg = read_json(config)
            if not isinstance(cfg, dict) or cfg.get("project_id") != pid:
                fail("project_id", "does not match reporting/project.json")
            if isinstance(cfg, dict):
                if cfg.get("schema_version") != "1.0":
                    fail("project config", "unsupported schema_version")
                roots = cfg.get("source_roots")
                if not isinstance(roots, list) or not roots:
                    fail("project config", "source_roots must be a nonempty array")
                    allowed_roots = []
                else:
                    allowed_roots = []
                    for value in roots:
                        try:
                            allowed_roots.append(safe_path(project, value))
                        except (OSError, ValueError) as exc:
                            fail("project config.source_roots", str(exc))
        except (OSError, ValueError) as exc:
            fail("project config", str(exc))
        if len(errors) > config_error_start:
            allowed_roots = []
    else:
        warnings.append("No reporting/project.json; project identity could not be checked.")
    audience = obj_at(bundle, "audience", "bundle")
    string(audience, "goal", "audience")
    array(audience, "known_concepts", "audience", True)
    maps = {}
    global_ids = set()
    for collection in ("evidence", "knowledge", "vocabulary", "sections"):
        records = array(bundle, collection, "bundle")
        maps[collection] = {}
        for i, record in enumerate(records):
            where = f"{collection}[{i}]"
            if not isinstance(record, dict):
                fail(where, "required object")
                continue
            ident = string(record, "id", where)
            if ident:
                if ident in global_ids:
                    fail(where + ".id", "duplicate ID " + ident)
                global_ids.add(ident)
                maps[collection][ident] = record
            if collection == "evidence":
                for key in ("claim", "scope"):
                    string(record, key, where)
                source = obj_at(record, "source", where)
                string(source, "locator", where + ".source")
                file_hash(source, where + ".source", is_source=True)
                state = choice(record, "verification", {"verified", "reported", "unverified"}, where)
                if state == "reported":
                    warnings.append(where + ": reported evidence has not been independently verified.")
                array(record, "limitations", where, True)
            elif collection == "knowledge":
                for key in ("question", "claim", "reasoning"):
                    string(record, key, where)
                array(record, "evidence_ids", where, True)
                array(record, "limitations", where, True)
                choice(record, "kind", {"observation", "inference", "recommendation", "open"}, where)
                choice(record, "status", {"supported", "hypothesis", "disputed", "superseded", "open"}, where)
            elif collection == "vocabulary":
                for key in ("name", "meaning", "example"):
                    string(record, key, where)
                for key in ("aliases", "prerequisite_ids"):
                    array(record, key, where, True)
                state = choice(record, "state", {"unexplained", "explained", "user_confirmed", "questioned"}, where)
                ref = string(record, "feedback_ref", where, True)
                if state == "user_confirmed" and not ref:
                    fail(where, "user_confirmed requires feedback_ref")
            else:
                for key in ("question", "answer", "context", "example"):
                    string(record, key, where)
                for key in ("knowledge_ids", "concept_ids", "limits"):
                    array(record, key, where, True)
    def refs(record, key, target, where):
        values = record.get(key)
        values = values if isinstance(values, list) else []
        for value in values:
            if isinstance(value, str) and value not in maps[target]:
                fail(where + "." + key, "unknown reference " + value)
        return [v for v in values if isinstance(v, str) and v in maps[target]]
    for ident, record in maps["knowledge"].items():
        evidence = refs(record, "evidence_ids", "evidence", ident)
        if record.get("status") == "supported":
            if not evidence:
                fail(ident, "supported knowledge requires evidence")
            if record.get("kind") == "open":
                fail(ident, "open knowledge cannot be supported")
            for eid in evidence:
                if maps["evidence"][eid].get("verification") == "unverified":
                    fail(ident, "supported knowledge references unverified evidence " + eid)
    graph = {}
    for ident, record in maps["vocabulary"].items():
        graph[ident] = refs(record, "prerequisite_ids", "vocabulary", ident)
    # Iterative topological removal avoids recursion limits on large vocabularies.
    pending = {k: set(v) for k, v in graph.items()}
    while pending:
        ready = {k for k, v in pending.items() if not v}
        if not ready:
            fail("vocabulary", "prerequisite cycle involving " + ", ".join(sorted(pending)))
            break
        pending = {k: v - ready for k, v in pending.items() if k not in ready}
    for ident, record in maps["sections"].items():
        kids = refs(record, "knowledge_ids", "knowledge", ident)
        refs(record, "concept_ids", "vocabulary", ident)
        for kid in kids:
            if maps["knowledge"][kid].get("status") == "superseded":
                warnings.append(ident + ": references superseded knowledge " + kid + "; verify historical context.")
    if not maps["sections"]:
        fail("sections", "at least one explanation section is required")
    report = obj_at(bundle, "report", "bundle")
    file_hash(report, "report")
    try:
        body = safe_path(project, report.get("path")).read_text(encoding="utf-8-sig")
        if not body.strip():
            fail("report", "report must not be empty")
        for ident, record in maps["vocabulary"].items():
            aliases = record.get("aliases", [])
            if isinstance(aliases, list):
                for alias in aliases:
                    if isinstance(alias, str) and alias and alias in body:
                        warnings.append(f"report uses alias {alias!r} for {record.get('name')!r}; check naming consistency.")
    except UnicodeDecodeError as exc:
        fail("report", "report must be UTF-8 text: " + str(exc))
    except (OSError, ValueError) as exc:
        fail("report", "cannot read report text: " + str(exc))
    checks = obj_at(bundle, "checks", "bundle")
    choice(checks, "fact_review", {"passed", "pending", "failed"}, "checks")
    reader = choice(checks, "reader_review", {"passed", "pending", "failed", "unavailable"}, "checks")
    if type(checks.get("reader_independent")) is not bool:
        fail("checks.reader_independent", "required boolean")
    if reader == "passed" and checks.get("reader_independent") is not True:
        fail(
            "checks",
            "reader_review='passed' requires reader_independent=true; "
            "save same-agent self-review separately and use reader_review='unavailable'",
        )
    if reader == "unavailable":
        warnings.append("Independent reader review unavailable; clarity has not been independently reviewed.")
    understanding = choice(checks, "user_understanding", {"unconfirmed", "confirmed", "questioned"}, "checks")
    ref = string(checks, "feedback_ref", "checks", True)
    if understanding == "confirmed" and not ref:
        fail("checks", "confirmed user understanding requires feedback_ref")
    if not array(bundle, "reader_questions", "bundle", True):
        fail("reader_questions", "at least one reader question is required")
    return {"mechanical_status": "failed" if errors else "passed", "errors": errors, "warnings": warnings,
            "review_states": checks, "semantic_limitations": SEMANTIC_LIMITS}


def init(project, project_id):
    if not project_id.strip():
        raise ValueError("project-id must not be empty")
    root = Path(project).resolve()
    folder = safe_path(root, "reporting")
    if folder.exists():
        raise ValueError("reporting already exists; init never overwrites existing materials")
    folder.mkdir(parents=True)
    (folder / "project.json").write_text(json.dumps({"schema_version": "1.0", "project_id": project_id,
        "source_roots": ["."], "output_dir": "reporting"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in ("evidence", "knowledge", "vocabulary", "sections"):
        (folder / (name + ".json")).write_text("[]\n", encoding="utf-8")
    return {"status": "initialized", "path": str(folder), "note": "Empty materials only; no claims or approvals created."}


def reader_pack(bundle_path, project, output):
    bundle = read_json(bundle_path)
    if not isinstance(bundle, dict) or bundle.get("schema_version") != "1.0":
        raise ValueError("reader-pack requires a schema 1.0 bundle object")
    result = check(bundle, project)
    if result["mechanical_status"] != "passed":
        raise ValueError("reader-pack requires mechanical checks to pass: " + "; ".join(result["errors"]))
    report_path = safe_path(project, bundle["report"]["path"])
    content = report_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != bundle["report"]["sha256"].lower():
        raise ValueError("report SHA-256 changed before export")
    # Only the actual final report, audience goal and questions cross the boundary.
    # Report text may itself contain cited facts; no private material layers are copied.
    pack = {"schema_version": "1.0", "report": content.decode("utf-8-sig"),
            "audience": {"goal": bundle["audience"]["goal"]}, "reader_questions": bundle["reader_questions"]}
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        json.dump(pack, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {"status": "exported", "path": str(target), "note": "Actual final report, audience goal and questions only; private layers excluded."}


def calculate(request):
    """Calculate explicit decimal operands; does not infer pairing, units or scope."""
    if not isinstance(request, dict):
        raise ValueError("calculation input must be an object")
    operation = request.get("operation")
    methods = {
        "sum": "sum(operands)",
        "mean": "sum(operands) / count(operands)",
        "difference": "operands[0] - operands[1]",
        "ratio": "operands[0] / operands[1]",
        "percent_change": "(new - old) / old * 100; operands = [old, new]",
    }
    if not isinstance(operation, str) or operation not in methods:
        raise ValueError("operation must be sum, mean, difference, ratio or percent_change")
    operands = request.get("operands")
    if not isinstance(operands, list) or len(operands) > 10000:
        raise ValueError("operands must be an array with at most 10000 decimal strings")
    decimals = request.get("decimals")
    if type(decimals) is not int or not 0 <= decimals <= 12:
        raise ValueError("decimals must be an integer from 0 to 12")
    if operation == "mean" and not operands:
        raise ValueError("mean requires at least one operand")
    if operation in {"difference", "ratio", "percent_change"} and len(operands) != 2:
        raise ValueError(operation + " requires exactly two operands")
    numbers = []
    for index, text in enumerate(operands):
        if not isinstance(text, str) or not 1 <= len(text) <= 100:
            raise ValueError(f"operands[{index}] must be a decimal string of 1 to 100 characters")
        if re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text) is None:
            raise ValueError(f"operands[{index}] is not a finite decimal string")
        try:
            number = Decimal(text)
        except DecimalException as exc:
            raise ValueError(f"operands[{index}] is not a valid decimal") from exc
        if not number.is_finite() or abs(number.as_tuple().exponent) > 100 or (number and abs(number.adjusted()) > 100):
            raise ValueError(f"operands[{index}] exceeds supported decimal scale (-100 to 100)")
        numbers.append(number)
    if operation == "ratio" and numbers[1].is_zero():
        raise ValueError("ratio denominator must not be zero")
    if operation == "percent_change" and numbers[0].is_zero():
        raise ValueError("percent_change old value must not be zero")
    try:
        # Bounds above keep exact sums/products below this precision and leave
        # enough guard digits for division before final rounding to 0..12 places.
        with localcontext() as context:
            context.prec = 512
            context.rounding = ROUND_HALF_UP
            if operation == "sum":
                value = sum(numbers, Decimal(0))
            elif operation == "mean":
                value = sum(numbers, Decimal(0)) / len(numbers)
            elif operation == "difference":
                value = numbers[0] - numbers[1]
            elif operation == "ratio":
                value = numbers[0] / numbers[1]
            else:
                value = (numbers[1] - numbers[0]) / numbers[0] * 100
            rounded = value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
            if rounded.is_zero():
                rounded = rounded.copy_abs()
            result = format(rounded, "f")
    except DecimalException as exc:
        raise ValueError("calculation exceeds supported decimal arithmetic") from exc
    return {"status": "calculated", "operation": operation, "operands": operands,
            "decimals": decimals, "result": result,
            "method": methods[operation] + "; Decimal precision=512; ROUND_HALF_UP to decimals places. Pairing, units and interpretation are not validated."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("init", help="Create empty project reporting files; never overwrite")
    p.add_argument("--project", required=True)
    p.add_argument("--project-id", required=True)
    p = subs.add_parser("check", help="Check a bundle and file digests; emit JSON, exit 1 on mechanical failure")
    p.add_argument("--bundle", required=True)
    p.add_argument("--project", required=True)
    p = subs.add_parser("reader-pack", help="Export verified final report, audience goal and reader questions; never overwrite")
    p.add_argument("--bundle", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--output", required=True)
    p = subs.add_parser("calculate", help="Calculate explicit decimal strings using Decimal and ROUND_HALF_UP")
    p.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init(args.project, args.project_id)
        elif args.command == "check":
            result = check(read_json(args.bundle), args.project)
        elif args.command == "calculate":
            result = calculate(read_json(args.input))
        else:
            result = reader_pack(args.bundle, args.project, args.output)
    except (OSError, ValueError) as exc:
        result = {"mechanical_status": "failed", "errors": [str(exc)], "semantic_limitations": SEMANTIC_LIMITS}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("mechanical_status") == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
