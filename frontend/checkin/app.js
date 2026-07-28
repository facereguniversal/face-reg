const IS_LOCAL = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE = IS_LOCAL
  ? "http://localhost:8000/api"
  : "https://face-reg-production.up.railway.app/api";
// We allow query token for auth testing if needed
const urlParams = new URLSearchParams(window.location.search);
const TOKEN = urlParams.get("token") || "";

function getHeaders() {
  const headers = {};
  if (TOKEN) {
    headers["Authorization"] = `Bearer ${TOKEN}`;
  }
  return headers;
}

const video = document.getElementById("webcam");
const statusText = document.getElementById("status-text");
const successCard = document.getElementById("success-card");
const scannerOverlay = document.getElementById("scanner-overlay");
const scannerInterface = document.querySelector(".scanner-interface");
let stream = null;
let scanInterval = null;
let isIdentified = false;

// Initialize Webcam
async function startWebcam() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        facingMode: "user",
      },
    });
    video.srcObject = stream;

    video.addEventListener("loadedmetadata", () => {
      video.play();
      startScanning();
    });
  } catch (err) {
    statusText.textContent = "We couldn't open the camera";
    console.error("Camera Error:", err);
  }
}

// Extract frame as Blob (downscaled to 320px for 10x faster inference)
function getFrameBlob() {
  return new Promise((resolve) => {
    const canvas = document.createElement("canvas");
    const targetWidth = 320;
    const srcW = video.videoWidth || 640;
    const srcH = video.videoHeight || 480;
    const scale = Math.min(1, targetWidth / srcW);

    canvas.width = Math.round(srcW * scale);
    canvas.height = Math.round(srcH * scale);
    const ctx = canvas.getContext("2d");

    // Display is mirrored via CSS, mirror canvas to send true orientation
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(resolve, "image/jpeg", 0.75);
  });
}

let isScanningFrame = false;

function startScanning() {
  isIdentified = false;
  isScanningFrame = false;
  if (scanInterval) clearInterval(scanInterval);

  successCard.classList.remove("visible");
  setTimeout(() => {
    successCard.classList.add("hidden");
    if (!isIdentified) {
      successCard.style.display = "none";
    }
  }, 500);

  scannerInterface.classList.remove("success");
  scannerOverlay.style.display = "block";
  statusText.textContent = "Position your face in the frame";

  scanInterval = setInterval(scanFrame, 2500); // Check every 2.5 seconds
}

async function scanFrame() {
  if (isIdentified || isScanningFrame) return;
  isScanningFrame = true;

  try {
    const blob = await getFrameBlob();
    const formData = new FormData();
    formData.append("image", blob, `scan_${Date.now()}.jpg`);

    console.log("[Checkin] Calling identify API:", `${API_BASE}/identify`);
    const response = await fetch(`${API_BASE}/identify`, {
      method: "POST",
      body: formData,
      headers: getHeaders(),
    });

    console.log("[Checkin] Response status:", response.status);

    if (response.ok) {
      const result = await response.json();
      console.log("[Checkin] Result:", JSON.stringify(result));
      if (result.matches && result.matches.length > 0) {
        const match = result.matches[0];
        console.log(
          "[Checkin] Best match:",
          match.name,
          "class:",
          match.student_class,
          "score:",
          match.score,
        );
        if (match.score > 0.4) {
          handleSuccess(match);
        } else {
          statusText.textContent = "Move closer to the camera";
        }
      } else {
        console.log("[Checkin] No matches found");
        statusText.textContent = "No matching student found. Please enroll first.";
      }
    } else {
      const errText = await response.text();
      console.warn("[Checkin] Identify error:", response.status, errText);
      statusText.textContent = "Check-in service unavailable";
    }
  } catch (e) {
    console.error("[Checkin] Request failed:", e);
    statusText.textContent = "Reconnecting to check-in service...";
  } finally {
    isScanningFrame = false;
  }
}

function handleSuccess(match) {
  isIdentified = true;
  clearInterval(scanInterval);

  const studentName = match.name || "Student";
  statusText.textContent = `Student recognized: ${studentName}!`;

  const nameEl = document.getElementById("student-name");
  const classEl = document.getElementById("student-class");
  const timeEl = document.getElementById("checkin-time");

  if (nameEl) nameEl.textContent = studentName;
  if (classEl) classEl.textContent = match.student_class || "Class Unassigned";
  if (timeEl)
    timeEl.textContent = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

  scannerOverlay.style.display = "none";
  scannerInterface.classList.add("success");

  successCard.classList.remove("hidden");
  successCard.style.display = "flex";
  setTimeout(() => {
    successCard.classList.add("visible");
  }, 50);

  // After 6 seconds, reset back to scanning mode for next student
  setTimeout(() => {
    startScanning();
  }, 6000);
}

// Init Application
startWebcam();
