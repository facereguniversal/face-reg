# API Reference

Base URL: `http://localhost:8000` (development)

All endpoints (except `/api/health` and `/api/auth/*`) require a valid JWT bearer token:

```
Authorization: Bearer <access_token>
```

## Authentication

### POST /api/auth/login

Obtain a JWT access token.

**Request:**
```json
{
  "email": "admin@example.com",
  "password": "secret"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

### POST /api/auth/refresh

Exchange a refresh token for a new access token.

**Request:**
```json
{ "refresh_token": "eyJ..." }
```

**Response:** Same shape as login.

---

## Users

### POST /api/users

Create a new user. **Admin only.**

**Request:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "metadata": { "department": "engineering" }
}
```

**Response `201`:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "created_at": "2026-01-01T00:00:00Z"
}
```

---

### GET /api/users/{id}

Retrieve user metadata.

**Response `200`:**
```json
{
  "user_id": "550e8400-...",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "created_at": "2026-01-01T00:00:00Z",
  "face_count": 3
}
```

---

### DELETE /api/users/{id}

Delete a user and all associated face templates. **Admin only.**

**Response:** `204 No Content`

---

## Face Enrollment

### POST /api/users/{id}/faces

Enroll 4–6 face images for the given user. Images must be sent as `multipart/form-data`.

**Request:**
```
Content-Type: multipart/form-data

images: <file1.jpg>
images: <file2.jpg>
...
```

**Response `201`:**
```json
{
  "template_ids": ["uuid1", "uuid2", "uuid3"],
  "status": "enrolled",
  "quality_scores": [0.92, 0.88, 0.95]
}
```

**Error `422`** if fewer than 1 valid face detected, or quality too low.

---

### GET /api/faces/{template_id}

Get metadata for a specific face template.

**Response `200`:**
```json
{
  "face_id": "uuid1",
  "user_id": "550e8400-...",
  "model": "arcface_r100",
  "quality_score": 0.92,
  "created_at": "2026-01-01T00:00:00Z"
}
```

---

### DELETE /api/faces/{template_id}

Delete a specific face template. **Admin or template owner.**

**Response:** `204 No Content`

---

## Recognition

### POST /api/identify

Identify the face in a submitted image against all enrolled users (1:N search).

**Request:** `multipart/form-data` with `image` field, or JSON:
```json
{ "image_url": "https://example.com/photo.jpg" }
```

**Response `200`:**
```json
{
  "matches": [
    { "user_id": "550e8400-...", "name": "Jane Doe", "score": 0.98 },
    { "user_id": "660e8400-...", "name": "John Smith", "score": 0.76 }
  ],
  "latency_ms": 45
}
```

Returns an empty `matches` array if no face exceeds the similarity threshold.

---

### POST /api/identify/batch

Identify faces in multiple images in one call.

**Request:** `multipart/form-data` with multiple `images` fields.

**Response `200`:**
```json
{
  "results": [
    { "image_index": 0, "matches": [{ "user_id": "...", "score": 0.95 }] },
    { "image_index": 1, "matches": [] }
  ]
}
```

---

### POST /api/verify

Verify whether an image matches a specific user (1:1).

**Request:** `multipart/form-data`:
```
user_id: 550e8400-...
image: <file.jpg>
```

**Response `200`:**
```json
{
  "verified": true,
  "score": 0.94,
  "threshold": 0.6
}
```

---

## Utility

### GET /api/health

Health check. No authentication required.

**Response `200`:**
```json
{
  "status": "ok",
  "model_server": "ok",
  "database": "ok"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

| Code | Meaning |
|---|---|
| `400` | Bad request / invalid input |
| `401` | Missing or invalid token |
| `403` | Insufficient permissions |
| `404` | Resource not found |
| `422` | Validation error (Pydantic) |
| `429` | Rate limit exceeded |
| `500` | Internal server error |
