"""Basic API endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Verify the health check endpoint responds correctly."""

    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["database"] == "ok"
        assert data["model_server"] in {"ok", "down"}
        assert data["status"] in {"ok", "degraded"}

    def test_root_lists_demo_links(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["demo_capture"] == "/demo/capture/"
        assert data["demo_checkin"] == "/demo/checkin/"

    def test_demo_static_routes_are_served(self, client: TestClient):
        capture_resp = client.get("/demo/capture/")
        checkin_resp = client.get("/demo/checkin/")
        assert capture_resp.status_code == 200
        assert checkin_resp.status_code == 200
        assert "Face Recognition" in capture_resp.text
        assert "Lumiere Hotels" in checkin_resp.text


class TestAuthEndpoints:
    """Verify auth endpoints exist and reject bad input."""

    def test_login_missing_body_returns_422(self, client: TestClient):
        resp = client.post("/api/auth/login")
        assert resp.status_code == 422

    def test_refresh_missing_body_returns_422(self, client: TestClient):
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 422

    def test_password_hash_round_trip(self):
        from api.auth.jwt_handler import hash_password, verify_password

        hashed = hash_password("secret-pass")
        assert verify_password("secret-pass", hashed)
        assert not verify_password("wrong-pass", hashed)
        assert not verify_password("secret-pass", "")


class TestUserEndpoints:
    """Verify user endpoints require authentication."""

    def test_create_user_requires_auth(self, client: TestClient):
        resp = client.post("/api/users", json={"name": "A", "email": "a@b.com"})
        assert resp.status_code == 401

    def test_get_user_requires_auth(self, client: TestClient):
        resp = client.get("/api/users/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 401


class TestRecognitionEndpoints:
    """Verify recognition endpoints require authentication."""

    def test_identify_requires_auth(self, client: TestClient):
        resp = client.post("/api/identify")
        assert resp.status_code == 401

    def test_verify_requires_auth(self, client: TestClient):
        resp = client.post("/api/verify")
        assert resp.status_code == 401
