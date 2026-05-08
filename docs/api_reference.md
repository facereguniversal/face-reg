# API Reference

Base URL: `http://localhost:8000`

All endpoints except `/`, `/docs`, `/api/health`, `/demo/capture/`, `/demo/checkin/`, and `/api/auth/*` require a bearer token.

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
  "created_at": "2026-01-01T00:00:00Z",
  "face_count": 0
}
```

### GET /api/users/{user_id}

Response `200`:

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "created_at": "2026-01-01T00:00:00Z",
  "face_count": 4
}
```

### DELETE /api/users/{user_id}

Response: `204 No Content`

## Faces

### POST /api/users/{user_id}/faces

Multipart enrollment with 4 to 6 `images` fields.

Response `201`:

```json
{
  "template_ids": [
    "uuid1",
    "uuid2",
    "uuid3",
    "uuid4"
  ],
  "status": "enrolled",
  "quality_scores": [0.92, 0.88, 0.95, 0.91]
}
```

Common failure responses:

- `400` when fewer than four images pass local quality checks.
- `400` when fewer than four images produce valid embeddings.
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

Both UIs call the API on the same host origin and accept a `token` query parameter for demo-only auth bootstrapping.
