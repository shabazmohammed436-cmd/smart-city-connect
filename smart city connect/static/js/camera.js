document.addEventListener("DOMContentLoaded", function () {
    const startBtn = document.getElementById("start-camera");
    const captureBtn = document.getElementById("capture-photo");
    const retakeBtn = document.getElementById("retake-photo");
    const video = document.getElementById("camera-preview");
    const canvas = document.getElementById("camera-canvas");
    const preview = document.getElementById("photo-preview");
    const status = document.getElementById("camera-status");
    const fileInput = document.getElementById("photo");
    const captureTime = document.getElementById("capture_time");
    let stream = null;

    if (!startBtn) return;

    function stopStream() {
        if (stream) {
            stream.getTracks().forEach(function (track) { track.stop(); });
            stream = null;
        }
    }

    startBtn.addEventListener("click", async function () {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            status.textContent = "This browser cannot open the camera. Please upload a photograph instead.";
            return;
        }
        status.textContent = "Requesting camera permission...";
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
            video.srcObject = stream;
            video.hidden = false;
            preview.hidden = true;
            captureBtn.disabled = false;
            retakeBtn.disabled = true;
            status.textContent = "Camera is on. Frame the problem, then capture.";
        } catch (err) {
            status.textContent = "Camera permission was denied or the camera is unavailable. You can still upload a file.";
        }
    });

    captureBtn.addEventListener("click", function () {
        if (!stream) return;
        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
            if (!blob) {
                status.textContent = "Could not capture that frame. Try uploading a file.";
                return;
            }
            const file = new File([blob], "camera-capture.jpg", { type: "image/jpeg" });
            const transfer = new DataTransfer();
            transfer.items.add(file);
            fileInput.files = transfer.files;
            preview.src = URL.createObjectURL(blob);
            preview.hidden = false;
            video.hidden = true;
            captureTime.value = new Date().toISOString();
            retakeBtn.disabled = false;
            captureBtn.disabled = true;
            status.textContent = "Photograph captured. Capture time was recorded from this device.";
            stopStream();
        }, "image/jpeg", 0.9);
    });

    retakeBtn.addEventListener("click", function () {
        preview.hidden = true;
        captureTime.value = "";
        fileInput.value = "";
        startBtn.click();
    });

    fileInput.addEventListener("change", function () {
        if (!fileInput.files[0]) return;
        stopStream();
        preview.src = URL.createObjectURL(fileInput.files[0]);
        preview.hidden = false;
        video.hidden = true;
        captureTime.value = "";
        status.textContent = "File selected. Capture time is unknown for uploads, so only upload time will be stored.";
        retakeBtn.disabled = false;
    });

    window.addEventListener("beforeunload", stopStream);
});
