// ── Accessibility: font size + high contrast ────────────────────
(function initAccessibility() {
  var scale = parseInt(localStorage.getItem('examFontScale'), 10) || 100;
  var hc = localStorage.getItem('examHighContrast') === 'true';

  applyFontScale(scale);
  applyHighContrast(hc);

  window.examA11y = {
    increaseFontSize: function () {
      scale = Math.min(150, scale + 10);
      applyFontScale(scale);
      localStorage.setItem('examFontScale', scale);
    },
    decreaseFontSize: function () {
      scale = Math.max(80, scale - 10);
      applyFontScale(scale);
      localStorage.setItem('examFontScale', scale);
    },
    toggleHighContrast: function () {
      hc = !hc;
      applyHighContrast(hc);
      localStorage.setItem('examHighContrast', hc);
    }
  };

  function applyFontScale(val) {
    document.documentElement.style.setProperty('--exam-font-scale', (val / 100).toString());
    var label = document.getElementById('fontSizeLabel');
    if (label) label.textContent = val + '%';
  }

  function applyHighContrast(on) {
    document.documentElement.setAttribute('data-high-contrast', on ? 'true' : 'false');
    var btn = document.getElementById('hcToggleBtn');
    if (btn) {
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    }
  }
})();

// Global variable to track media permissions
let mediaPermissionsGranted = false;
let mediaStream = null;

// Show pre-exam permissions modal for Registered candidates, then request
// media access after the user clicks Continue. If no features need permissions
// (no video proctoring, no screen recording), skip the modal entirely.
window.addEventListener("load", function () {
  var modalEl = document.getElementById("preExamModal");
  if (modalEl && exam.submission_status === "Registered") {
    var needsPermissions = exam.enable_video_proctoring || exam.enable_screen_recording;
    if (needsPermissions) {
      var modal = new bootstrap.Modal(modalEl);
      modal.show();
      document.getElementById("preExamContinueBtn").addEventListener("click", function () {
        modal.hide();
        if (exam.enable_video_proctoring) {
          requestMediaAccess();
        }
      });
      return;
    }
  }
  // No modal needed — request media access directly
  if (exam.enable_video_proctoring) {
    requestMediaAccess();
  }
});

async function requestMediaAccess() {
  try {
    // Reuse the single shared camera acquisition (defined in examform.js) so
    // the permission pre-check, the recorder, and the face tracker all share
    // one MediaStream. Opening the camera here independently would steal the
    // device from the recorder and fire spurious track-ended terminations.
    if (typeof acquireCameraStream === "function") {
      mediaStream = await acquireCameraStream();
    } else {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });
    }

    console.log("Media permissions granted");
    mediaPermissionsGranted = true;

    // Set up the video stream (this function is only called when video proctoring is enabled).
    // Only attach if nothing is attached yet — startRecording() also binds this element.
    const videoElement = document.getElementById("webcam-stream");
    if (videoElement && !videoElement.srcObject) {
      videoElement.srcObject = mediaStream;
    }
  } catch (error) {
    console.error("Error accessing media devices:", error);
    mediaPermissionsGranted = false;

    // Show error message to user
    showMediaPermissionError();
  }
}

function showMediaPermissionError() {
  frappe.show_alert({
    message:
      "Camera and microphone access is required to start the exam. Please allow access and refresh the page.",
    indicator: "red",
  });

  // Show modal with more detailed instructions
  $("#alertTitle").text("Media Access Required");
  $("#alertText").html(`
          <p>This exam requires access to your camera and microphone for proctoring purposes.</p>
          <p>Please:</p>
          <ol>
              <li>Click "Allow" when prompted for camera and microphone access</li>
              <li>If you accidentally blocked access, click on the camera/microphone icon in your browser's address bar to enable permissions</li>
              <li>Refresh this page after granting permissions</li>
          </ol>
          <p><strong>You cannot start the exam without granting these permissions.</strong></p>
      `);
  $("#examAlert").modal("show");
}

function checkMediaPermissionsBeforeStart() {
  // Only check permissions if video proctoring is enabled
  if (!exam.enable_video_proctoring) return true;

  if (!mediaPermissionsGranted) {
    frappe.show_alert({
      message:
        "Please grant camera and microphone permissions before starting the exam.",
      indicator: "red",
    });
    return false;
  }

  // Camera is open but lid/shutter may still be closed — require a visible face.
  // faceCurrentlyVisible is set by the gazer's onFaceDetected callback in examform.js.
  if (typeof faceCurrentlyVisible !== "undefined" && !faceCurrentlyVisible) {
    frappe.show_alert({
      message:
        "Face not detected. Open your camera shutter and ensure your face is clearly visible before starting.",
      indicator: "red",
    });
    return false;
  }

  return true;
}

$(document).ready(function () {
  // Create calculator instance only if calculator is enabled
  if (exam.enable_calculator) {
    calculator = new BootstrapCalculator("#exam-calculator");
    calculator.init();
  }

  // Only add toggle functionality if instructions exist
  if (exam.instructions) {
    $("#toggleInstruction").click(function () {
      $("#instruction").toggle();
      $(this).html(function (i, html) {
        if (html.includes("Hide instructions")) {
          return '<span class="d-flex align-items-center"><i data-feather="info"></i>Show instructions</span>';
        } else {
          return '<span class="d-flex align-items-center"><i data-feather="info"></i>Hide instructions</span>';
        }
      });
    });
  }

  // Timer toggle is now handled by Alpine.js - no jQuery code needed
  // Video toggle is now handled by Alpine.js - no jQuery code needed

  // Chat functionality - these are now handled by initializeChatbox() if chatbox.js is loaded
  // Fallback handlers in case chatbox.js is not available
  if (typeof initializeChatbox !== 'function') {
    $("#send-message").click(function () {
      sendChatMessage();
    });

    $("#chat-input").keypress(function (e) {
      if (e.which == 13) {
        sendChatMessage();
        return false;
      }
    });
  }
});