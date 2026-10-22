"""Opt-in Sentry for capture runs; this file is byte-identical in every sibling book-*-data repo.

Off unless ``SENTRY_DSN`` is set and the ``sentry`` extra is installed. The shared capture
runtime reports failures as an exit code (not an exception), so the caller passes that code
to :func:`report_exit` and a non-zero run becomes one Sentry event. No payloads, source
bodies or personal data are attached: only the source id and the exit code.
"""

from __future__ import annotations

import os
from importlib import import_module
from types import ModuleType


def init_sentry(source_id: str) -> ModuleType | None:
    """Initialise Sentry for one capture run; return the SDK, or None when it is off."""
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return None
    try:
        sdk = import_module("sentry_sdk")
    except ImportError:
        return None
    sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "local"),
        send_default_pii=False,
        traces_sample_rate=0.0,
    )
    sdk.set_tag("source_id", source_id)
    return sdk


def report_exit(sdk: ModuleType | None, source_id: str, code: int) -> int:
    """Send one error event for a failed run and return ``code`` unchanged."""
    if sdk is not None and code != 0:
        sdk.capture_message(f"capture {source_id} failed with exit code {code}", level="error")
        sdk.flush(timeout=5)
    return code
