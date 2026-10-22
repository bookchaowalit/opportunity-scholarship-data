"""Offline consistency checks for source policies, the CLI boundary and capture guards."""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.resources import files
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlsplit

from book_scholarship_data import capture
from book_scholarship_data.cli import filter_items, main, resource

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def schema_for(version):
    for entry in files("book_scholarship_data").iterdir():
        if entry.name.startswith("schema") and entry.name.endswith(".json"):
            schema = json.loads(entry.read_text(encoding="utf-8"))
            if schema["properties"]["schema_version"].get("const") == version:
                return schema
    raise AssertionError(f"no bundled schema declares {version}")


class SourcePolicyTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((REPOSITORY_ROOT / "sources.json").read_text(encoding="utf-8"))

    def test_policy_file_exists(self):
        self.assertTrue((REPOSITORY_ROOT / self.catalog["policy_file"]).is_file())

    def test_enabled_sources_resolve_to_consistent_policies(self):
        caps = set(self.catalog["enabled_category_capabilities"])
        self.assertEqual(len(self.catalog["enabled_sources"]), len(set(self.catalog["enabled_sources"])))
        for source_id in self.catalog["enabled_sources"]:
            with self.subTest(source=source_id):
                policy = capture.source_config(source_id)
                self.assertEqual(policy["id"], source_id)
                self.assertEqual(policy["product"], "book-scholarship-data")
                self.assertEqual(policy["domain"], self.catalog["domain"])
                self.assertTrue(policy["enabled"])
                self.assertEqual(policy["permission_status"], self.catalog["permission_status"])
                self.assertGreaterEqual(policy["min_interval_seconds"], 21600)
                self.assertIn(policy["category"], caps)
                category_enum = schema_for(policy["schema_version"])["properties"]["items"]["items"]["properties"][
                    "category"
                ]["enum"]
                self.assertIn(policy["category"], category_enum)
                for key in ("source_url", "fetch_url"):
                    url = urlsplit(policy[key])
                    self.assertEqual(url.scheme, "https")
                    self.assertFalse(url.username or url.password or url.fragment)
                self.assertFalse(urlsplit(policy["source_url"]).query)

    def test_policy_files_are_enabled_and_duplicates_identical(self):
        by_id: dict[str, list[Any]] = {}
        for entry in files("book_scholarship_data").iterdir():
            if entry.name.startswith("source") and entry.name.endswith(".json"):
                policy = json.loads(entry.read_text(encoding="utf-8"))
                by_id.setdefault(policy["id"], []).append(policy)
        self.assertEqual(set(by_id), set(self.catalog["enabled_sources"]))
        for source_id, copies in by_id.items():
            with self.subTest(source=source_id):
                self.assertTrue(all(copy == copies[0] for copy in copies))

    def test_source_id_rejects_traversal_and_unknown(self):
        for bad in ("../schema", "Source", "a/b", "", "demo "):
            with self.subTest(source=bad), self.assertRaises(ValueError):
                capture.source_config(bad)
        with self.assertRaises(ValueError):
            capture.source_config("not-a-configured-source")

    def test_capture_requires_explicit_shared_runtime(self):
        err = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stderr(err):
            self.assertEqual(capture.main(["records"]), 2)
        with (
            tempfile.TemporaryDirectory() as empty,
            patch.dict(os.environ, {"SOLO_DATA_LAKE_ROOT": empty}),
            redirect_stderr(err),
        ):
            self.assertEqual(capture.main(["records"]), 2)


class CliBoundaryTests(unittest.TestCase):
    def test_contract_prints_bundled_schema(self):
        code, out, _ = run_cli(["contract"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), resource("schema.json"))

    def test_contract_version_selects_v1_or_v2_schema(self):
        for version, name in (("v1", "schema.json"), ("v2", "schema-v2.json")):
            with self.subTest(version=version):
                code, out, _ = run_cli(["contract", "--version", version])
                self.assertEqual(code, 0)
                schema = json.loads(out)
                self.assertEqual(schema, resource(name))
                self.assertTrue(schema["properties"]["schema_version"]["const"].endswith("." + version))
        # The v2 contract is what captured records use.
        self.assertEqual(
            resource("schema-v2.json")["properties"]["schema_version"]["const"],
            resource("source.json")["schema_version"],
        )

    def test_contract_rejects_unknown_version(self):
        with self.assertRaises(SystemExit) as exit_info, redirect_stderr(io.StringIO()):
            main(["contract", "--version", "v3"])
        self.assertEqual(exit_info.exception.code, 2)

    def test_validate_reports_count_for_valid_export(self):
        demo = files("book_scholarship_data").joinpath("demo.json")
        code, out, _ = run_cli(["validate", str(demo)])
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertTrue(report["valid"])
        self.assertEqual(report["count"], len(resource("demo.json")["items"]))

    def test_validate_rejects_without_echoing_input(self):
        payload = resource("demo.json")
        payload["items"][0]["title"] = 12345
        payload["items"][0]["source_url"] = "https://example.org/private-marker-value"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            code, out, err = run_cli(["validate", str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertNotIn("private-marker-value", err)

    def test_validate_rejects_missing_and_malformed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.json"
            broken.write_text("{not json", encoding="utf-8")
            self.assertEqual(run_cli(["validate", str(broken)])[0], 2)
            self.assertEqual(run_cli(["validate", str(Path(tmp) / "missing.json")])[0], 2)

    def test_demo_rejects_negative_age_and_bad_clock(self):
        self.assertEqual(run_cli(["demo", "--max-age-hours", "-1"])[0], 2)
        self.assertEqual(run_cli(["demo", "--as-of", "2026-09-07"])[0], 2)
        self.assertEqual(run_cli(["demo", "--as-of", "2026-09-07T00:00:00"])[0], 2)

    def test_query_is_case_insensitive(self):
        data = resource("demo.json")
        category = data["items"][0]["category"]
        found = filter_items(data, "2026-09-07T00:00:00Z", query=category.upper())
        self.assertTrue(found)
        self.assertTrue(
            all(category in item["category"] or category.casefold() in item["title"].casefold() for item in found)
        )


if __name__ == "__main__":
    unittest.main()
