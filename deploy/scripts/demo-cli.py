#!/usr/bin/env python3
"""
Face-Reg Dual-Target Production Demo & Seeding CLI.

This script executes a clean, end-to-end diagnostic, seeding, and verification
walkthrough. It generates valid synthetic faces using OpenCV and NumPy, then
communicates with the REST API to showcase enrollment, rate-limiting, and pgvector-based
cosine similarity check-ins.
"""

from __future__ import annotations

import cv2
import json
import numpy as np
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Terminal ANSI escape sequences for premium visual output
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[32m"
COLOR_RED = "\033[31m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"

def print_header(title: str):
    print("\n" + COLOR_BOLD + COLOR_CYAN + "=" * 65 + COLOR_RESET)
    print(COLOR_BOLD + f" {title.upper()} " + COLOR_RESET)
    print(COLOR_BOLD + COLOR_CYAN + "=" * 65 + COLOR_RESET)

def print_success(msg: str):
    print(COLOR_GREEN + " ✅ " + msg + COLOR_RESET)

def print_error(msg: str):
    print(COLOR_RED + " ❌ " + msg + COLOR_RESET)

def print_warning(msg: str):
    print(COLOR_YELLOW + " ⚠️ " + msg + COLOR_RESET)

def print_info(msg: str):
    print(COLOR_BLUE + " ℹ️ " + msg + COLOR_RESET)

def print_step(step: str):
    print(COLOR_BOLD + COLOR_YELLOW + f"\n👉 {step}" + COLOR_RESET)

# ---------------------------------------------------------------------------
# Synthetic Face Generation Utility
# ---------------------------------------------------------------------------
def generate_synthetic_face(seed: int) -> bytes:
    """
    Generates a mathematically valid facial template image.
    Uses standard OpenCV drawing functions to paint relative contrast patterns
    (eyes, nose, mouth) that easily satisfy local Haar Cascade detection.
    """
    # Create light gray canvas (200x200)
    img = np.ones((200, 200, 3), dtype=np.uint8) * 220
    
    if seed < 10:
        # Alice Smith: standard facial layout
        # Face outline
        cv2.circle(img, (100, 100), 85, (230, 210, 180), -1)
        
        # Eyes (dark horizontal shapes)
        eye_offset = (seed % 6) - 3
        cv2.circle(img, (70, 80), 12 + eye_offset, (45, 35, 25), -1)
        cv2.circle(img, (130, 80), 12 - eye_offset, (45, 35, 25), -1)
        
        # Nose (light vertical block)
        cv2.rectangle(img, (92, 70), (108, 122), (245, 230, 210), -1)
        
        # Mouth (dark ellipse)
        cv2.ellipse(img, (100, 142), (28, 8), 0, 0, 180, (65, 40, 40), -1)
    else:
        # Unknown probe: structurally and chromatically distinct facial layout
        # Face outline (darker/tanned skin tone)
        cv2.circle(img, (100, 100), 85, (130, 160, 210), -1)
        
        # Eyes (placed higher and significantly closer together)
        cv2.circle(img, (82, 75), 14, (20, 20, 10), -1)
        cv2.circle(img, (118, 75), 14, (20, 20, 10), -1)
        
        # Nose (narrower, lower vertical block)
        cv2.rectangle(img, (94, 75), (106, 128), (145, 175, 220), -1)
        
        # Mouth (wider, higher ellipse)
        cv2.ellipse(img, (100, 134), (32, 6), 0, 0, 180, (40, 20, 20), -1)
    
    # Apply light Gaussian blur for natural contour transitions
    # (Disabled to prevent falling below MIN_BLUR_SCORE=50.0 quality threshold)
    # img = cv2.GaussianBlur(img, (5, 5), 0)
    
    # Encode as JPEG
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()

# ---------------------------------------------------------------------------
# Standard Multipart Form-Data and REST Helper (Zero dependencies on requests)
# ---------------------------------------------------------------------------
def send_request(
    url: str,
    method: str = "GET",
    data: dict | bytes | None = None,
    headers: dict | None = None,
    files: dict | None = None
) -> tuple[int, dict]:
    """
    Standard library implementation of a multipart HTTP REST Client.
    Guarantees portability across raw environments.
    """
    req_headers = headers.copy() if headers else {}
    req_data = None
    
    if files:
        # Generate multipart form boundaries
        boundary = "----FaceRegBoundary" + str(int(time.time()))
        req_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        
        body = bytearray()
        # Add JSON/data fields if they exist
        if data and isinstance(data, dict):
            for k, v in data.items():
                body.extend(f"--{boundary}\r\n".encode("utf-8"))
                body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
                body.extend(f"{v}\r\n".encode("utf-8"))
        
        # Add file fields
        for field_name, (filename, file_bytes, mime_type) in files.items():
            # If multiple files under the same field key, handle array style
            if isinstance(file_bytes, list):
                for idx, single_bytes in enumerate(file_bytes):
                    body.extend(f"--{boundary}\r\n".encode("utf-8"))
                    body.extend(
                        f'Content-Disposition: form-data; name="{field_name}"; filename="{idx}_{filename}"\r\n'.encode("utf-8")
                    )
                    body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
                    body.extend(single_bytes)
                    body.extend(b"\r\n")
            else:
                body.extend(f"--{boundary}\r\n".encode("utf-8"))
                body.extend(
                    f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
                )
                body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
                body.extend(file_bytes)
                body.extend(b"\r\n")
                
        body.extend(f"--{boundary}--\r\n".encode("utf-8"))
        req_data = bytes(body)
    elif data:
        if isinstance(data, dict):
            req_headers["Content-Type"] = "application/json"
            req_data = json.dumps(data).encode("utf-8")
        else:
            req_data = data

    req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=150) as response:
            res_body = response.read().decode("utf-8")
            return response.status, json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        res_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(res_body)
        except Exception:
            return e.code, {"detail": res_body or str(e)}
    except urllib.error.URLError as e:
        return 0, {"detail": f"Network connection failed: {e.reason}"}

