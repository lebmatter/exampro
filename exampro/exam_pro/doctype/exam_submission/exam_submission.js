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

        // Load Feather Icons for control glyphs
        if (typeof feather === 'undefined' && !document.getElementById("exampro-feather-js")) {
            const script = document.createElement("script");
            script.id = "exampro-feather-js";
            script.src = "https://cdn.jsdelivr.net/npm/feather-icons/dist/feather.min.js";
            script.onload = () => feather.replace();
            document.head.appendChild(script);
        } else if (typeof feather !== 'undefined') {
            feather.replace();
        }

        // Handle video display — reuses the framework-agnostic VideoPlayer
        // module so the desk-form player and the proctor page stay aligned.
        frappe.require("/assets/exampro/js/video_player.js", function () {
            frappe.call({
                method: "exampro.exam_pro.doctype.exam_submission.exam_submission.exam_video_list",
                args: { exam_submission: frm.doc.name },
                callback: function (r) {
                    const videosMap = (r.message && r.message.videos) || {};
                    // Chunk keys are `{ms-epoch}-{rand}` (random suffix prevents
                    // replay-overwrite), so parse only the leading digits.
                    const parseTs = (k) => {
                        const m = String(k).match(/^(\d+)/);
                        return m ? Number(m[1]) : NaN;
                    };
                    const entries = Object.entries(videosMap)
                        .sort((a, b) => parseTs(a[0]) - parseTs(b[0]));
                    const chunks = entries.map(([, url]) => url);
                    const chunkStarts = entries.map(([ts]) => parseTs(ts));

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

                    buildProctorSeekBar(frm, chunkStarts);
                },
            });
        });

        // Replace retina_location_log field with a proctoring state timeline:
        // x = exam start → end, y = discrete state (screen / distracted / away /
        // noface) plotted as a coloured step line.
        if (frm.doc.retina_location_log && frm.fields_dict.retina_location_log) {
            const $fieldWrap = $(frm.fields_dict.retina_location_log.wrapper);

            // The field lives in a half-width `.form-column`; anchor the timeline
            // to the surrounding `.section-body` so it can span the full section
            // width instead of being clipped to one column.
            const $section = $fieldWrap.closest('.section-body, .form-section');

            // Avoid duplicate canvases when refresh fires more than once.
            $section.find('.proctor-timeline-group').remove();

            // Do NOT set the field's `hidden` df property: this field is now the
            // only one in its section, and hiding it would make Frappe treat the
            // section as empty and collapse it (hiding our canvas too). Instead
            // visually hide just the raw JSON editor; the section stays alive.
            $fieldWrap.find('.control-input-wrapper').hide();
            $fieldWrap.find('.control-label').hide();

            const plotHtml = `
                <div class="form-group proctor-timeline-group" style="width: 100%; padding: 0 15px;">
                    <div class="control-input-wrapper">
                        <canvas id="proctorTimeline" width="1100" height="420" style="border: 1px solid #ddd; border-radius: 4px; max-width: 100%; display: block;"></canvas>
                        <div style="margin-top: 10px; display: flex; flex-wrap: wrap; gap: 20px; font-size: 12px;">
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="width: 12px; height: 12px; border-radius: 2px; background-color: #27ae60;"></div>
                                <span>Screen Gaze</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="width: 12px; height: 12px; border-radius: 2px; background-color: #f1c40f;"></div>
                                <span>Distracted Gaze</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="width: 12px; height: 12px; border-radius: 2px; background-color: #e74c3c;"></div>
                                <span>Away Gaze</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 5px;">
                                <div style="width: 12px; height: 12px; border-radius: 2px; background-color: #000000;"></div>
                                <span>No Face</span>
                            </div>
                        </div>
                        <div id="proctorTimelineCaption" class="text-muted" style="margin-top: 6px; font-size: 11px;"></div>
                        <div style="margin-top: 20px; display: flex; align-items: center; gap: 30px; flex-wrap: wrap;">
                            <canvas id="proctorPie" width="240" height="240" style="flex: 0 0 auto;"></canvas>
                            <div id="proctorPieBreakdown" style="font-size: 13px; line-height: 1.8; flex: 1 1 auto; min-width: 220px;"></div>
                        </div>
                    </div>
                </div>
            `;

            // Append to the section body so the canvas can span the full section
            // width, not just the half-width form-column the field sits in.
            const $target = $section.length ? $section : $fieldWrap.parent();
            $target.append(plotHtml);

            // Size off the timeline group's own clientWidth (full section width),
            // falling back to form-layout if it's not measurable yet. Redraw on
            // tab activation and window resize so it fills the full width.
            const sizeAndDraw = () => {
                const canvas = document.getElementById('proctorTimeline');
                if (!canvas) return;
                const group = canvas.closest('.proctor-timeline-group');
                const layoutEl = frm.$wrapper.find('.form-layout').get(0);
                const w = (group && group.clientWidth)
                    ? group.clientWidth
                    : (layoutEl && layoutEl.clientWidth ? layoutEl.clientWidth : 1100);
                canvas.width = Math.max(600, w - 30);
                canvas.height = 420;
                drawProctorTimeline(frm);
            };

            setTimeout(sizeAndDraw, 150);

            // Redraw when the Proctor tab is shown (canvas may have been sized
            // while hidden) and on resize. Namespaced so we don't stack handlers.
            frm.$wrapper.off('shown.bs.tab.proctortl').on('shown.bs.tab.proctortl', () => {
                setTimeout(sizeAndDraw, 50);
            });
            $(window).off('resize.proctortl').on('resize.proctortl', () => {
                clearTimeout(frm._proctorTlResize);
                frm._proctorTlResize = setTimeout(sizeAndDraw, 200);
            });
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

// Render the proctoring state as a time-series step graph: x = exam start → end,
// y = discrete state lanes (screen / distracted / away / noface). The line is
// coloured per the current state; "noface" is black.
function drawProctorTimeline(frm) {
    const canvas = document.getElementById('proctorTimeline');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;

    // Parse + normalize samples into {t, state}, sorted by time.
    let raw = [];
    try {
        raw = JSON.parse(frm.doc.retina_location_log) || [];
    } catch (e) {
        console.error('Error parsing retina location data:', e);
        return;
    }

    const points = [];
    raw.forEach((p) => {
        if (!p || !p.timestamp) return;
        let state = p.state;
        if (!state) {
            // Back-compat with older records that only stored gazeDirection.
            if (p.gazeDirection === 'screen') state = 'screen';
            else if (p.gazeDirection === 'away') state = 'away';
            else state = 'screen';
        }
        points.push({ t: Number(p.timestamp), state: state });
    });
    points.sort((a, b) => a.t - b.t);

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, W, H);

    if (points.length === 0) {
        ctx.fillStyle = '#999';
        ctx.font = '13px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('No time-series proctoring data recorded.', W / 2, H / 2);
        return;
    }

    // Lanes top → bottom (best to worst).
    const lanes = [
        { key: 'screen',     label: 'Screen Gaze',     color: '#27ae60' },
        { key: 'distracted', label: 'Distracted Gaze', color: '#f1c40f' },
        { key: 'away',       label: 'Away Gaze',       color: '#e74c3c' },
        { key: 'noface',     label: 'No Face',         color: '#000000' },
    ];
    const laneIndex = {};
    lanes.forEach((l, i) => { laneIndex[l.key] = i; });

    const padLeft = 110, padRight = 20, padTop = 16, padBottom = 34;
    const plotW = W - padLeft - padRight;
    const plotH = H - padTop - padBottom;
    const laneH = plotH / lanes.length;

    const t0 = points[0].t;
    const t1 = points.length > 1 ? points[points.length - 1].t : t0 + 1;
    const span = Math.max(1, t1 - t0);
    const X = (t) => padLeft + ((t - t0) / span) * plotW;
    const laneCenterY = (i) => padTop + i * laneH + laneH / 2;

    // Lane backgrounds + labels.
    lanes.forEach((l, i) => {
        const yTop = padTop + i * laneH;
        ctx.fillStyle = (i % 2 === 0) ? '#fafafa' : '#f2f2f2';
        ctx.fillRect(padLeft, yTop, plotW, laneH);
        ctx.fillStyle = '#333';
        ctx.font = '12px Arial';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(l.label, padLeft - 10, yTop + laneH / 2);
        // Colour swatch beside the label.
        ctx.fillStyle = l.color;
        ctx.fillRect(padLeft - 6, yTop + laneH / 2 - 1, 4, 2);
    });

    // Vertical time gridlines + x-axis labels (clock time of the samples).
    const ticks = 6;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (let k = 0; k <= ticks; k++) {
        const tt = t0 + (span * k) / ticks;
        const x = X(tt);
        ctx.strokeStyle = '#eee';
        ctx.beginPath();
        ctx.moveTo(x, padTop);
        ctx.lineTo(x, padTop + plotH);
        ctx.stroke();
        const d = new Date(tt);
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        const ss = String(d.getSeconds()).padStart(2, '0');
        ctx.fillStyle = '#666';
        ctx.font = '10px Arial';
        ctx.fillText(`${hh}:${mm}:${ss}`, x, padTop + plotH + 5);
    }

    // Step line: horizontal segment per sample at its lane, with thin risers
    // between consecutive states.
    for (let i = 0; i < points.length; i++) {
        const li = laneIndex[points[i].state];
        if (li === undefined) continue;
        const yC = laneCenterY(li);
        const x1 = X(points[i].t);
        const x2 = (i < points.length - 1) ? X(points[i + 1].t) : padLeft + plotW;

        ctx.strokeStyle = lanes[li].color;
        ctx.lineWidth = 3;
        ctx.lineCap = 'butt';
        ctx.beginPath();
        ctx.moveTo(x1, yC);
        ctx.lineTo(Math.max(x1 + 1, x2), yC);
        ctx.stroke();

        if (i < points.length - 1) {
            const lj = laneIndex[points[i + 1].state];
            if (lj !== undefined && lj !== li) {
                ctx.strokeStyle = '#bbb';
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.moveTo(x2, yC);
                ctx.lineTo(x2, laneCenterY(lj));
                ctx.stroke();
            }
        }
    }

    // Plot border.
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 1;
    ctx.strokeRect(padLeft, padTop, plotW, plotH);

    // Caption with absolute exam window from the doc, when available.
    const caption = document.getElementById('proctorTimelineCaption');
    if (caption) {
        const startStr = frm.doc.exam_started_time
            ? frappe.datetime.str_to_user(frm.doc.exam_started_time)
            : new Date(t0).toLocaleString();
        const endStr = frm.doc.exam_submitted_time
            ? frappe.datetime.str_to_user(frm.doc.exam_submitted_time)
            : new Date(t1).toLocaleString();
        caption.textContent = `Exam window: ${startStr} → ${endStr}`;
    }

    drawProctorPie(points, lanes);
}

