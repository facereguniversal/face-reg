import {
    FaceDetector,
    FilesetResolver,
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";

const API_BASE = `${window.location.origin}/api`;
const params = new URLSearchParams(window.location.search);
const DEVICE_ID = params.get("deviceId") || "demo-kiosk";
const DEVICE_TOKEN = params.get("deviceToken") || "demo-token";

const shell = document.querySelector(".kiosk-shell");
const video = document.getElementById("webcam");
const overlay = document.getElementById("overlay");
const statusText = document.getElementById("status-text");
const resultPanel = document.getElementById("result-panel");
const resultTitle = document.getElementById("result-title");
const guestName = document.getElementById("guest-name");
const guestRole = document.getElementById("guest-role");
const spinner = document.getElementById("spinner");

let detector = null;
let stream = null;
let state = "idle";
let stableFrames = 0;
let lastBox = null;
let fallbackTimer = null;

const MODEL_URL =
    "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite";

function setState(nextState, message) {
    state = nextState;
    shell.dataset.state = nextState;
    statusText.textContent = message;
    spinner.hidden = nextState !== "processing";
}

async function start() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 960 },
                height: { ideal: 720 },
                facingMode: "user",
            },
            audio: false,
        });
        video.srcObject = stream;
        await video.play();
        resizeOverlay();
        window.addEventListener("resize", resizeOverlay);
        await loadDetector();
        setState("idle", "Please step forward");
        requestAnimationFrame(detectionLoop);
    } catch (error) {
        console.error(error);
        setState("error", "Camera unavailable. Please visit reception.");
    }
}

async function loadDetector() {
    try {
        const vision = await FilesetResolver.forVisionTasks(
            "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
        );
        detector = await FaceDetector.createFromOptions(vision, {
            baseOptions: { modelAssetPath: MODEL_URL },
            runningMode: "VIDEO",
        });
    } catch (error) {
        console.warn("MediaPipe detector unavailable; using timed fallback.", error);
        fallbackTimer = window.setInterval(() => {
            if (state === "idle") {
                submitCurrentFrame();
            }
        }, 3000);
    }
}

function resizeOverlay() {
    overlay.width = video.clientWidth;
    overlay.height = video.clientHeight;
}

function detectionLoop() {
    if (
        detector &&
        video.readyState >= 2 &&
        (state === "idle" || state === "stabilizing")
    ) {
        const result = detector.detectForVideo(video, performance.now());
        handleDetections(result.detections || []);
    }
    requestAnimationFrame(detectionLoop);
}

function handleDetections(detections) {
    const ctx = overlay.getContext("2d");
    ctx.clearRect(0, 0, overlay.width, overlay.height);

    if (!detections.length) {
        stableFrames = 0;
        lastBox = null;
        if (state !== "idle") setState("idle", "Please step forward");
        return;
    }

    const box = detections[0].boundingBox;
    const scaleX = overlay.width / video.videoWidth;
    const scaleY = overlay.height / video.videoHeight;
    const viewBox = {
        x: box.originX * scaleX,
        y: box.originY * scaleY,
        width: box.width * scaleX,
        height: box.height * scaleY,
    };
    drawBox(ctx, viewBox);

    const centered = isCentered(viewBox);
    const stable = isStable(viewBox);
    stableFrames = centered && stable ? stableFrames + 1 : 0;
    lastBox = viewBox;

    if (!centered) {
        setState("stabilizing", "Center your face");
        return;
    }
    if (stableFrames < 8) {
        setState("stabilizing", "Hold still");
        return;
    }
    submitCurrentFrame();
}

function drawBox(ctx, box) {
    ctx.strokeStyle = state === "stabilizing" ? "#f5b84b" : "#42d392";
    ctx.lineWidth = 4;
    ctx.strokeRect(box.x, box.y, box.width, box.height);
}

function isCentered(box) {
    const centerX = box.x + box.width / 2;
    const centerY = box.y + box.height / 2;
    const minSize = Math.min(overlay.width, overlay.height) * 0.22;
    return (
        Math.abs(centerX - overlay.width / 2) < overlay.width * 0.18 &&
        Math.abs(centerY - overlay.height / 2) < overlay.height * 0.20 &&
        box.width >= minSize
    );
}

function isStable(box) {
    if (!lastBox) return true;
    const movement =
        Math.abs(box.x - lastBox.x) +
        Math.abs(box.y - lastBox.y) +
        Math.abs(box.width - lastBox.width) +
        Math.abs(box.height - lastBox.height);
    return movement < overlay.width * 0.08;
}

async function frameBlob() {
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
}

async function submitCurrentFrame() {
    if (state === "processing" || state === "cooldown") return;
    setState("processing", "Checking you in");

    try {
        const blob = await frameBlob();
        const form = new FormData();
        form.append("image", blob, `checkin_${Date.now()}.jpg`);

        const response = await fetch(`${API_BASE}/checkin`, {
            method: "POST",
            headers: {
                "X-Device-Id": DEVICE_ID,
                "X-Device-Token": DEVICE_TOKEN,
            },
            body: form,
        });
        const payload = await response.json();
        handleCheckinResponse(response.status, payload);
    } catch (error) {
        console.error(error);
        showError("Network issue. Please visit reception.");
    }
}

function handleCheckinResponse(httpStatus, payload) {
    if (httpStatus === 200 && payload.status === "SUCCESS") {
        showSuccess(payload.user, payload.message || "Welcome.");
        return;
    }
    if (httpStatus === 200 && payload.status === "ALREADY_CHECKED_IN") {
        showSuccess(payload.user, "Already checked in.");
        return;
    }
    if (httpStatus === 403 || payload.status === "SPOOF_DETECTED") {
        showError("Unable to verify liveness. Please visit reception.");
        return;
    }
    showError("Face not recognized. Please visit reception.");
}

function showSuccess(user, message) {
    playChime();
    resultPanel.hidden = false;
    resultTitle.textContent = message;
    guestName.textContent = user?.name || "Guest";
    guestRole.textContent = user?.role || "";
    setState("success", `Welcome, ${user?.name || "Guest"}`);
    beginCooldown();
}

function showError(message) {
    resultPanel.hidden = true;
    guestName.textContent = "";
    guestRole.textContent = "";
    setState("error", message);
    beginCooldown();
}

function beginCooldown() {
    stableFrames = 0;
    lastBox = null;
    setTimeout(() => {
        resultPanel.hidden = true;
        setState("cooldown", "Resetting");
        setTimeout(() => setState("idle", "Please step forward"), 500);
    }, 3000);
}

function playChime() {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const now = ctx.currentTime;
    [523.25, 659.25, 783.99].forEach((freq, index) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = freq;
        osc.type = "sine";
        gain.gain.setValueAtTime(0.0001, now + index * 0.08);
        gain.gain.exponentialRampToValueAtTime(0.14, now + index * 0.08 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + index * 0.08 + 0.22);
        osc.connect(gain).connect(ctx.destination);
        osc.start(now + index * 0.08);
        osc.stop(now + index * 0.08 + 0.24);
    });
}

window.addEventListener("beforeunload", () => {
    if (fallbackTimer) window.clearInterval(fallbackTimer);
    if (stream) stream.getTracks().forEach((track) => track.stop());
});

start();
