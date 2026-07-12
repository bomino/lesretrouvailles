/**
 * Profile photo uploader.
 *
 * Flow:
 *   1. User picks a file → client-side validation (type, size).
 *   2. POST /api/cloudinary/sign/ → get signature (server-pinned folder).
 *   3. POST file directly to Cloudinary's upload endpoint with that signature.
 *   4. On success, write Cloudinary's public_id into the hidden form field
 *      and update the on-screen preview.
 *   5. User clicks "Enregistrer" → Django form POSTs as normal; the backend
 *      validates that public_id is under members/<slug>/ before persisting.
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
        const signEndpoint = root.dataset.signEndpoint || "/api/cloudinary/sign/";
        const csrfToken = root.dataset.csrfToken || readCsrfFromCookie();
        // Optional: when present, the uploader runs in admin-on-behalf-of mode.
        // The sign endpoint pins the Cloudinary folder to this member's slug
        // (only honored if the requester is staff).
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
                const signBody = new FormData();
                if (memberSlug) {
                    signBody.append("member_slug", memberSlug);
                }
                const signResp = await fetch(signEndpoint, {
                    method: "POST",
                    headers: { "X-CSRFToken": csrfToken, "Accept": "application/json" },
                    credentials: "same-origin",
                    body: signBody,
                });

                if (signResp.status === 429) {
                    showStatus("Trop de tentatives. Réessayez dans une minute.", "error");
                    return;
                }
                if (!signResp.ok) {
                    showStatus("Impossible d'obtenir l'autorisation. Réessayez.", "error");
                    return;
                }

                const sig = await signResp.json();

                showStatus("Téléversement…", "info");

                const fd = new FormData();
                fd.append("file", file);
                fd.append("api_key", sig.api_key);
                fd.append("timestamp", String(sig.timestamp));
                fd.append("signature", sig.signature);
                fd.append("folder", sig.folder);

                const upResp = await fetch(
                    `https://api.cloudinary.com/v1_1/${cloudName}/image/upload`,
                    { method: "POST", body: fd },
                );

                if (!upResp.ok) {
                    const err = await upResp.json().catch(() => ({}));
                    // Cloudinary's error text is English ("File size too large.
                    // Got 11534336…"); every other branch of this script speaks
                    // French. Log it for debugging, show French to the member.
                    console.error("Cloudinary upload failed:", err && err.error && err.error.message);
                    showStatus("Échec du téléversement. Réessayez ou choisissez une autre photo.", "error");
                    return;
                }

                const result = await upResp.json();
                hidden.value = result.public_id;

                if (previewEl) {
                    previewEl.src = result.secure_url;
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
