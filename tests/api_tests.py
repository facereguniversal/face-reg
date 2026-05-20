"""Basic API endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Verify the health check endpoint responds correctly."""

    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/api/health")
        data = resp.json()
        assert data["database"] == "ok"
        assert data["model_server"] in {"ok", "down"}
        assert data["status"] in {"ok", "degraded"}
        if data["status"] == "degraded":
            assert resp.status_code == 503
        else:
            assert resp.status_code == 200

    def test_root_lists_demo_links(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["demo_capture"] == "/demo/capture/"
        assert data["demo_checkin"] == "/demo/checkin/"
        assert data["demo_admin"] == "/demo/admin/"

    def test_demo_static_routes_are_served(self, client: TestClient):
        capture_resp = client.get("/demo/capture/")
        checkin_resp = client.get("/demo/checkin/")
        admin_resp = client.get("/demo/admin/")
        assert capture_resp.status_code == 200
        assert checkin_resp.status_code == 200
        assert admin_resp.status_code == 200
        assert "Guest Enrollment" in capture_resp.text
        assert "Guest Check-In" in checkin_resp.text
        assert "Live Check-Ins" in admin_resp.text


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

    def test_user_search_requires_admin(self, client: TestClient):
        resp = client.get("/api/users?query=a")
        assert resp.status_code == 401


class TestRecognitionEndpoints:
    """Verify recognition endpoints require authentication."""

    def test_validate_requires_auth(self, client: TestClient):
        resp = client.post("/api/faces/validate")
        assert resp.status_code == 401

    def test_identify_requires_auth(self, client: TestClient):
        resp = client.post("/api/identify")
        assert resp.status_code == 401

    def test_verify_requires_auth(self, client: TestClient):
        resp = client.post("/api/verify")
        assert resp.status_code == 401


class TestCheckInRoutes:
    """Verify check-in route authentication boundaries."""

    class FakeRouteFaceService:
        async def _get_embeddings(self, _images):
            return [
                {
                    "embedding": [0.0] * 512,
                    "quality": 0.0,
                    "valid": False,
                    "issues": ["no_face_detected"],
                    "liveness_score": None,
                    "liveness_passed": None,
                    "liveness_mode": "heuristic",
                }
            ]

        @staticmethod
        def _is_valid_embedding_result(_item):
            return False

    def test_checkin_requires_device_credentials(self, client: TestClient):
        resp = client.post(
            "/api/checkin",
            files={"image": ("face.jpg", b"image-bytes", "image/jpeg")},
        )
        assert resp.status_code == 401

    def test_checkin_rejects_bad_device_token(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("CHECKIN_DEVICE_TOKENS", "kiosk-1:secret")
        resp = client.post(
            "/api/checkin",
            headers={"X-Device-Id": "kiosk-1", "X-Device-Token": "wrong"},
            files={"image": ("face.jpg", b"image-bytes", "image/jpeg")},
        )
        assert resp.status_code == 403

    def test_checkin_accepts_multipart_with_valid_device(
        self, client: TestClient, monkeypatch
    ):
        from api.main import app

        monkeypatch.setenv("CHECKIN_DEVICE_TOKENS", "kiosk-1:secret")
        app.state.face_service = self.FakeRouteFaceService()
        resp = client.post(
            "/api/checkin",
            headers={"X-Device-Id": "kiosk-1", "X-Device-Token": "secret"},
            files={"image": ("face.jpg", b"image-bytes", "image/jpeg")},
        )
        assert resp.status_code == 401
        assert resp.json()["status"] == "FAILED"

    def test_live_feed_requires_admin(self, client: TestClient):
        resp = client.get("/api/checkins/live")
        assert resp.status_code == 401

    def test_live_feed_accepts_admin_token(self, client: TestClient):
        from api.auth.jwt_handler import create_access_token

        token = create_access_token(
            "00000000-0000-0000-0000-000000000001",
            role="admin",
        )
        resp = client.get(
            "/api/checkins/live",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["checkins"] == []

    def test_live_websocket_accepts_admin_token(self, client: TestClient):
        from api.auth.jwt_handler import create_access_token

        token = create_access_token(
            "00000000-0000-0000-0000-000000000001",
            role="admin",
        )
        with client.websocket_connect(f"/api/checkins/live/ws?token={token}") as ws:
            assert ws.receive_json() == {"type": "ready"}

    def test_live_websocket_rejects_missing_token(self, client: TestClient):
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/checkins/live/ws"):
                pass
