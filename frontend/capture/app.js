const API_BASE = "/api";
const MIN_FRAMES = 4;
const MAX_FRAMES = 6;
const USER_ID = "00000000-0000-0000-0000-000000000000";

// Handle optional token parameter from URL
const urlParams = new URLSearchParams(window.location.search);
const TOKEN = urlParams.get('token') || '';

function getHeaders() {
    const headers = {};
    if (TOKEN) {
        headers['Authorization'] = `Bearer ${TOKEN}`;
    }
    return headers;
}

const video = document.getElementById('webcam');
const canvas = document.getElementById('canvas');
const feedbackText = document.getElementById('feedbackText');
const feedbackPanel = document.getElementById('feedbackPanel');
const guide = document.getElementById('guide');
const captureBtn = document.getElementById('captureBtn');
const submitBtn = document.getElementById('submitBtn');
const gallery = document.getElementById('gallery');
const frameCountEl = document.getElementById('frameCount');

let capturedFrames = []; // Array of Blobs
let isProcessing = false;

// Initialize Webcam
async function setupWebcam() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" }
        });
        video.srcObject = stream;
        video.onloadedmetadata = () => {
            video.play();
            startValidationLoop();
        };
    } catch (err) {
        setFeedback("Camera access denied or unavailable", "error");
        console.error(err);
    }
}

// Continuous Quality Validation (Debounced)
function startValidationLoop() {
    setInterval(() => {
        if (!isProcessing && capturedFrames.length < MAX_FRAMES) {
            validateCurrentFrame();
        }
    }, 1500);
}

// Capture current frame from webcam as lightweight 480px JPEG
function getFrameBlob() {
    return new Promise(resolve => {
        const targetWidth = 480;
        const aspectRatio = video.videoWidth ? (video.videoHeight / video.videoWidth) : 0.75;
        canvas.width = targetWidth;
        canvas.height = Math.round(targetWidth * aspectRatio);
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(resolve, 'image/jpeg', 0.75);
    });
}

// Validate single frame with API
async function validateCurrentFrame() {
    isProcessing = true;
    try {
        const blob = await getFrameBlob();
        const formData = new FormData();
        formData.append("image", blob, "validate.jpg");

        const response = await fetch(`${API_BASE}/faces/validate`, {
            method: 'POST',
            body: formData,
            headers: getHeaders(),
        });

        if (!response.ok) throw new Error(`Validation API error (${response.status})`);
        
        const result = await response.json();
        
        if (result && result.passed) {
            setFeedback(`Good quality (Score: ${Math.round(result.quality_score || 0)})`, "success");
        } else {
            const issuesText = (result && Array.isArray(result.issues)) ? result.issues.join(", ") : ((result && result.detail) ? result.detail : "Validation error");
            setFeedback("Issues: " + issuesText, "error");
        }
    } catch (e) {
        console.error(e);
        setFeedback("Backend service connecting... (" + e.message + ")", "error");
    } finally {
        isProcessing = false;
    }
}

// UI Feedback
function setFeedback(msg, type) {
    feedbackText.textContent = msg;
    feedbackPanel.className = type;
    guide.className = type === "success" ? "good" : (type === "error" ? "bad" : "");
}

// Capture button click
captureBtn.addEventListener('click', async () => {
    if (capturedFrames.length >= MAX_FRAMES) return;

    captureBtn.disabled = true;
    captureBtn.textContent = "Processing...";

    const blob = await getFrameBlob();
    
    // Quick validation before adding to gallery
    const formData = new FormData();
    formData.append("image", blob, `frame_${Date.now()}.jpg`);

    try {
        const response = await fetch(`${API_BASE}/faces/validate`, {
            method: 'POST',
            body: formData,
            headers: getHeaders()
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result && result.passed) {
                addFrameToGallery(blob);
            } else {
                const issuesText = (result && Array.isArray(result.issues)) ? result.issues.join(", ") : ((result && result.detail) ? result.detail : "Quality check failed");
                alert("Captured frame failed quality check: " + issuesText);
            }
        } else {
            addFrameToGallery(blob);
        }
    } catch (e) {
        console.error("Capture validation failed", e);
        // Fallback: still add if API is unreachable for validation
        addFrameToGallery(blob); 
    }

    captureBtn.textContent = "Capture Frame";
    captureBtn.disabled = capturedFrames.length >= MAX_FRAMES;
});

// Gallery Management
function addFrameToGallery(blob) {
    capturedFrames.push(blob);
    renderGallery();
}

function removeFrame(index) {
    capturedFrames.splice(index, 1);
    renderGallery();
    captureBtn.disabled = false;
}

function renderGallery() {
    gallery.innerHTML = '';
    frameCountEl.textContent = capturedFrames.length;

    capturedFrames.forEach((blob, idx) => {
        const item = document.createElement('div');
        item.className = 'gallery-item';
        
        const img = document.createElement('img');
        img.src = URL.createObjectURL(blob);
        
        const btn = document.createElement('button');
        btn.className = 'remove-btn';
        btn.innerHTML = '×';
        btn.onclick = () => removeFrame(idx);
        
        item.appendChild(img);
        item.appendChild(btn);
        gallery.appendChild(item);
    });

    submitBtn.disabled = capturedFrames.length < MIN_FRAMES;
}

// Complete Enrollment
submitBtn.addEventListener('click', async () => {
    if (capturedFrames.length < MIN_FRAMES) return;

    submitBtn.disabled = true;
    submitBtn.textContent = "Enrolling...";

    const formData = new FormData();
    capturedFrames.forEach((blob, idx) => {
        formData.append("images", blob, `enroll_${idx}.jpg`);
    });

    try {
        const response = await fetch(`${API_BASE}/users/${USER_ID}/faces`, {
            method: 'POST',
            body: formData,
            headers: getHeaders()
        });

        if (response.ok) {
            const data = await response.json();
            alert(`Success! Enrolled templates: ${data.template_ids.length}`);
            window.location.reload();
        } else {
            const text = await response.text();
            let errMsg = "Unknown error";
            try {
                const err = JSON.parse(text);
                errMsg = err.detail || text;
            } catch (_) {
                errMsg = text || response.statusText;
            }
            alert("Enrollment failed: " + errMsg);
        }
    } catch (e) {
        alert("Enrollment error: " + e.message);
        console.error(e);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Complete Enrollment";
    }
});

// Start app
setupWebcam();
