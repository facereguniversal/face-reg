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
    statusText.textContent = "Looking for Guest...";
    
    scanInterval = setInterval(scanFrame, 2000); // Check every 2 seconds
}

async function scanFrame() {
    if (isIdentified) return;
    
    try {
        const blob = await getFrameBlob();
        const formData = new FormData();
        formData.append("image", blob, `scan_${Date.now()}.jpg`);

        const response = await fetch(`${API_BASE}/identify`, {
            method: 'POST',
            body: formData,
            headers: getHeaders()
        });

        if (response.ok) {
            const result = await response.json();
            if (result.matches && result.matches.length > 0) {
                // Determine if confident enough (0.4 cosine sim is often acceptable for ArcFace but config dependent)
                const match = result.matches[0];
                if (match.score > 0.4) {
                    handleSuccess(match.user_id);
                }
            }
        } else {
            console.warn("Identify endpoint returned:", response.status);
        }
    } catch (e) {
        console.error("Scanning request failed. Backend offline?", e);
    }
}

function handleSuccess(userId) {
    isIdentified = true;
    clearInterval(scanInterval);
    
    statusText.textContent = "Identity Confirmed";
    // For privacy in actual kiosk, we might mask UUID, but we display it here to prove MVP works
    guestIdSpan.textContent = userId;
    
    scannerOverlay.style.display = 'none';
    scannerInterface.classList.add('success');
    
    successCard.classList.remove('hidden');
    // Add small delay to ensure display block hits the render tree before transition
    setTimeout(() => {
        successCard.classList.add('visible');
    }, 50);

    // After 6 seconds, reset back to scanning mode for next guest
    setTimeout(() => {
        startScanning();
    }, 6000);
}

// Init Application
startWebcam();
