/**
 * Shared gaze / attention-score chart rendering.
 *
 * Used by the Exam Submission desk form, the live proctor modal,
 * and the proctor archive modal.
 */

var GazeCharts = (function () {

  var LANES = [
    { key: 'screen',     label: 'Screen Gaze',     color: '#27ae60' },
    { key: 'distracted', label: 'Distracted Gaze', color: '#f1c40f' },
    { key: 'away',       label: 'Away Gaze',       color: '#e74c3c' },
    { key: 'noface',     label: 'No Face',         color: '#000000' },
  ];

  function parseRetinaLog(raw) {
    if (typeof raw === 'string') {
      try { raw = JSON.parse(raw) || []; } catch (e) { raw = []; }
    }
    if (!Array.isArray(raw)) raw = [];

    var points = [];
    raw.forEach(function (p) {
      if (!p || !p.timestamp) return;
      var state = p.state;
      if (!state) {
        if (p.gazeDirection === 'screen') state = 'screen';
        else if (p.gazeDirection === 'away') state = 'away';
        else state = 'screen';
      }
      points.push({ t: Number(p.timestamp), state: state });
    });
    points.sort(function (a, b) { return a.t - b.t; });
    return points;
  }

  function computeTotals(points) {
    var totals = {};
    LANES.forEach(function (l) { totals[l.key] = 0; });
    for (var i = 0; i < points.length - 1; i++) {
      var dur = points[i + 1].t - points[i].t;
      if (dur > 0 && totals[points[i].state] !== undefined) {
        totals[points[i].state] += dur;
      }
    }
    var grandMs = LANES.reduce(function (s, l) { return s + totals[l.key]; }, 0);
    return { totals: totals, grandMs: grandMs };
  }

  function fmtMins(ms) {
    var totalSec = Math.round(ms / 1000);
    var m = Math.floor(totalSec / 60);
    var s = totalSec % 60;
    return m + 'm ' + String(s).padStart(2, '0') + 's';
  }

  function drawTimeline(canvasEl, points, opts) {
    opts = opts || {};
    if (typeof canvasEl === 'string') canvasEl = document.getElementById(canvasEl);
    if (!canvasEl) return;

    var ctx = canvasEl.getContext('2d');
    var W = canvasEl.width, H = canvasEl.height;

    var laneIndex = {};
    LANES.forEach(function (l, i) { laneIndex[l.key] = i; });

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

    var padLeft = 110, padRight = 20, padTop = 16, padBottom = 34;
    var plotW = W - padLeft - padRight;
    var plotH = H - padTop - padBottom;
    var laneH = plotH / LANES.length;

    var t0 = points[0].t;
    var t1 = points.length > 1 ? points[points.length - 1].t : t0 + 1;
    var span = Math.max(1, t1 - t0);
    var X = function (t) { return padLeft + ((t - t0) / span) * plotW; };
    var laneCenterY = function (i) { return padTop + i * laneH + laneH / 2; };

    LANES.forEach(function (l, i) {
      var yTop = padTop + i * laneH;
      ctx.fillStyle = (i % 2 === 0) ? '#fafafa' : '#f2f2f2';
      ctx.fillRect(padLeft, yTop, plotW, laneH);
      ctx.fillStyle = '#333';
      ctx.font = '12px Arial';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(l.label, padLeft - 10, yTop + laneH / 2);
      ctx.fillStyle = l.color;
      ctx.fillRect(padLeft - 6, yTop + laneH / 2 - 1, 4, 2);
    });

    var ticks = 6;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (var k = 0; k <= ticks; k++) {
      var tt = t0 + (span * k) / ticks;
      var x = X(tt);
      ctx.strokeStyle = '#eee';
      ctx.beginPath();
      ctx.moveTo(x, padTop);
      ctx.lineTo(x, padTop + plotH);
      ctx.stroke();
      var d = new Date(tt);
      var hh = String(d.getHours()).padStart(2, '0');
      var mm = String(d.getMinutes()).padStart(2, '0');
      var ss = String(d.getSeconds()).padStart(2, '0');
      ctx.fillStyle = '#666';
      ctx.font = '10px Arial';
      ctx.fillText(hh + ':' + mm + ':' + ss, x, padTop + plotH + 5);
    }

    for (var i = 0; i < points.length; i++) {
      var li = laneIndex[points[i].state];
      if (li === undefined) continue;
      var yC = laneCenterY(li);
      var x1 = X(points[i].t);
      var x2 = (i < points.length - 1) ? X(points[i + 1].t) : padLeft + plotW;

      ctx.strokeStyle = LANES[li].color;
      ctx.lineWidth = 3;
      ctx.lineCap = 'butt';
      ctx.beginPath();
      ctx.moveTo(x1, yC);
      ctx.lineTo(Math.max(x1 + 1, x2), yC);
      ctx.stroke();

      if (i < points.length - 1) {
        var lj = laneIndex[points[i + 1].state];
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

    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 1;
    ctx.strokeRect(padLeft, padTop, plotW, plotH);

    if (opts.captionEl) {
      var captionEl = typeof opts.captionEl === 'string'
        ? document.getElementById(opts.captionEl) : opts.captionEl;
      if (captionEl) {
        var fmtDate = function (v) { return v ? new Date(v).toLocaleString() : null; };
        var startStr = (opts.examStartedTime
          ? (typeof frappe !== 'undefined' ? frappe.datetime.str_to_user(opts.examStartedTime) : fmtDate(opts.examStartedTime))
          : new Date(t0).toLocaleString());
        var endStr = (opts.examSubmittedTime
          ? (typeof frappe !== 'undefined' ? frappe.datetime.str_to_user(opts.examSubmittedTime) : fmtDate(opts.examSubmittedTime))
          : new Date(t1).toLocaleString());
        captionEl.textContent = 'Exam window: ' + startStr + ' → ' + endStr;
      }
    }
  }

  function drawPie(canvasEl, breakdownEl, points, opts) {
    opts = opts || {};
    if (typeof canvasEl === 'string') canvasEl = document.getElementById(canvasEl);
    if (typeof breakdownEl === 'string') breakdownEl = document.getElementById(breakdownEl);
    if (!canvasEl || !breakdownEl) return {};

    var result = computeTotals(points);
    var totals = result.totals;
    var grandMs = result.grandMs;

    var ctx = canvasEl.getContext('2d');
    var W = canvasEl.width, H = canvasEl.height;
    ctx.clearRect(0, 0, W, H);

    var cx = W / 2, cy = H / 2, r = Math.min(W, H) / 2 - 6;

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
      breakdownEl.innerHTML = '';
      return { totals: totals, grandMs: grandMs };
    }

    var start = -Math.PI / 2;
    LANES.forEach(function (l) {
      var frac = totals[l.key] / grandMs;
      if (frac <= 0) return;
      var end = start + frac * 2 * Math.PI;
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

    var rows = LANES.map(function (l) {
      var ms = totals[l.key];
      var pct = (ms / grandMs) * 100;
      return '<div style="display:flex;align-items:center;gap:8px;">' +
        '<span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:' + l.color + ';"></span>' +
        '<span style="flex:0 0 130px;">' + l.label + '</span>' +
        '<span style="flex:0 0 80px;font-variant-numeric:tabular-nums;">' + fmtMins(ms) + '</span>' +
        '<span style="color:#666;font-variant-numeric:tabular-nums;">' + pct.toFixed(1) + '%</span>' +
        '</div>';
    }).join('');
    breakdownEl.innerHTML =
      '<div style="font-weight:600;margin-bottom:6px;">Time by state (total ' + fmtMins(grandMs) + ')</div>' + rows;

    return { totals: totals, grandMs: grandMs };
  }

  function renderAttentionScore(el, totals, grandMs, faceCountChanges) {
    if (typeof el === 'string') el = document.getElementById(el);
    if (!el) return;

    if (grandMs <= 0) { el.innerHTML = ''; return; }
    var durationSec = grandMs / 1000;
    var durationHrs = durationSec / 3600;

    var awayPct = ((totals.away || 0) / grandMs) * 100;
    var distractedPct = ((totals.distracted || 0) / grandMs) * 100;
    var changesPerHr = durationHrs > 0 ? faceCountChanges / durationHrs : 0;

    var awayScore = Math.max(0, 100 - Math.max(0, awayPct - 5) * 5);
    var changesScore = Math.max(0, 100 - Math.max(0, changesPerHr - 3) * 15);
    var distractedScore = Math.max(0, 100 - Math.max(0, distractedPct - 20) * 2);

    var score = Math.round(awayScore * 0.45 + changesScore * 0.30 + distractedScore * 0.25);
    var color = score >= 70 ? '#198754' : score >= 40 ? '#fd7e14' : '#dc3545';
    var label = score >= 70 ? 'Good' : score >= 40 ? 'Moderate' : 'Poor';

    el.innerHTML =
      '<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:12px;">' +
        '<span style="font-size:2rem;font-weight:700;color:' + color + ';line-height:1;font-variant-numeric:tabular-nums;">' + score + '</span>' +
        '<span style="font-size:0.85rem;font-weight:600;color:' + color + ';">' + label + '</span>' +
        '<span style="font-size:0.75rem;color:#666;">Attention Score</span>' +
      '</div>' +
      '<div style="font-size:0.75rem;color:#666;margin-bottom:8px;display:flex;gap:16px;flex-wrap:wrap;">' +
        '<span>Away: ' + awayPct.toFixed(1) + '%</span>' +
        '<span>Distracted: ' + distractedPct.toFixed(1) + '%</span>' +
        '<span>Face changes/hr: ' + changesPerHr.toFixed(1) + '</span>' +
      '</div>';
  }

  function renderAll(opts) {
    var points = parseRetinaLog(opts.retinaLog);
    drawTimeline(opts.timelineCanvas, points, {
      captionEl: opts.captionEl,
      examStartedTime: opts.examStartedTime,
      examSubmittedTime: opts.examSubmittedTime,
    });
    var result = drawPie(opts.pieCanvas, opts.breakdownEl, points);
    if (result.grandMs > 0) {
      renderAttentionScore(opts.scoreEl, result.totals, result.grandMs, opts.faceCountChanges || 0);
    }
  }

  return {
    LANES: LANES,
    parseRetinaLog: parseRetinaLog,
    computeTotals: computeTotals,
    drawTimeline: drawTimeline,
    drawPie: drawPie,
    renderAttentionScore: renderAttentionScore,
    renderAll: renderAll,
  };

})();
