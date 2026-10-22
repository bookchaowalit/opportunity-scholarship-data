"""Capture entry point as a job; this file is byte-identical in every sibling book-*-data repo.

The discovery portfolio in data-lake-pipelines runs ``python -m <package>.capture`` for
each product. The shared runtime turns every capture failure into exit code 2 and a
generic stderr line, so an unhandled-exception hook never sees it. These tests pin that
a failed run still reaches Sentry when ``SENTRY_DSN`` is set, and that nothing is sent
(or imported) when it is not. No network: the runtime and ``sentry_sdk`` are fakes.
"""

import importlib
import os
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_name = re.search(r'^name = "([a-z-]+)"$', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
assert _name is not None, "pyproject.toml has no project name"
PACKAGE = _name[1].replace("-", "_")
capture = importlib.import_module(PACKAGE + ".capture")

RUNTIME = """VERSION = 1
CALLS = []


def run(source, normalize, validate, argv=None):
    CALLS.append((source["id"], list(argv or [])))
    return {exit_code}
"""


class FakeSentry(types.ModuleType):
    def __init__(self):
        super().__init__("sentry_sdk")
        self.init_kwargs = None
        self.messages = []
        self.tags = {}

    def init(self, **kwargs):
        self.init_kwargs = kwargs

    def set_tag(self, key, value):
        self.tags[key] = value

    def capture_message(self, message, level=None):
        self.messages.append((message, level))

    def flush(self, timeout=None):
        return None


class CaptureJobTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self._forget_runtime)
        self.sentry = FakeSentry()
        patcher = mock.patch.dict(sys.modules, {"sentry_sdk": self.sentry})
        patcher.start()
        self.addCleanup(patcher.stop)
        saved_path = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), saved_path))

    @staticmethod
    def _forget_runtime():
        for name in [m for m in sys.modules if m == "discovery" or m.startswith("discovery.")]:
            del sys.modules[name]

    def runtime(self, exit_code):
        discovery = Path(self.tmp.name) / "infra/scripts/discovery"
        discovery.mkdir(parents=True)
        (discovery / "__init__.py").write_text("", encoding="utf-8")
        (discovery / "capture_runtime.py").write_text(RUNTIME.format(exit_code=exit_code), encoding="utf-8")
        return self.tmp.name

    def run_main(self, exit_code, dsn):
        env = {"SOLO_DATA_LAKE_ROOT": self.runtime(exit_code)}
        if dsn:
            env["SENTRY_DSN"] = dsn
        with mock.patch.dict(os.environ, env, clear=True):
            return capture.main(["acquire", "--lake", "lake", "--state-dir", "state"])

    def test_failed_capture_reaches_sentry(self):
        self.assertEqual(self.run_main(2, "https://key@example.invalid/1"), 2)
        self.assertEqual(len(self.sentry.messages), 1)
        message, level = self.sentry.messages[0]
        self.assertEqual(level, "error")
        self.assertIn("exit code 2", message)
        self.assertEqual(self.sentry.tags.get("source_id"), capture.source_config()["id"])
        self.assertIs((self.sentry.init_kwargs or {}).get("send_default_pii"), False)

    def test_successful_capture_sends_nothing(self):
        self.assertEqual(self.run_main(0, "https://key@example.invalid/1"), 0)
        self.assertEqual(self.sentry.messages, [])
        self.assertIsNotNone(self.sentry.init_kwargs)

    def test_without_dsn_sentry_stays_off(self):
        self.assertEqual(self.run_main(2, ""), 2)
        self.assertIsNone(self.sentry.init_kwargs)
        self.assertEqual(self.sentry.messages, [])

    def test_missing_runtime_still_fails_closed(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(capture.main(["status", "--lake", "l", "--state-dir", "s"]), 2)
        self.assertEqual(self.sentry.messages, [])


if __name__ == "__main__":
    unittest.main()