// Pie + breakdown of per-state time. Each sample's duration is the gap to the
// next sample; the final sample carries no duration (no future to fill).
function drawProctorPie(points, lanes) {
    const canvas = document.getElementById('proctorPie');
    const breakdown = document.getElementById('proctorPieBreakdown');
    if (!canvas || !breakdown) return;

    const totals = {};
    lanes.forEach(l => { totals[l.key] = 0; });
    for (let i = 0; i < points.length - 1; i++) {
        const dur = points[i + 1].t - points[i].t;
        if (dur > 0 && totals[points[i].state] !== undefined) {
            totals[points[i].state] += dur;
        }
    }
    const grandMs = lanes.reduce((s, l) => s + totals[l.key], 0);

    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const cx = W / 2, cy = H / 2, r = Math.min(W, H) / 2 - 6;

    if (grandMs === 0) {
        ctx.fillStyle = '#eee';
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, 2 * Math.PI);
        ctx.fill();
        ctx.fillStyle = '#999';
        ctx.font = '12px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('No duration data', cx, cy);
        breakdown.innerHTML = '';
        return;
    }

    let start = -Math.PI / 2;
    lanes.forEach(l => {
        const frac = totals[l.key] / grandMs;
        if (frac <= 0) return;
        const end = start + frac * 2 * Math.PI;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, r, start, end);
        ctx.closePath();
        ctx.fillStyle = l.color;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
        start = end;
    });

    const fmtMins = (ms) => {
        const totalSec = Math.round(ms / 1000);
        const m = Math.floor(totalSec / 60);
        const s = totalSec % 60;
        return `${m}m ${String(s).padStart(2, '0')}s`;
    };

    const rows = lanes.map(l => {
        const ms = totals[l.key];
        const pct = (ms / grandMs) * 100;
        return `
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="display: inline-block; width: 12px; height: 12px; border-radius: 2px; background:${l.color};"></span>
                <span style="flex: 0 0 130px;">${l.label}</span>
                <span style="flex: 0 0 80px; font-variant-numeric: tabular-nums;">${fmtMins(ms)}</span>
                <span style="color:#666; font-variant-numeric: tabular-nums;">${pct.toFixed(1)}%</span>
            </div>
        `;
    }).join('');
    breakdown.innerHTML = `
        <div style="font-weight: 600; margin-bottom: 6px;">Time by state (total ${fmtMins(grandMs)})</div>
        ${rows}
    `;
}

