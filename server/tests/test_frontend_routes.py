"""Routing rules for serving the built web app from FastAPI. Two real bugs
lived here: a missing map worker was masked by an index.html 200, and the
fix for that briefly 404'd ward deep links because ward keys contain dots."""

import pytest
from fastapi.testclient import TestClient

from server.main import WEB_DIST, app

pytestmark = pytest.mark.skipif(not (WEB_DIST / "index.html").exists(), reason="web/dist not built")
client = TestClient(app)


def test_client_routes_get_the_app():
    for path in ["/", "/plan", "/ask", "/method", "/brief/ward_369_final.317"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert "<div id=\"root\">" in r.text, path


def test_missing_static_asset_is_a_real_404():
    assert client.get("/assets/does-not-exist.js").status_code == 404
    assert client.get("/maplibre/nope.mjs").status_code == 404


def test_map_worker_is_served_as_javascript():
    r = client.get("/maplibre/maplibre-gl-worker.mjs")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/javascript")


def test_path_traversal_does_not_leak_source():
    r = client.get("/../server/main.py")
    assert "uvicorn" not in r.text


def test_unknown_api_path_is_404_not_the_app():
    assert client.get("/api/does-not-exist").status_code == 404
