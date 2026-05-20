# API Reference

Base URL: `http://localhost:8000`

All endpoints except `/`, `/docs`, `/api/health`, `/demo/capture/`, `/demo/checkin/`, `/demo/admin/`, `/api/checkin`, and `/api/auth/*` require a bearer token.

```http
Authorization: Bearer <access_token>
```

## Authentication

### POST /api/auth/login

Request:

```json
{
  "email": "admin@example.com",
  "password": "adminpass"
}
```

Response:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### POST /api/auth/refresh

Request:

```json
{
  "refresh_token": "eyJ..."
}
```

Response: same shape as login.

## Users

### POST /api/users

Admin-only user creation.

Request:

```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "metadata": {
    "group": "demo"
  }
}
```

Response `201`:

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "role": "user",
  "created_at": "2026-01-01T00:00:00Z",
  "face_count": 0,
  "last_checkin": null
}
```

### GET /api/users?query=&limit=

Admin-only user search for manual override workflows.

Response `200`:

```json
{
  "users": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Jane Doe",
      "email": "jane@example.com",
      "role": "user",
      "last_checkin": null
    }
  ]
}
```

### GET /api/users/{user_id}

Response `200`:

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "role": "user",
  "created_at": "2026-01-01T00:00:00Z",
  "face_count": 1,
  "last_checkin": null
}
```

### DELETE /api/users/{user_id}

Response: `204 No Content`

## Faces

### POST /api/users/{user_id}/faces

Multipart enrollment with 3 to 5 `images` fields. Valid embeddings are averaged into one normalized template.

Response `201`:

```json
{
  "template_ids": [
    "uuid1"
  ],
  "status": "enrolled",
  "quality_scores": [0.92, 0.88, 0.95, 0.91]
}
```

Common failure responses:

- `400` when fewer than three images pass local quality checks.
- `400` when fewer than three images produce valid embeddings.
- `404` when the target user does not exist.

### POST /api/faces/validate

Multipart request with a single `image` field.

Response `200`:

```json
{
  "passed": true,
  "quality_score": 0.91,
  "issues": []
}
```

Rejected example:

```json
{
  "passed": false,
  "quality_score": null,
  "issues": ["invalid_embedding"]
}
```

### GET /api/faces/{template_id}

Response `200`:

```json
{
  "face_id": "uuid1",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "arcface_r100",
  "quality_score": 0.92,
  "created_at": "2026-01-01T00:00:00Z"
}
```

### DELETE /api/faces/{template_id}

Response: `204 No Content`

## Recognition

### POST /api/checkin

Kiosk-only check-in endpoint. Requires device headers:

```http
X-Device-Id: demo-kiosk
X-Device-Token: demo-token
```

Accepts either multipart `image` or JSON `image_base64`.

Success response `200`:

```json
{
  "status": "SUCCESS",
  "message": "Welcome, Jane Doe.",
  "user": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Jane Doe",
    "email": "jane@example.com",
    "role": "user"
  },
  "checkin": {
    "id": "checkin-uuid",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "checkin_time": "2026-01-01T00:00:00Z",
    "status": "SUCCESS",
    "device_or_location_id": "demo-kiosk",
    "confidence_score": 0.94
  },
  "confidence_score": 0.94,
  "threshold": 0.6,
  "cooldown_seconds": null,
  "issues": []
}
```

Other outcomes:

- `200` with `ALREADY_CHECKED_IN` during the cooldown window.
- `401` with `FAILED` when no known face exceeds the threshold.
- `403` with `SPOOF_DETECTED` when liveness fails.

### GET /api/checkins/live

Admin-only polling endpoint. Query params: `limit`, `since`, `include_failed`.

### WS /api/checkins/live/ws?token=<admin_access_token>

Admin-only WebSocket stream. Sends `{ "type": "ready" }` on connect and `{ "type": "checkin", "checkin": ... }` for new events.

### POST /api/checkins/manual

Admin-only manual override.

Request:

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "device_or_location_id": "front-desk",
  "reason": "Camera could not verify mask"
}
```

### POST /api/identify

Multipart request with one `image` field.

Response `200`:

```json
{
  "matches": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Jane Doe",
      "score": 0.98
    }
  ],
  "latency_ms": 42.7
}
```

If no face can be embedded or no match exceeds the threshold, `matches` is empty.

### POST /api/identify/batch

Multipart request with repeated `images` fields.

Response `200`:

```json
{
  "results": [
    {
      "image_index": 0,
      "matches": [
        {
          "user_id": "550e8400-e29b-41d4-a716-446655440000",
          "name": "Jane Doe",
          "score": 0.98
        }
      ]
    },
    {
      "image_index": 1,
      "matches": []
    }
  ]
}
```

### POST /api/verify

Multipart request:

```text
user_id: 550e8400-e29b-41d4-a716-446655440000
image: <file.jpg>
```

Response `200`:

```json
{
  "verified": true,
  "score": 0.94,
  "threshold": 0.6
}
```

## Utility

### GET /api/health

Response `200`:

```json
{
  "status": "ok",
  "database": "ok",
  "model_server": "ok",
  "model_mode": "insightface"
}
```

## Demo UI Paths

The browser demos are served by the API service:

- `GET /demo/capture/`
- `GET /demo/checkin/`
- `GET /demo/admin/`

Capture and admin accept a `token` query parameter for demo-only admin auth. Check-in accepts `deviceId` and `deviceToken` query parameters for kiosk auth.
