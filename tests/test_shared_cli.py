"""Shared-CLI guardrails; this file is byte-identical in every sibling book-*-data repo.

``cli.py`` is vendored (copied) across the sibling ``book-*-data`` repositories until
the shared runtime package is independently installable. The pins below make a local
edit fail loudly: change every copy of the same variant together, then update the
hash here and copy this file to every sibling unchanged.
"""
import copy
import hashlib
import importlib
import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_name = re.search(r'^name = "([a-z-]+)"$', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
assert _name is not None, "pyproject.toml has no project name"
PROJECT = _name[1]
cli = importlib.import_module(PROJECT.replace("-", "_") + ".cli")

# Three variants: base, +contract --version v2, +v2 availability windows (benefit).
CLI_SHA256 = {
    "book-benefit-data": "d7d0837be73c71a51a8427fa37875f592caab83c9f709340cce991300b97e20f",
    "book-bounty-data": "5b4a7327093da486483dc123db547dde3b5c6c5ce6a4f24be084f06c50e6d998",
    "book-competition-data": "5b4a7327093da486483dc123db547dde3b5c6c5ce6a4f24be084f06c50e6d998",
    "book-creator-program-data": "5b4a7327093da486483dc123db547dde3b5c6c5ce6a4f24be084f06c50e6d998",
    "book-deal-data": "5b4a7327093da486483dc123db547dde3b5c6c5ce6a4f24be084f06c50e6d998",
    "book-freebie-data": "987d38370537c268dda6af63987ab258bb3f8cef31568b03182a95858efd74dc",
    "book-grant-data": "987d38370537c268dda6af63987ab258bb3f8cef31568b03182a95858efd74dc",
    "book-learning-program-data": "5b4a7327093da486483dc123db547dde3b5c6c5ce6a4f24be084f06c50e6d998",
    "book-mobility-program-data": "5b4a7327093da486483dc123db547dde3b5c6c5ce6a4f24be084f06c50e6d998",
    "book-paid-study-data": "5b4a7327093da486483dc123db547dde3b5c6c5ce6a4f24be084f06c50e6d998",
    "book-partnership-data": "5b4a7327093da486483dc123db547dde3b5c6c5ce6a4f24be084f06c50e6d998",
    "book-procurement-data": "5b4a7327093da486483dc123db547dde3b5c6c5ce6a4f24be084f06c50e6d998",
    "book-scholarship-data": "987d38370537c268dda6af63987ab258bb3f8cef31568b03182a95858efd74dc",
    "book-startup-program-data": "5b4a7327093da486483dc123db547dde3b5c6c5ce6a4f24be084f06c50e6d998",
}


def live_demo(host):
    """The packaged demo turned into a live payload whose records all use ``host``."""
    payload = copy.deepcopy(cli.resource("demo.json"))
    payload["data_status"] = "live"
    for item in payload["items"]:
        item["source_url"] = "https://" + host + "/record"
        item["provenance"].update(evidence_kind="captured", raw_object_key="raw/a", bronze_manifest_key="bronze/a")
    return payload


class VendoredCliTest(unittest.TestCase):
    def test_cli_matches_the_pinned_shared_copy(self):
        digest = hashlib.sha256(Path(str(cli.__file__)).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        self.assertIn(PROJECT, CLI_SHA256)
        siblings = sorted(name for name, pinned in CLI_SHA256.items() if pinned == CLI_SHA256[PROJECT])
        self.assertEqual(
            digest,
            CLI_SHA256[PROJECT],
            "cli.py drifted from its vendored copy; apply the same change to " + ", ".join(siblings),
        )


class TimestampTest(unittest.TestCase):
    def test_fraction_digits_parse_identically_on_every_interpreter(self):
        # Python 3.10 fromisoformat rejects fractions that are not 3 or 6 digits.
        cases = {
            "2026-09-07T00:00:00.1Z": 100000,
            "2026-09-07T00:00:00.12Z": 120000,
            "2026-09-07T00:00:00.1234Z": 123400,
            "2026-09-07T00:00:00.1234567+07:00": 123456,
        }
        for value, micro in cases.items():
            with self.subTest(value=value):
                self.assertEqual(cli.timestamp(value).microsecond, micro)

    def test_offsets_normalise_to_the_same_utc_instant(self):
        bangkok = cli.timestamp("2026-10-01T07:00:00+07:00")
        new_york = cli.timestamp("2026-09-30T20:00:00-04:00")
        self.assertEqual(bangkok, cli.timestamp("2026-10-01T00:00:00Z"))
        self.assertEqual(bangkok, new_york)
        self.assertEqual(bangkok.utcoffset().total_seconds(), 0)

    def test_naive_and_non_ascii_timestamps_are_rejected(self):
        for value in ("2026-09-07T00:00:00", "2026-09-07", "๒๐๒๖-09-07T00:00:00Z", "2026-09-07T24:00:00Z"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cli.timestamp(value)


class ValidateTest(unittest.TestCase):
    def test_non_finite_numbers_are_rejected(self):
        for amount in (float("nan"), float("inf"), float("-inf")):
            payload = copy.deepcopy(cli.resource("demo.json"))
            payload["items"][0]["value"].update(amount=amount, currency="USD")
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                cli.validate(payload)

    def test_validate_command_rejects_nan_and_overflow_literals(self):
        payload = copy.deepcopy(cli.resource("demo.json"))
        payload["items"][0]["value"].update(amount=123456789, currency="USD")
        text = json.dumps(payload)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "payload.json"
            for literal, code in (("123456789", 0), ("NaN", 2), ("Infinity", 2), ("-Infinity", 2), ("1e400", 2)):
                path.write_text(text.replace("123456789", literal), encoding="utf-8")
                out, err = io.StringIO(), io.StringIO()
                with self.subTest(literal=literal), redirect_stdout(out), redirect_stderr(err):
                    self.assertEqual(cli.main(["validate", str(path)]), code)
                self.assertNotIn(literal, err.getvalue())

    def test_trailing_dot_synthetic_host_cannot_be_live(self):
        for host in ("example.org.", "EXAMPLE.ORG", "demo.example.org."):
            with self.subTest(host=host), self.assertRaisesRegex(ValueError, "synthetic source"):
                cli.validate(live_demo(host))

    def test_lookalike_hosts_are_not_treated_as_synthetic(self):
        for host in ("notexample.org", "example.org.evil.test"):
            with self.subTest(host=host):
                try:
                    cli.validate(live_demo(host))
                except ValueError as error:
                    self.assertNotIn("synthetic", str(error))


class TextNormalisationTest(unittest.TestCase):
    def test_blank_or_invisible_required_text_is_rejected(self):
        for field in ("id", "title", "provider", "eligibility_text"):
            for value in (" ", "\u200b", "\ufeff\u00ad\u2060"):
                payload = copy.deepcopy(cli.resource("demo.json"))
                payload["items"][0][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    cli.validate(payload)

    def test_ids_differing_only_by_invisible_characters_are_duplicates(self):
        payload = copy.deepcopy(cli.resource("demo.json"))
        twin = copy.deepcopy(payload["items"][0])
        twin["id"] = "\u200b" + twin["id"] + " "
        payload["items"].append(twin)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            cli.validate(payload)

    def test_query_matches_thai_and_full_width_spellings(self):
        payload = copy.deepcopy(cli.resource("demo.json"))
        target = payload["items"][0]
        target["title"] = "ลดค่าน้ำประปา ปี 2569 UK"
        # SARA AM vs NIKHAHIT + SARA AA (either mark order), Thai digits,
        # full-width Latin and a stray zero-width space.
        for query in ("น้ำ", "น\u0e49\u0e4d\u0e32", "น\u0e4d\u0e49\u0e32", "๒๕๖๙", "ＵＫ", "u\u200bk"):
            with self.subTest(query=query):
                found = cli.filter_items(payload, payload["retrieved_at"], query=query)
                self.assertIn(target["id"], [item["id"] for item in found])


if __name__ == "__main__":
    unittest.main()
