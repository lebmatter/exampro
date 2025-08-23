// Global variable to track media permissions
let mediaPermissionsGranted = false;
let mediaStream = null;

// Request camera and audio access on window load (only if video proctoring is enabled)
window.addEventListener("load", function () {
  if (exam.enable_video_proctoring) {
    requestMediaAccess();
  }
});

async function requestMediaAccess() {
  try {
    // Request both video and audio permissions
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: true,
    });

    console.log("Media permissions granted");
    mediaPermissionsGranted = true;

    // Set up the video stream (this function is only called when video proctoring is enabled)
    const videoElement = document.getElementById("webcam-stream");
    if (videoElement) {
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
  if (exam.enable_video_proctoring && !mediaPermissionsGranted) {
    frappe.show_alert({
      message:
        "Please grant camera and microphone permissions before starting the exam.",
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
          return '<span class="d-flex align-items-center"><i class="bi bi-info-circle me-2"></i>Show instructions</span>';
        } else {
          return '<span class="d-flex align-items-center"><i class="bi bi-info-circle me-2"></i>Hide instructions</span>';
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