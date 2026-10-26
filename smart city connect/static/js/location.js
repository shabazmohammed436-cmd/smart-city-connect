document.addEventListener("DOMContentLoaded", function () {
    const button = document.getElementById("use-location");
    const status = document.getElementById("location-status");
    const latInput = document.getElementById("latitude");
    const lngInput = document.getElementById("longitude");
    const sourceInput = document.getElementById("location_source");
    const addressInput = document.getElementById("address");
    const mapBox = document.getElementById("mini-map");
    let map = null;
    let marker = null;

    if (!button) return;

    function showMap(lat, lng) {
        if (!window.L || !mapBox) return;
        mapBox.classList.remove("hidden");
        if (!map) {
            map = L.map(mapBox).setView([lat, lng], 16);
            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                attribution: "&copy; OpenStreetMap contributors"
            }).addTo(map);
        } else {
            map.setView([lat, lng], 16);
        }
        if (marker) {
            marker.setLatLng([lat, lng]);
        } else {
            marker = L.marker([lat, lng]).addTo(map);
        }
        setTimeout(function () { map.invalidateSize(); }, 200);
    }

    async function lookupAddress(lat, lng) {
        if (!window.SCC || !window.SCC.nominatimEnabled) return;
        try {
            const res = await fetch(window.SCC.reverseUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": window.SCC.csrfToken
                },
                body: JSON.stringify({ lat: lat, lng: lng })
            });
            const data = await res.json();
            if (data.ok && data.address && !addressInput.value) {
                addressInput.value = data.address;
            } else if (!data.ok) {
                status.textContent += " Address lookup: " + data.reason;
            }
        } catch (err) {
            status.textContent += " Address lookup is unavailable.";
        }
    }

    button.addEventListener("click", function () {
        if (!navigator.geolocation) {
            status.textContent = "This browser cannot read GPS. Enter the address manually. Coordinates will stay blank.";
            sourceInput.value = "unavailable";
            return;
        }
        status.textContent = "Requesting location permission...";
        navigator.geolocation.getCurrentPosition(
            function (pos) {
                const lat = pos.coords.latitude.toFixed(6);
                const lng = pos.coords.longitude.toFixed(6);
                latInput.value = lat;
                lngInput.value = lng;
                sourceInput.value = "browser";
                status.textContent = "Location captured: " + lat + ", " + lng + ". You can still correct the address.";
                showMap(Number(lat), Number(lng));
                lookupAddress(lat, lng);
            },
            function () {
                sourceInput.value = "unavailable";
                latInput.value = "";
                lngInput.value = "";
                status.textContent = "Location permission was denied or GPS failed. Enter the address yourself. No coordinates will be stored.";
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    });
});
