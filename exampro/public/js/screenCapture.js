// screenCapture.js — Mandatory screen recording via getDisplayMedia.
// Captures periodic + event-driven screenshots, uploads to S3/R2.

class ScreenCapture {
  constructor(options) {
    this.examSubmission = options.examSubmission;
    this.getServerTimeOffsetMs = options.getServerTimeOffsetMs || (() => 0);
    this.onScreenLost = options.onScreenLost || (() => {});
    this.randomIntervalMin = options.randomIntervalMin || 30;
    this.randomIntervalMax = options.randomIntervalMax || 120;

    this.stream = null;
    this.videoTrack = null;
    this.randomTimer = null;
    this.canvas = null;
    this.ctx = null;
    this.videoEl = null;

    this.uploadQueue = [];
    this.uploading = false;
    this.destroyed = false;
  }

  async requestDisplayMedia() {
    // Proactively request window-management permission so
    // window.screen.isExtended is accurate for multi-monitor detection.
    if (navigator.permissions && navigator.permissions.query) {
      try {
        await navigator.permissions.query({ name: "window-management" });
      } catch (_) {}
    }

    var constraints = {
      video: { displaySurface: "monitor" },
      audio: false,
      selfBrowserSurface: "exclude",
      monitorTypeSurfaces: "exclude",
    };

    this.stream = await navigator.mediaDevices.getDisplayMedia(constraints);
    this.videoTrack = this.stream.getVideoTracks()[0];

    this.videoTrack.addEventListener("ended", () => {
      if (!this.destroyed) {
        this.onScreenLost();
      }
    });

    return this.stream;
  }

  validateSelection() {
    if (!this.videoTrack) {
      return { valid: false, reason: "No video track available." };
    }

    var settings = this.videoTrack.getSettings();

    if (settings.displaySurface === "browser") {
      return { valid: false, reason: "You must share your entire screen, not a browser tab." };
    }
    if (settings.displaySurface === "window") {
      return { valid: false, reason: "You must share your entire screen, not a window." };
    }
    // Firefox doesn't report displaySurface — allow but log a warning
    if (!settings.displaySurface) {
      console.warn("displaySurface not reported by browser — screen selection cannot be verified.");
    }

    // Multi-monitor detection via Screen API (requires window-management permission)
    if (window.screen.isExtended) {
      return {
        valid: false,
        reason: "Multiple monitors detected. Please disconnect extra displays and try again.",
      };
    }

    return { valid: true, reason: "" };
  }

  startRandomCaptures() {
    if (this.destroyed) return;
    this._scheduleNextCapture();
  }

  _scheduleNextCapture() {
    if (this.destroyed) return;
    var delay = (Math.random() * (this.randomIntervalMax - this.randomIntervalMin) + this.randomIntervalMin) * 1000;
    this.randomTimer = setTimeout(() => {
      this.captureScreenshot(null);
      this._scheduleNextCapture();
    }, delay);
  }

  stopRandomCaptures() {
    if (this.randomTimer) {
      clearTimeout(this.randomTimer);
      this.randomTimer = null;
    }
  }

  captureEventScreenshot(eventText) {
    this.captureScreenshot(eventText);
  }

  captureScreenshot(eventText) {
    if (this.destroyed) return;
    if (!this.videoTrack || this.videoTrack.readyState !== "live") return;

    try {
      if (!this.videoEl) {
        this.videoEl = document.createElement("video");
        this.videoEl.autoplay = true;
        this.videoEl.playsInline = true;
        this.videoEl.muted = true;
        this.videoEl.style.cssText = "position:absolute;opacity:0;pointer-events:none;";
        this.videoEl.srcObject = this.stream;
        document.body.appendChild(this.videoEl);
      }

      var track = this.videoTrack;
      var settings = track.getSettings();
      var w = settings.width || this.videoEl.videoWidth;
      var h = settings.height || this.videoEl.videoHeight;
      if (!w || !h) return;

      if (!this.canvas) {
        this.canvas = document.createElement("canvas");
        this.ctx = this.canvas.getContext("2d");
      }
      this.canvas.width = w;
      this.canvas.height = h;

      this.ctx.drawImage(this.videoEl, 0, 0, w, h);

      this._drawTimestamp(w, h);

      if (eventText) {
        this._drawEventOverlay(eventText, w, h);
      }

      var self = this;
      this.canvas.toBlob(function (blob) {
        if (blob && !self.destroyed) {
          self._queueUpload(blob);
        }
      }, "image/jpeg", 0.85);
    } catch (e) {
      console.warn("Screenshot capture failed:", e);
    }
  }

