# School Check-in System & Student Enrollment Design

## Overview
Transform the face recognition system from a hotel kiosk template into a School Attendance and Student Check-in System. The system registers students with their name and class/grade, identifies students via webcam facial recognition, and welcomes each student by name upon successful check-in.

## Design Details

### 1. API & Data Schemas (`api/models/schemas.py`, `api/services/face_service.py`, `api/services/user_service.py`)
- **`MatchResult` Schema**:
  - `user_id`: UUID
  - `name`: str
  - `student_class`: str (Optional/defaulting to "Class Unassigned")
  - `score`: float
- **`UserCreate` & `UserResponse` Schemas**:
  - Add optional `student_class: str | None = None`
- **User Service & Face Service**:
  - Store `student_class` in `user.extra_metadata["student_class"]` during user creation or demo enrollment.
  - When matching faces in `face_service.py`, retrieve `student_class` from `user.extra_metadata` and attach it to the `MatchResult`.

### 2. Student Enrollment UI (`frontend/capture/`)
- **Wording**: Update branding to "School Attendance System - Student Registration".
- **Form Inputs**:
  - Student Name (`<input id="student-name" placeholder="Student Full Name">`)
  - Class / Grade (`<input id="student-class" placeholder="Class / Grade (e.g. Grade 10-A)">`)
- **Enrollment Flow**:
  - Captures face samples, sends student details (`name`, `student_class`) to API.

### 3. Student Check-in Kiosk UI (`frontend/checkin/`)
- **Wording**: Update title/header to "Oakridge Academy – Student Check-In".
- **Status State**: Update scanner text to "Scanning for Student...".
- **Success State**:
  - Main Welcome: "Welcome to School, <span id="student-name"></span>!"
  - Sub-details: "Class: <span id="student-class"></span>"
  - Subtitle: "Attendance recorded. Have a wonderful day at school!"

## Verification Plan
- Verify API response for `/api/identify` includes `student_class`.
- Verify Student Enrollment UI accepts name and class and submits correctly.
- Verify Check-in Kiosk UI displays personalized greeting and class name when student is recognized.
