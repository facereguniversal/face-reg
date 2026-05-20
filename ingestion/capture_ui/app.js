const API_BASE = `${window.location.origin}/api`;
const params = new URLSearchParams(window.location.search);
const TOKEN = params.get("token") || "";

const profilePane = document.getElementById("profile-pane");
const capturePane = document.getElementById("capture-pane");
const profileForm = document.getElementById("profile-form");
const video = document.getElementById("webcam");
const guide = document.getElementById("face-guide");
const feedbackPanel = document.getElementById("feedback-panel");
const feedbackText = document.getElementById("feedback-text");
const captureBtn = document.getElementById("capture-btn");
const submitBtn = document.getElementById("submit-btn");
const gallery = document.getElementById("gallery");
const poseList = document.getElementById("pose-list");
const createdUserName = document.getElementById("created-user-name");

const poses = ["Straight", "Slight Left", "Slight Right", "Slight Up", "Slight Down"];
const MIN_FRAMES = 3;
const MAX_FRAMES = 5;

let currentUser = null;
let stream = null;
let capturedFrames = [];
let isValidating = false;

function headers(json = false) {
  const result = {};
  if (TOKEN) result.Authorization = `Bearer ${TOKEN}`;
  if (json) result["Content-Type"] = "application/json";
  return result;
}

function setFeedback(message, type = "neutral") {
  feedbackText.textContent = message;
  feedbackPanel.dataset.type = type;
  guide.dataset.type = type;
}

function setStep(step) {
  document.querySelectorAll("[data-step-dot]").forEach((item) => {
    item.classList.toggle("active", item.dataset.stepDot === step);
  });
}

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = profileForm.querySelector("button");
  button.disabled = true;
  button.textContent = "Creating";

  try {
    const body = {
      name: document.getElementById("name-input").value.trim(),
      email: document.getElementById("email-input").value.trim(),
      metadata: { enrollment_source: "capture_ui" },
    };
    const response = await fetch(`${API_BASE}/users`, {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Profile creation failed");
    }
    currentUser = payload;
    createdUserName.textContent = payload.name;
    profilePane.hidden = true;
    capturePane.hidden = false;
    setStep("capture");
    renderPoses();
    await startWebcam();
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Create Profile";
  }
});

async function startWebcam() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 960 }, height: { ideal: 720 }, facingMode: "user" },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    captureBtn.disabled = false;
    updateCaptureButton();
    validationLoop();
  } catch (error) {
    setFeedback("Camera unavailable", "error");
  }
}

async function validationLoop() {
  if (!capturePane.hidden && !isValidating && capturedFrames.length < MAX_FRAMES) {
    await validateCurrentFrame(false);
  }
  window.setTimeout(validationLoop, 1800);
}

async function frameBlob() {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
}

async function validateCurrentFrame(showErrors = true) {
  isValidating = true;
  try {
    const blob = await frameBlob();
    const form = new FormData();
    form.append("image", blob, "validate.jpg");
    const response = await fetch(`${API_BASE}/faces/validate`, {
      method: "POST",
      headers: headers(),
      body: form,
    });
    const payload = await response.json();
    if (payload.passed) {
      setFeedback("Ready to capture", "success");
      return { passed: true, blob };
    }
    if (showErrors) {
      setFeedback(`Try again: ${payload.issues.join(", ")}`, "error");
    } else {
      setFeedback("Position face in the frame", "neutral");
    }
    return { passed: false, blob };
  } catch (error) {
    console.warn(error);
    setFeedback("Validation unavailable", "neutral");
    return { passed: true, blob: await frameBlob() };
  } finally {
    isValidating = false;
  }
}

captureBtn.addEventListener("click", async () => {
  if (capturedFrames.length >= MAX_FRAMES) return;
  captureBtn.disabled = true;
  captureBtn.textContent = "Checking";

  const validation = await validateCurrentFrame(true);
  if (validation.passed) {
    capturedFrames.push(validation.blob);
    renderGallery();
    renderPoses();
  }
  updateCaptureButton();
});

submitBtn.addEventListener("click", async () => {
  if (!currentUser || capturedFrames.length < MIN_FRAMES) return;
  submitBtn.disabled = true;
  submitBtn.textContent = "Enrolling";
  setStep("submit");

  const form = new FormData();
  capturedFrames.forEach((blob, index) => {
    form.append("images", blob, `enroll_${index}.jpg`);
  });

  try {
    const response = await fetch(`${API_BASE}/users/${currentUser.user_id}/faces`, {
      method: "POST",
      headers: headers(),
      body: form,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Enrollment failed");
    }
    setFeedback("Enrollment complete", "success");
    submitBtn.textContent = "Enrolled";
  } catch (error) {
    alert(error.message);
    setStep("capture");
    submitBtn.disabled = false;
    submitBtn.textContent = "Complete Enrollment";
  }
});

function updateCaptureButton() {
  if (capturedFrames.length >= MAX_FRAMES) {
    captureBtn.disabled = true;
    captureBtn.textContent = "All Captures Complete";
    return;
  }
  const pose = poses[capturedFrames.length];
  captureBtn.disabled = false;
  captureBtn.textContent = `Capture ${pose}`;
  submitBtn.disabled = capturedFrames.length < MIN_FRAMES;
}

function renderPoses() {
  poseList.innerHTML = "";
  poses.forEach((pose, index) => {
    const item = document.createElement("li");
    item.textContent = pose;
    if (index < capturedFrames.length) item.className = "done";
    if (index === capturedFrames.length) item.className = "active";
    poseList.appendChild(item);
  });
}

function renderGallery() {
  gallery.innerHTML = "";
  capturedFrames.forEach((blob, index) => {
    const item = document.createElement("button");
    item.className = "thumb";
    item.type = "button";
    item.title = "Remove capture";
    const img = document.createElement("img");
    img.src = URL.createObjectURL(blob);
    item.appendChild(img);
    item.addEventListener("click", () => {
      capturedFrames.splice(index, 1);
      renderGallery();
      renderPoses();
      updateCaptureButton();
    });
    gallery.appendChild(item);
  });
}

window.addEventListener("beforeunload", () => {
  if (stream) stream.getTracks().forEach((track) => track.stop());
});
