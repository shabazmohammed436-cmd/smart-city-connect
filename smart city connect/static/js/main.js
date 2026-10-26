document.addEventListener("DOMContentLoaded", function () {
    const toggle = document.querySelector(".nav-toggle");
    const nav = document.querySelector(".site-nav");
    if (toggle && nav) {
        toggle.addEventListener("click", function () {
            const open = nav.classList.toggle("open");
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        });
    }

    const badge = document.getElementById("unread-badge");
    if (badge) {
        setInterval(async function () {
            try {
                const res = await fetch("/api/notifications/unread");
                if (!res.ok) return;
                const data = await res.json();
                badge.textContent = data.count;
                badge.classList.toggle("hidden", !data.count);
            } catch (err) {
                /* Keep the last known count if the network is busy. */
            }
        }, 12000);
    }

    const form = document.getElementById("complaint-form");
    if (!form) return;

    const panels = Array.from(form.querySelectorAll(".step-panel"));
    const stepLabels = Array.from(document.querySelectorAll("#wizard-steps li"));
    const nextBtn = document.getElementById("next-step");
    const prevBtn = document.getElementById("prev-step");
    const submitBtn = document.getElementById("submit-btn");
    const submitStatus = document.getElementById("submit-status");
    let step = 0;

    function showStep() {
        panels.forEach(function (panel, index) {
            panel.classList.toggle("hidden", index !== step);
        });
        stepLabels.forEach(function (label, index) {
            label.classList.toggle("active", index === step);
        });
        prevBtn.hidden = step === 0;
        nextBtn.hidden = step === panels.length - 1;
        if (step === panels.length - 1) fillReview();
    }

    function fillReview() {
        const box = document.getElementById("review-box");
        const photo = document.getElementById("photo");
        box.innerHTML =
            "<div><strong>Title</strong><p>" + escapeHtml(form.title.value) + "</p></div>" +
            "<div><strong>Description</strong><p>" + escapeHtml(form.description.value) + "</p></div>" +
            "<div><strong>Address</strong><p>" + escapeHtml(form.address.value) + "</p></div>" +
            "<div><strong>Coordinates</strong><p>" +
            (form.latitude.value && form.longitude.value
                ? form.latitude.value + ", " + form.longitude.value
                : "Not recorded") +
            "</p></div>" +
            "<div><strong>Photograph</strong><p>" +
            (photo.files[0] ? photo.files[0].name : "Missing") +
            "</p></div>";
    }

    function escapeHtml(value) {
        return (value || "").replace(/[&<>"']/g, function (ch) {
            return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch];
        });
    }

    nextBtn.addEventListener("click", function () {
        if (step === 0 && !document.getElementById("photo").files.length) {
            alert("Please capture or upload a photograph first.");
            return;
        }
        if (step === 1 && form.address.value.trim().length < 4) {
            alert("Please enter an address or nearby landmark.");
            return;
        }
        if (step === 2 && (form.title.value.trim().length < 4 || form.description.value.trim().length < 10)) {
            alert("Please add a title and a more detailed description.");
            return;
        }
        step += 1;
        showStep();
    });
    prevBtn.addEventListener("click", function () {
        step -= 1;
        showStep();
    });

    form.addEventListener("submit", function () {
        submitBtn.disabled = true;
        submitStatus.classList.remove("hidden");
    });

    showStep();
});
