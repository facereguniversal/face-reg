const IS_LOCAL = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE = IS_LOCAL
    ? "http://localhost:8000/api"
    : "https://face-reg-production.up.railway.app/api";
// We allow query token for auth testing if needed
const urlParams = new URLSearchParams(window.location.search);
const TOKEN = urlParams.get('token') || "";

function getHeaders() {
    const headers = {};
    if (TOKEN) {
        headers['Authorization'] = `Bearer ${TOKEN}`;
    }
    return headers;
}

const video = document.getElementById('webcam');
const statusText = document.getElementById('status-text');
const successCard = document.getElementById('success-card');
const scannerOverlay = document.getElementById('scanner-overlay');
const scannerInterface = document.querySelector('.scanner-interface');
const guestIdSpan = document.getElementById('guest-id');

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
                facingMode: "user"
            }
        });
        video.srcObject = stream;
        
        video.addEventListener('loadedmetadata', () => {
            startScanning();
        });
    } catch (err) {
        statusText.textContent = "Camera Initialization Error";
        console.error("Camera Error:", err);
    }
}

// Extract frame as Blob
function getFrameBlob() {
    return new Promise((resolve) => {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        // The display is mirrored via CSS, so we mirror the canvas to send true orientation
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0);
        canvas.toBlob(resolve, 'image/jpeg', 0.9);
    });
}

function startScanning() {
    isIdentified = false;
    successCard.classList.remove('visible');
    // timeout strictly so CSS transition finishes before pointer-events hides it
    setTimeout(() => successCard.classList.add('hidden'), 500); 
    
    scannerInterface.classList.remove('success');
    scannerOverlay.style.display = 'block';
    statusText.textContent = "Scanning for Student...";
    
    scanInterval = setInterval(scanFrame, 2000); // Check every 2 seconds
}

async function scanFrame() {
    if (isIdentified) return;
    
    try {
        const blob = await getFrameBlob();
        const formData = new FormData();
        formData.append("image", blob, `scan_${Date.now()}.jpg`);

        console.log("[Checkin] Calling identify API:", `${API_BASE}/identify`);
        const response = await fetch(`${API_BASE}/identify`, {
            method: 'POST',
            body: formData,
            headers: getHeaders()
        });

        console.log("[Checkin] Response status:", response.status);

        if (response.ok) {
            const result = await response.json();
            console.log("[Checkin] Result:", JSON.stringify(result));
            if (result.matches && result.matches.length > 0) {
                const match = result.matches[0];
                console.log("[Checkin] Best match:", match.name, "class:", match.student_class, "score:", match.score);
                if (match.score > 0.4) {
                    handleSuccess(match);
                } else {
                    statusText.textContent = `Score low: ${match.score.toFixed(2)}`;
                }
            } else {
                console.log("[Checkin] No matches found");
            }
        } else {
            const errText = await response.text();
            console.warn("[Checkin] Identify error:", response.status, errText);
            statusText.textContent = `API Error: ${response.status}`;
        }
    } catch (e) {
        console.error("[Checkin] Request failed:", e);
        statusText.textContent = "Backend offline";
    }
}

function handleSuccess(match) {
    isIdentified = true;
    clearInterval(scanInterval);
    
    statusText.textContent = "Student Recognized";
    
    const nameEl = document.getElementById('student-name');
    const classEl = document.getElementById('student-class');
    const timeEl = document.getElementById('checkin-time');
    
    if (nameEl) nameEl.textContent = match.name || "Student";
    if (classEl) classEl.textContent = match.student_class || "Class Unassigned";
    if (timeEl) timeEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    scannerOverlay.style.display = 'none';
    scannerInterface.classList.add('success');
    
    successCard.classList.remove('hidden');
    // Add small delay to ensure display block hits the render tree before transition
    setTimeout(() => {
        successCard.classList.add('visible');
    }, 50);

    // After 6 seconds, reset back to scanning mode for next student
    setTimeout(() => {
        startScanning();
    }, 6000);
}

// Init Application
startWebcam();