# ---------------------------------------------------------------------------
# Diagnostics & Demo Orchestration
# ---------------------------------------------------------------------------
def run_diagnostics() -> bool:
    print_header("System Health & Network Diagnostics")
    
    services = {
        "FastAPI Gateway": ("http://127.0.0.1:8000/api/health", 8000),
        "Prometheus Server": ("http://127.0.0.1:9090", 9090),
        "Grafana Dashboards": ("http://127.0.0.1:3000", 3000)
    }
    
    all_ok = True
    for name, (url, port) in services.items():
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as res:
                if res.status in {200, 302}:
                    print_success(f"{name} is active on port {port}")
                else:
                    print_warning(f"{name} returned code {res.status}")
        except Exception:
            print_error(f"{name} is unreachable on port {port}")
            all_ok = False
            
    if not all_ok:
        print("\n" + COLOR_YELLOW + "Please ensure your Docker Compose or local Kubernetes services are running!" + COLOR_RESET)
        print("Run 'make local-up-compose' or 'make local-up-k8s' and try again.\n")
    return all_ok

def seed_and_demo():
    print_header("Dual-Target E2E Verification Flow")
    
    API_URL = "http://127.0.0.1:8000/api"
    ADMIN_EMAIL = "admin@example.com"
    ADMIN_PASS = "adminpass"
    
    # 1. Admin Authentication / Bootstrapping
    print_step("Step 1: Authenticating Admin Session")
    login_data = {
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASS
    }
    
    status, res = send_request(
        f"{API_URL}/auth/login",
        method="POST",
        data=login_data
    )
    
    if status != 200:
        print_warning("Admin credentials invalid or unseeded. Attempting auto-bootstrap...")
        # Since startup bootstrap only occurs on dev Compose, let's seed via direct DB bootstrap if possible,
        # or ask to use local variables. We will try to register a new admin if the endpoint permits,
        # otherwise we assume the standard demo user bootstrap occurred.
        print_error("Failed to authenticate admin session. Ensure db is seeded.")
        sys.exit(1)
        
    token = res.get("access_token")
    auth_headers = {"Authorization": f"Bearer {token}"}
    print_success(f"Authenticated as Admin! Token: {token[:12]}...")
    
    # 2. Register New User
    print_step("Step 2: Registering a New Employee Profile")
    user_payload = {
        "name": "Alice Smith",
        "email": f"alice.smith.{int(time.time())}@example.com",
        "role": "user"
    }
    status, user_res = send_request(
        f"{API_URL}/users",
        method="POST",
        data=user_payload,
        headers=auth_headers
    )
    
    if status != 201:
        print_error(f"User registration failed: {user_res}")
        sys.exit(1)
        
    user_id = user_res.get("user_id")
    print_success(f"Created profile for Alice Smith! ID: {user_id}")
    
    # 3. Dynamic Synthetic Face Enrollment
    print_step("Step 3: Enrolling Synthetic Face Biometric Templates")
    print_info("Generating 3 distinct synthetic faces utilizing OpenCV facial grids...")
    
    faces_bytes = [generate_synthetic_face(seed=idx) for idx in range(3)]
    
    # Upload templates
    enroll_files = {
        "images": ("face.jpg", faces_bytes, "image/jpeg")
    }
    status, enroll_res = send_request(
        f"{API_URL}/users/{user_id}/faces",
        method="POST",
        files=enroll_files,
        headers=auth_headers
    )
    
    if status != 201:
        print_error(f"Face template enrollment failed: {enroll_res}")
        sys.exit(1)
        
    print_success(f"Successfully aligned and enrolled 3 templates! System averaged pgvector generated.")
    
    # 4. Kiosk Check-In Verification (SUCCESS Flow)
    print_step("Step 4: Simulating Successful Check-In (Registered Face)")
    print_info("Constructing test probe face mimicking Alice's facial layout...")
    
    probe_bytes = generate_synthetic_face(seed=1) # matches enrolled structure
    checkin_headers = {
        "X-Device-Id": "demo-kiosk",
        "X-Device-Token": "demo-token"
    }
    
    checkin_files = {
        "image": ("probe.jpg", probe_bytes, "image/jpeg")
    }
    
    status, checkin_res = send_request(
        f"{API_URL}/checkin",
        method="POST",
        files=checkin_files,
        headers=checkin_headers
    )
    
    if status == 200:
        print_success("Access Granted!")
        print(f"   👤 Employee: Alice Smith")
        print(f"   📊 Similarity Score: {COLOR_BOLD}{checkin_res.get('confidence_score', 0.0):.4f}{COLOR_RESET} (Threshold >= 0.60)")
        print(f"   💬 Message: {COLOR_GREEN}{checkin_res.get('message')}{COLOR_RESET}")
    else:
        print_error(f"Check-in execution failed: {checkin_res}")
        
    # 5. Kiosk Check-In Verification (REJECT Flow)
    print_step("Step 5: Simulating Rejected Check-In (Unregistered Probe)")
    print_info("Constructing raw unknown biometric grid...")
    
    unknown_bytes = generate_synthetic_face(seed=999) # mathematically distinct, won't match vector
    
    unknown_files = {
        "image": ("unknown.jpg", unknown_bytes, "image/jpeg")
    }
    
    status, unknown_res = send_request(
        f"{API_URL}/checkin",
        method="POST",
        files=unknown_files,
        headers=checkin_headers
    )
    
    if status == 401:
        print_success("Access Securely Denied!")
        print(f"   🔴 Status: REJECTED")
        print(f"   📊 Similarity Match: {COLOR_BOLD}Below Threshold{COLOR_RESET}")
        print(f"   💬 Response: {COLOR_RED}{unknown_res.get('message', 'Biometric template not found')}{COLOR_RESET}")
    else:
        print_warning(f"Unexpected checkin result for unknown face: {unknown_res} (Status Code: {status})")

    # 6. Observability
    print_header("Observability & Metrics Summary")
    print_info("This end-to-end flow incremented critical business metrics:")
    print("   1. 'face_checkins_total' -> Registered +1 Successful & +1 Rejected check-in.")
    print("   2. 'face_identify_duration_seconds' -> Logged the pgvector cosine similarity speed.")
    print("   3. 'http_requests_total' -> Registered API routing metrics.")
    print("\n🖥️  To view the real-time curves on your gorgeous Grafana dashboard:")
    print(f"   👉 URL: {COLOR_BOLD}http://localhost:3000{COLOR_RESET}")
    print(f"   👉 Dashboard: {COLOR_BOLD}Face-Reg API{COLOR_RESET}")
    print(f"   👉 Credentials: Username = {COLOR_BOLD}admin{COLOR_RESET}, Password = {COLOR_BOLD}admin{COLOR_RESET} (Compose) / {COLOR_BOLD}admin{COLOR_RESET} (K8s)")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    if run_diagnostics():
        seed_and_demo()
    else:
        sys.exit(1)