  _drawTimestamp(w, h) {
    var offsetMs = this.getServerTimeOffsetMs();
    var serverNow = new Date(Date.now() + offsetMs);
    var ts = serverNow.getFullYear() + "-" +
      String(serverNow.getMonth() + 1).padStart(2, "0") + "-" +
      String(serverNow.getDate()).padStart(2, "0") + " " +
      String(serverNow.getHours()).padStart(2, "0") + ":" +
      String(serverNow.getMinutes()).padStart(2, "0") + ":" +
      String(serverNow.getSeconds()).padStart(2, "0") + " IST";

    var fontSize = Math.max(16, Math.round(h / 50));
    this.ctx.font = "bold " + fontSize + "px monospace";
    var textWidth = this.ctx.measureText(ts).width;
    var pad = 10;
    var x = w - textWidth - pad * 2;
    var y = h - fontSize - pad * 2;

    this.ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
    this.ctx.fillRect(x, y, textWidth + pad * 2, fontSize + pad * 2);
    this.ctx.fillStyle = "#ffffff";
    this.ctx.fillText(ts, x + pad, y + pad + fontSize);
  }

  _drawEventOverlay(text, w, h) {
    var fontSize = Math.max(20, Math.round(h / 35));
    this.ctx.font = "bold " + fontSize + "px sans-serif";
    var textWidth = this.ctx.measureText(text).width;
    var pad = 16;
    var bannerH = fontSize + pad * 2;
    var bannerY = (h - bannerH) / 2;

    this.ctx.fillStyle = "rgba(220, 53, 69, 0.85)";
    this.ctx.fillRect(0, bannerY, w, bannerH);
    this.ctx.fillStyle = "#ffffff";
    this.ctx.textAlign = "center";
    this.ctx.fillText(text, w / 2, bannerY + pad + fontSize);
    this.ctx.textAlign = "start";
  }

  _queueUpload(blob) {
    if (this.uploadQueue.length >= 5) {
      this.uploadQueue.shift();
    }
    this.uploadQueue.push(blob);
    this._processQueue();
  }

  _processQueue() {
    if (this.uploading || this.uploadQueue.length === 0 || this.destroyed) return;
    this.uploading = true;

    var blob = this.uploadQueue.shift();
    var self = this;

    this._uploadScreenshot(blob).finally(function () {
      self.uploading = false;
      setTimeout(function () {
        self._processQueue();
      }, 2000);
    });
  }

  _uploadScreenshot(blob) {
    var self = this;
    return new Promise(function (resolve) {
      frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.get_screenshot_upload_url",
        type: "POST",
        args: {
          exam_submission: self.examSubmission,
          file_size: blob.size,
        },
        callback: function (r) {
          if (!r.message || !r.message.url) {
            resolve();
            return;
          }
          fetch(r.message.url, {
            method: "PUT",
            body: blob,
            headers: { "Content-Type": "image/jpeg" },
            credentials: "omit",
          })
            .then(function () { resolve(); })
            .catch(function (e) {
              console.warn("Screenshot upload failed:", e);
              resolve();
            });
        },
        error: function () {
          resolve();
        },
      });
    });
  }

  destroy() {
    this.destroyed = true;
    this.stopRandomCaptures();
    if (this.videoTrack) {
      this.videoTrack.stop();
      this.videoTrack = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach(function (t) { t.stop(); });
      this.stream = null;
    }
    if (this.videoEl && this.videoEl.parentNode) {
      this.videoEl.parentNode.removeChild(this.videoEl);
    }
    this.videoEl = null;
    this.canvas = null;
    this.ctx = null;
    this.uploadQueue = [];
  }
}

if (typeof window !== "undefined") {
  window.ScreenCapture = ScreenCapture;
}