// Coloured seek bar drawn below the player controls. Each segment shows the
// proctoring state during that slice of wall-clock time. Clicking a position
// loads the chunk that covers that timestamp and seeks within it.
function buildProctorSeekBar(frm, chunkStarts) {
    const wrap = document.getElementById("esub-player-wrap");
    if (!wrap || !chunkStarts || chunkStarts.length === 0) return;

    // Parse proctoring timeline samples.
    let raw = [];
    try { raw = JSON.parse(frm.doc.retina_location_log || "[]") || []; } catch (e) { raw = []; }
    const points = [];
    raw.forEach(p => {
        if (!p || !p.timestamp) return;
        let state = p.state;
        if (!state) {
            if (p.gazeDirection === "screen") state = "screen";
            else if (p.gazeDirection === "away") state = "away";
            else state = "screen";
        }
        points.push({ t: Number(p.timestamp), state: state });
    });
    points.sort((a, b) => a.t - b.t);

    // Window the bar spans: from the earliest known point of activity
    // (first chunk start, or first sample) to the latest (last sample +
    // a small tail so the last segment is visible).
    const t0 = Math.min(chunkStarts[0], points.length ? points[0].t : chunkStarts[0]);
    const t1Sample = points.length ? points[points.length - 1].t : 0;
    const t1Chunk = chunkStarts[chunkStarts.length - 1] + 60_000; // assume ~1m tail
    const t1 = Math.max(t1Sample, t1Chunk, t0 + 1);
    const span = t1 - t0;

    const stateColor = {
        screen:     "#27ae60",
        distracted: "#f1c40f",
        away:       "#e74c3c",
        noface:     "#000000",
    };

    // (Re)build the seek wrapper. Idempotent so refresh() doesn't stack.
    let bar = wrap.querySelector(".esub-seek-bar");
    if (!bar) {
        const seekWrap = document.createElement("div");
        seekWrap.className = "esub-seek-wrap";
        seekWrap.style.marginTop = "8px";
        seekWrap.innerHTML = `
            <canvas class="esub-seek-bar"
                style="display:block;width:100%;height:14px;border-radius:3px;cursor:pointer;background:#eee"
                height="14"></canvas>
            <div class="esub-seek-caption text-muted"
                style="font-size:10px;margin-top:4px;display:flex;justify-content:space-between"></div>
        `;
        wrap.appendChild(seekWrap);
        bar = seekWrap.querySelector(".esub-seek-bar");
    }
    const caption = wrap.querySelector(".esub-seek-caption");

    function draw() {
        const w = bar.clientWidth || bar.parentElement.clientWidth || 480;
        bar.width = w;
        const ctx = bar.getContext("2d");
        const h = bar.height;
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = "#eee";
        ctx.fillRect(0, 0, w, h);

        if (points.length === 0) return;

        // Fill segments between consecutive samples.
        for (let i = 0; i < points.length; i++) {
            const ts = points[i].t;
            const tn = (i + 1 < points.length) ? points[i + 1].t : t1;
            const x = ((ts - t0) / span) * w;
            const x2 = ((tn - t0) / span) * w;
            ctx.fillStyle = stateColor[points[i].state] || "#888";
            ctx.fillRect(x, 0, Math.max(1, x2 - x), h);
        }

        // Faint chunk boundary ticks so the reviewer sees where each blob starts.
        ctx.fillStyle = "rgba(255,255,255,0.55)";
        chunkStarts.forEach(ts => {
            const x = ((ts - t0) / span) * w;
            ctx.fillRect(Math.round(x), 0, 1, h);
        });
    }

    if (caption) {
        const fmt = (ts) => {
            const d = new Date(ts);
            return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        };
        caption.innerHTML = `<span>${fmt(t0)}</span><span>${fmt(t1)}</span>`;
    }

    // Click → find chunk for that ts, load it, seek within it.
    bar.onclick = function (ev) {
        const rect = bar.getBoundingClientRect();
        const frac = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
        const clickTs = t0 + frac * span;

        // Find the chunk window covering clickTs (chunkStarts is ascending).
        let idx = chunkStarts.findIndex((s, i) => {
            const next = chunkStarts[i + 1] || Infinity;
            return clickTs >= s && clickTs < next;
        });
        if (idx < 0) idx = (clickTs < chunkStarts[0]) ? 0 : (chunkStarts.length - 1);

        const player = frm._candidateVideoPlayer;
        if (!player) return;
        player.playAt(idx);

        const offsetSec = Math.max(0, (clickTs - chunkStarts[idx]) / 1000);
        const video = document.getElementById("esub-player-video");
        if (!video) return;
        const seek = () => {
            try {
                const d = isFinite(video.duration) ? video.duration : 0;
                video.currentTime = d ? Math.min(offsetSec, d - 0.1) : offsetSec;
            } catch (e) { /* not seekable yet */ }
        };
        if (video.readyState >= 1 && isFinite(video.duration)) {
            seek();
        } else {
            video.addEventListener("loadedmetadata", seek, { once: true });
        }
    };

    draw();
    if (!frm._proctorSeekResize) {
        frm._proctorSeekResize = () => draw();
        window.addEventListener("resize", frm._proctorSeekResize);
    }
}
