// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Exam Submission", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("Exam Submission", {
    refresh(frm) {
        // "Inspect video files" — lists the raw proctoring objects stored under
        // this submission's prefix in S3/R2 in a popup, with size, timestamp,
        // and a short-lived link to open/download each file.
        if (!frm.is_new()) {
            frm.add_custom_button(
                __("Inspect video files"),
                () => show_video_files_dialog(frm),
                __("Actions")
            );
        }

        // Load the Bootstrap Icons font best-effort so the control glyphs
        // render. This is intentionally NOT gated together with the player
        // logic: if the CDN is slow/blocked the player must still load (the
        // buttons just fall back to bare labels).
        if (!document.getElementById("exampro-bi-css")) {
            const link = document.createElement("link");
            link.id = "exampro-bi-css";
            link.rel = "stylesheet";
            link.href = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css";
            document.head.appendChild(link);
        }

        // Handle video display — reuses the framework-agnostic VideoPlayer
        // module so the desk-form player and the proctor page stay aligned.
        frappe.require("/assets/exampro/js/video_player.js", function () {
            frappe.call({
                method: "exampro.exam_pro.doctype.exam_submission.exam_submission.exam_video_list",
                args: { exam_submission: frm.doc.name },
                callback: function (r) {
                    const videosMap = (r.message && r.message.videos) || {};
                    const chunks = Object.entries(videosMap)
                        .sort((a, b) => Number(a[0]) - Number(b[0]))
                        .map(([, url]) => url);

                    if (chunks.length === 0) return;

                    const wrap = document.getElementById("esub-player-wrap");
                    if (!wrap) return;
                    wrap.classList.remove("hidden");

                    if (frm._candidateVideoPlayer) {
                        frm._candidateVideoPlayer.destroy();
                    }
                    frm._candidateVideoPlayer = new VideoPlayer({
                        videoEl: "#esub-player-video",
                        prevBtn: "#esub-player-prev",
                        nextBtn: "#esub-player-next",
                        playPauseBtn: "#esub-player-play",
                        skipBackBtn: "#esub-player-skip-back",
                        skipForwardBtn: "#esub-player-skip-fwd",
                        goLiveBtn: "#esub-player-live",
                        indexField: "#esub-player-index",
                    });
                    frm._candidateVideoPlayer.loadChunks(chunks);
                },
            });
        });

        // Replace retina_location_log field with canvas plot
        if (frm.doc.retina_location_log) {
            // Hide the original JSON field
            frm.set_df_property('retina_location_log', 'hidden', 1);
            
            // Create canvas element for plotting
            const plotHtml = `
                <div class="form-group">
                    <div class="clearfix">
                        <label class="control-label">Retina Location Plot</label>
                    </div>
                    <div class="control-input-wrapper">
                        <canvas id="plotCanvas" width="300" height="300" style="border: 1px solid #ddd; border-radius: 4px;"></canvas>
                        <div style="margin-top: 10px; display: flex; gap: 20px; font-size: 12px;">
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="width: 12px; height: 12px; border-radius: 50%; background-color: #27ae60;"></div>
                                <span>Screen Gaze</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="width: 12px; height: 12px; border-radius: 50%; background-color: #e74c3c;"></div>
                                <span>Away Gaze</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="width: 12px; height: 12px; border-radius: 50%; background-color: #f1c40f;"></div>
                                <span>Distracted Gaze</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Insert the canvas after the retina_location_log field
            $(frm.fields_dict.retina_location_log.wrapper).after(plotHtml);
            
            // Draw the plot
            setTimeout(() => {
                drawRetinaPlot(frm.doc.retina_location_log);
            }, 100);
        }
    },
});

function show_video_files_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("Video Files"),
        size: "large",
        fields: [{ fieldtype: "HTML", fieldname: "files_html" }],
    });

    const $body = $(dialog.fields_dict.files_html.$wrapper);
    $body.html(`<div class="text-muted text-center py-4">${__("Loading…")}</div>`);
    dialog.show();

    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.inspect_video_files",
        args: { exam_submission: frm.doc.name },
        callback: function (r) {
            const data = r.message || {};
            const files = data.files || [];

            if (files.length === 0) {
                $body.html(
                    `<div class="text-muted text-center py-4">${__("No video files found for this submission.")}</div>`
                );
                return;
            }

            const rows = files.map((f, i) => {
                const modified = f.last_modified
                    ? frappe.datetime.str_to_user(f.last_modified.replace("T", " ").split(".")[0])
                    : "-";
                return `
                    <tr>
                        <td class="text-muted">${i + 1}</td>
                        <td style="word-break:break-all">${frappe.utils.escape_html(f.filename)}</td>
                        <td class="text-right">${frappe.utils.escape_html(f.size_human || "-")}</td>
                        <td>${frappe.utils.escape_html(modified)}</td>
                        <td class="text-right">
                            <a href="${f.url}" target="_blank" rel="noopener" class="btn btn-xs btn-default">
                                ${__("Open")}
                            </a>
                        </td>
                    </tr>`;
            }).join("");

            $body.html(`
                <div class="mb-2 text-muted small">
                    ${__("Bucket")}: <code>${frappe.utils.escape_html(data.bucket || "")}</code>
                    &nbsp;·&nbsp; ${__("Prefix")}: <code>${frappe.utils.escape_html(data.prefix || "")}</code>
                    &nbsp;·&nbsp; ${data.count} ${__("file(s)")}
                </div>
                <div style="max-height:60vh;overflow:auto">
                    <table class="table table-bordered table-sm" style="margin-bottom:0">
                        <thead>
                            <tr>
                                <th style="width:40px">#</th>
                                <th>${__("File")}</th>
                                <th class="text-right" style="width:90px">${__("Size")}</th>
                                <th style="width:160px">${__("Last Modified")}</th>
                                <th class="text-right" style="width:80px"></th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
                <div class="mt-2 text-muted small">
                    ${__("Links expire in 15 minutes.")}
                </div>
            `);
        },
    });
}

function drawRetinaPlot(retinaData) {
    const canvas = document.getElementById('plotCanvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const plotWidth = canvas.width;
    const plotHeight = canvas.height;
    
    // Parse the JSON data
    let data = [];
    try {
        data = JSON.parse(retinaData) || [];
    } catch (e) {
        console.error('Error parsing retina location data:', e);
        return;
    }

    // Clear canvas with simple background
    ctx.fillStyle = '#f8f8f8';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw grid lines for reference (3x3 grid)
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 1;
    ctx.beginPath();
    
    // Vertical grid lines (thirds)
    for (let i = 1; i < 3; i++) {
        const x = (plotWidth / 3) * i;
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
    }
    
    // Horizontal grid lines (thirds)
    for (let i = 1; i < 3; i++) {
        const y = (plotHeight / 3) * i;
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
    }
    ctx.stroke();

    // Plot retina tracking points
    data.forEach((point, index) => {
        const canvasX = point.x * plotWidth;
        const canvasY = point.y * plotHeight;
        
        // Set color based on gaze direction - bright colors for visibility
        let color;
        switch(point.gazeDirection) {
            case 'screen':
                color = '#27ae60'; // Green for screen gaze
                break;
            case 'away':
                color = '#e74c3c'; // Red for away gaze
                break;
            case 'distracted':
                color = '#f1c40f'; // Yellow for distracted gaze
                break;
            default:
                color = '#95a5a6'; // Gray for unknown/undefined
        }
        ctx.fillStyle = color;
        
        // Draw bigger point for visibility
        ctx.beginPath();
        ctx.arc(canvasX, canvasY, 12, 0, 2 * Math.PI);
        ctx.fill();
        
        // Add point number with better contrast
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 14px Arial';
        ctx.textAlign = 'center';
        ctx.fillText((index + 1).toString(), canvasX, canvasY + 5);
    });
}
