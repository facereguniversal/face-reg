const API_BASE = "http://localhost:8000/api";
const urlParams = new URLSearchParams(window.location.search);
const USER_ID = urlParams.get('userId') || "00000000-0000-0000-0000-000000000000"; 
const TOKEN = urlParams.get('token') || "";

function getHeaders() {
    const headers = {};
    if (TOKEN) {
        headers['Authorization'] = `Bearer ${TOKEN}`;
    }
    return headers;
}

const video = document.getElementById('webcam');
const guide = document.getElementById('face-guide');
const feedbackPanel = document.getElementById('feedback-panel');
const feedbackText = document.getElementById('feedback-text');
const captureBtn = document.getElementById('capture-btn');
const submitBtn = document.getElementById('submit-btn');
const gallery = document.getElementById('gallery');
const frameCountEl = document.getElementById('frame-count');

let stream = null;
let capturedFrames = [];
const MAX_FRAMES = 6;
const MIN_FRAMES = 4;

let isProcessing = false;

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
        
        // Setup validation loop
        video.addEventListener('loadedmetadata', () => {
            captureBtn.disabled = false;
            validateLoop();
        });
    } catch (err) {
        setFeedback("Error accessing webcam: " + err.message, "error");
    }
}

// Continuous Validation
async function validateLoop() {
    if (stream && !isProcessing) {
        await validateCurrentFrame();
    }
    setTimeout(validateLoop, 2000); // Check every 2 seconds
}

// Extract frame as Blob
function getFrameBlob() {
    return new Promise((resolve) => {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);
        canvas.toBlob(resolve, 'image/jpeg', 0.9);
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

        if (!response.ok) throw new Error("Validation API error");
        
        const result = await response.json();
        
        if (result.passed) {
            setFeedback(`Good quality (Score: ${Math.round(result.quality_score || 0)})`, "success");
        } else {
            setFeedback("Issues: " + result.issues.join(", "), "error");
        }
    } catch (e) {
        console.error(e);
        // Silently fail validation loop to not interrupt UX
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
            if (result.passed) {
                addFrameToGallery(blob);
            } else {
                alert("Captured frame failed quality check: " + result.issues.join(", "));
            }
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

// Final Submission
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
            const err = await response.json();
            alert("Enrollment failed: " + (err.detail || "Unknown error"));
        }
    } catch (e) {
        alert("Network error during enrollment");
        console.error(e);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Complete Enrollment";
    }
});

// Init
startWebcam();