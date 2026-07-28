# School Check-in System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the facial recognition system into a School Attendance and Student Check-in System with student name, class/grade tracking, and personalized student greeting upon check-in.

**Architecture:** Extend FastAPI Pydantic models (`MatchResult`, `UserCreate`, `UserResponse`) to include `student_class`. Update database/service handlers to store `student_class` in user metadata. Update frontend HTML/JS/CSS to present school branding, enrollment forms (Name + Class), and personalized student check-in welcome card.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, HTML5/CSS3/Vanilla JS (ES6+), OpenCV / FAISS background services.

## Global Constraints
- Python type annotations & Pydantic v2 schemas
- HTML/CSS/JS without external heavy frameworks (vanilla)
- Preserve API route paths (`/api/identify`, `/api/users/{user_id}/faces`, etc.)

---

### Task 1: API Schemas & Service Updates (Backend)

**Files:**
- Modify: `api/models/schemas.py`
- Modify: `api/services/user_service.py`
- Modify: `api/services/face_service.py`
- Modify: `api/routes/identify.py`

**Interfaces:**
- `MatchResult`: `user_id: uuid.UUID`, `name: str`, `student_class: str = "Class Unassigned"`, `score: float`
- `UserCreate`: `name: str`, `email: EmailStr`, `student_class: str | None = None`, `metadata: dict[str, Any] | None = None`
- `UserResponse`: `user_id: uuid.UUID`, `name: str`, `email: EmailStr`, `student_class: str = "Class Unassigned"`, `created_at: datetime`, `face_count: int`

- [ ] **Step 1: Update `api/models/schemas.py`**

```python
class MatchResult(BaseModel):
    user_id: uuid.UUID
    name: str
    student_class: str = "Class Unassigned"
    score: float
```

- [ ] **Step 2: Update `api/services/user_service.py` & `face_service.py` to extract `student_class`**

In `face_service.py` during `identify`:
```python
student_class = (user.extra_metadata or {}).get("student_class", "Class Unassigned") if user.extra_metadata else "Class Unassigned"
matches.append(
    MatchResult(
        user_id=user.id,
        name=user.name,
        student_class=student_class,
        score=round(hit["score"], 4),
    )
)
```

- [ ] **Step 3: Update `enroll_demo` in `api/routes/identify.py`**
Store `"student_class": "Grade 10-A"` in `extra_metadata` when creating demo students.

- [ ] **Step 4: Commit backend changes**

```bash
git add api/models/schemas.py api/services/face_service.py api/services/user_service.py api/routes/identify.py
git commit -m "feat(api): add student_class support to MatchResult and user services"
```

---

### Task 2: Student Enrollment UI Updates (Frontend - Capture)

**Files:**
- Modify: `frontend/capture/index.html`
- Modify: `frontend/capture/app.js`
- Modify: `frontend/capture/style.css`

- [ ] **Step 1: Update `frontend/capture/index.html` header and student details input form**

```html
<header>
  <h1>School Attendance System</h1>
  <p>Student Biometric Registration</p>
</header>
```
Add input fields for Student Full Name and Class/Grade:
```html
<div class="student-form-group">
  <input type="text" id="student-name-input" placeholder="Student Full Name (e.g. Alex Smith)" required />
  <input type="text" id="student-class-input" placeholder="Class / Grade (e.g. Grade 10-A)" required />
</div>
```

- [ ] **Step 2: Update `frontend/capture/app.js` to send student name & class**

Include `student_name` and `student_class` in enrollment request payload or query metadata.

- [ ] **Step 3: Commit capture UI changes**

```bash
git add frontend/capture/index.html frontend/capture/app.js frontend/capture/style.css
git commit -m "feat(ui): update student enrollment UI with name and class inputs"
```

---

### Task 3: Student Check-in Kiosk UI Updates (Frontend - Checkin)

**Files:**
- Modify: `frontend/checkin/index.html`
- Modify: `frontend/checkin/app.js`
- Modify: `frontend/checkin/style.css`

- [ ] **Step 1: Update `frontend/checkin/index.html` wording & success card structure**

```html
<div class="header">
    <h1>Oakridge Academy</h1>
    <p>Student Check-In Kiosk</p>
</div>
```
Status text:
```html
<span id="status-text">Scanning for Student...</span>
```
Success card:
```html
<div class="success-card hidden" id="success-card">
    <div class="check-icon">✓</div>
    <h2>Welcome to School, <span id="student-name"></span>! 👋</h2>
    <p class="student-detail">Class: <strong id="student-class"></strong></p>
    <p class="subtitle">Attendance verified. Have a wonderful day in class!</p>
</div>
```

- [ ] **Step 2: Update `frontend/checkin/app.js` to display student name and class upon match**

```javascript
function handleSuccess(match) {
    isIdentified = true;
    clearInterval(scanInterval);
    
    statusText.textContent = "Student Recognized";
    document.getElementById('student-name').textContent = match.name || "Student";
    document.getElementById('student-class').textContent = match.student_class || "Class Unassigned";
    
    scannerOverlay.style.display = 'none';
    scannerInterface.classList.add('success');
    
    successCard.classList.remove('hidden');
    setTimeout(() => {
        successCard.classList.add('visible');
    }, 50);

    setTimeout(() => {
        startScanning();
    }, 6000);
}
```

- [ ] **Step 3: Commit checkin UI changes**

```bash
git add frontend/checkin/index.html frontend/checkin/app.js frontend/checkin/style.css
git commit -m "feat(ui): update checkin kiosk wording and personalize student welcome card"
```

---

### Task 4: Verification

- [ ] **Step 1: Verify API syntax and schemas**
Run pytest / python sanity check.

- [ ] **Step 2: Verify HTML/JS file syntax**
Ensure no unclosed tags or JavaScript syntax errors.
