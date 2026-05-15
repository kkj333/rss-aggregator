"""Settings の OpenAPI（/docs）フラグ。"""

from __future__ import annotations

import pytest

from shared.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, False),
        ("", False),
        ("0", False),
        ("false", False),
        ("no", False),
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("TRUE", True),
    ],
)
def test_enable_openapi_docs_from_env(monkeypatch, raw: str | None, expected: bool) -> None:
    if raw is None:
        monkeypatch.delenv("ENABLE_OPENAPI_DOCS", raising=False)
    else:
        monkeypatch.setenv("ENABLE_OPENAPI_DOCS", raw)
    s = Settings.from_env()
    assert s.enable_openapi_docs is expected
