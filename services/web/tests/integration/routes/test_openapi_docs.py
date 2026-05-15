"""FastAPI の /docs・/redoc・/openapi.json は既定で無効。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import web.main as app_main


@pytest.mark.integration
def test_openapi_ui_disabled_by_default() -> None:
    client = TestClient(app_main.app)
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
