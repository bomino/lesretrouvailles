/**
 * Profile photo uploader.
 *
 * Flow:
 *   1. User picks a file → client-side validation (type, size) for fast feedback.
 *   2. POST the file to /api/photo/upload/ (our server).
 *   3. Django strips EXIF/GPS via Pillow, then uploads to Cloudinary and returns
 *      the public_id.
 *   4. Write that public_id into the hidden form field, update the preview.
 *   5. User clicks "Enregistrer" → Django form POSTs as normal; the backend
 *      validates that public_id is under members/<slug>/ before persisting.
 *
 * The photo deliberately transits our server: uploading straight to Cloudinary
 * (the old flow) skipped the EXIF strip, so a photo taken at home kept its GPS
 * coordinates while the FAQ told members the metadata was removed (F-03). The
 * client-side checks below are UX, not security — the server enforces both.
 *
 * No framework. The widget activates whenever an element with
 * [data-photo-uploader] is present and wires itself to the hidden
 * input[name="photo_public_id"] on the same form.
 */
(function () {
    "use strict";

    const init = () => {
        const root = document.querySelector("[data-photo-uploader]");
        if (!root) return;

        const fileInput = root.querySelector('input[type="file"]');
        const trigger = root.querySelector("[data-photo-trigger]");
        const statusEl = root.querySelector("[data-photo-status]");
        const previewEl = root.querySelector("[data-photo-preview]");
        const hidden = document.querySelector('input[name="photo_public_id"]');
        const cloudName = root.dataset.cloudName;
        const uploadEndpoint = root.dataset.uploadEndpoint || "/api/photo/upload/";
        const csrfToken = root.dataset.csrfToken || readCsrfFromCookie();
        // Optional: when present, the uploader runs in admin-on-behalf-of mode.
        // The server pins the Cloudinary folder to this member's slug — and
        // only honors it when the requester is staff.
        const memberSlug = root.dataset.memberSlug || "";

        if (!fileInput || !trigger || !hidden || !cloudName || !csrfToken) {
            console.warn("[photo-uploader] missing required element/dataset; widget disabled");
            return;
        }

        if (cloudName === "fake-cloud") {
            // FakeCloudinary client is active — real uploads will fail.
            // Show a hint instead of letting the user try.
            trigger.disabled = true;
            trigger.classList.add("opacity-60", "cursor-not-allowed");
            showStatus(
                "Le téléversement nécessite les identifiants Cloudinary réels. Configurez CLOUDINARY_* dans .env pour activer.",
                "info",
            );
            return;
        }

        trigger.addEventListener("click", (e) => {
            e.preventDefault();
            fileInput.click();
        });

        fileInput.addEventListener("change", async () => {
            const file = fileInput.files && fileInput.files[0];
            if (!file) return;

            const allowed = ["image/jpeg", "image/png", "image/webp"];
            const max = 5 * 1024 * 1024;
            if (!allowed.includes(file.type)) {
                showStatus("Format non supporté. Utilisez JPG, PNG ou WebP.", "error");
                return;
            }
            if (file.size > max) {
                const mb = (file.size / 1024 / 1024).toFixed(1);
                showStatus(`Photo trop lourde (${mb} Mo). Maximum : 5 Mo.`, "error");
                return;
            }

            trigger.disabled = true;
            showStatus("Préparation…", "info");

            try {
                showStatus("Téléversement…", "info");

                const fd = new FormData();
                fd.append("file", file);
                if (memberSlug) {
                    fd.append("member_slug", memberSlug);
                }

                const upResp = await fetch(uploadEndpoint, {
                    method: "POST",
                    headers: { "X-CSRFToken": csrfToken, "Accept": "application/json" },
                    credentials: "same-origin",
                    body: fd,
                });

                if (upResp.status === 429) {
                    showStatus("Trop de tentatives. Réessayez dans une minute.", "error");
                    return;
                }
                if (!upResp.ok) {
                    // The server speaks French; surface its message when it has one.
                    const err = await upResp.json().catch(() => ({}));
                    showStatus(
                        (err && err.error) || "Échec du téléversement. Réessayez ou choisissez une autre photo.",
                        "error",
                    );
                    return;
                }

                const result = await upResp.json();
                hidden.value = result.public_id;

                if (previewEl) {
                    // Cloudinary delivery URL for the stripped asset we just stored.
                    previewEl.src = `https://res.cloudinary.com/${cloudName}/image/upload/c_fill,g_face,h_128,w_128/${result.public_id}`;
                    // Show the preview regardless of how it was hidden — Tailwind
                    // class on member-facing pages, inline style in Django admin.
                    previewEl.classList.remove("hidden");
                    previewEl.style.display = "";
                    const fallback = root.querySelector("[data-photo-fallback]");
                    if (fallback) {
                        fallback.classList.add("hidden");
                        fallback.style.display = "none";
                    }
                }

                showStatus(
                    "Photo téléversée. Cliquez sur Enregistrer pour confirmer.",
                    "success",
                );
            } catch (err) {
                console.error(err);
                showStatus("Erreur réseau. Vérifiez votre connexion.", "error");
            } finally {
                trigger.disabled = false;
                // Reset so the same file can be re-selected after a failed
                // upload (browsers suppress 'change' on identical re-selection
                // unless the input is cleared first).
                fileInput.value = "";
            }
        });

        function showStatus(msg, kind) {
            if (!statusEl) return;
            statusEl.textContent = msg;
            statusEl.dataset.kind = kind || "info";
        }
    };

    function readCsrfFromCookie() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
