var hiddenTime = 0;
var visibleTime = 0;
var examOverview;
var currentQuestion;
var detector;
var gazer;
var lastNoFaceAlertTime = 0;
var noFaceAlertCooldown = 10000; // 10 seconds cooldown between no face alerts
var lastWebcamErrorTime = 0;
var webcamErrorCooldown = 5000; // 5 seconds cooldown between webcam error alerts
var recordingInitialized = false; // Prevent multiple recording initializations
var submitAnswerTimeout; // Debounce timeout for textarea input
var isSubmittingAnswer = false; // Flag to prevent concurrent submissions
var pendingNavigation = false; // Set when a Next/Finish click arrives during an in-flight save
var faceCurrentlyVisible = false; // Updated by gazer onFaceDetected; gates exam start
var noFaceTerminationTimer = null; // setTimeout id for the 60s no-face termination
var noFaceCountdownInterval = null; // setInterval id for the visible countdown
var NO_FACE_GRACE_SECONDS = 60;
var helpShownFor = new Set(); // qs_no values where help has already been shown this session
var helpReadingTimer = null;

// Simple notification function as fallback
function showNotification(message, type = 'info') {
    // Try to use toastr first
    if (typeof toastr !== 'undefined') {
        switch(type) {
            case 'warning':
                toastr.warning(message);
                break;
            case 'error':
                toastr.error(message);
                break;
            case 'success':
                toastr.success(message);
                break;
            default:
                toastr.info(message);
        }
    } else {
        // Fallback to console and simple visual indicator
        console.log(`[${type.toUpperCase()}] ${message}`);
        
        // Create a simple notification element
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'error' ? '#f44336' : type === 'warning' ? '#ff9800' : '#2196f3'};
            color: white;
            padding: 12px 20px;
            border-radius: 4px;
            z-index: 10000;
            font-size: 14px;
            max-width: 300px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        `;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        // Remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
}

// Function to update the countdown timer
function updateTimer() {
    if (!examEnded) {
        var remainingTime = new Date(exam.end_time) - new Date().getTime();
        if (remainingTime <= 0) {
            // Display "0m 0s" when time is up
            document.getElementById("exam-timer").innerHTML = "00:00";
            
            // Show exam alert when time is up
            examAlert("Time's Up!", "Your exam time has expired. Click OK to proceed.");

            endExam(true);
            return; // Stop the timer from updating further
        }
        // Calculate minutes and seconds
        var minutes = Math.floor((remainingTime % (1000 * 60 * 60)) / (1000 * 60));
        var seconds = Math.floor((remainingTime % (1000 * 60)) / 1000);
        if (remainingTime > (1000 * 60 * 60)) { // 1000 milliseconds * 60 seconds * 60 minutes = 1 hour
            // Calculate hours, minutes, and seconds
            var hours = Math.floor(remainingTime / (1000 * 60 * 60));
            // Display the countdown timer
            $(".timer").text(`${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`);


        } else {
            // Display the countdown timer
            $(".timer").text(`${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`);

        }
        // Update the timer every second
        setTimeout(updateTimer, 1000);
    }

}

const answrdCheck = `<i class="bi bi-check-circle"></i>`;
const answrLater = `<i class="bi bi-clock-history"></i>`;
var examEnded = false;
var currentQsNo = 1;
// Initialize variables
let recorder;
let stream;
let recordingStream;
let recordingInterval;

// Offset between server wall-clock and client wall-clock (server - client, ms).
// Captured from the `Date` header on the first chunk-upload mint response so the
// watermark cannot be skewed by a candidate manipulating their system clock.
let serverTimeOffsetMs = 0;

function formatWatermarkTimestamp(date) {
    // Render as YYYY-MM-DD HH:MM:SS IST to keep the watermark legible and
    // unambiguous across viewer locales.
    try {
        const parts = new Intl.DateTimeFormat("en-GB", {
            timeZone: "Asia/Kolkata",
            year: "numeric", month: "2-digit", day: "2-digit",
            hour: "2-digit", minute: "2-digit", second: "2-digit",
            hour12: false,
        }).formatToParts(date);
        const map = {};
        parts.forEach(p => { map[p.type] = p.value; });
        return `${map.year}-${map.month}-${map.day} ${map.hour}:${map.minute}:${map.second} IST`;
    } catch (e) {
        return date.toISOString();
    }
}

// Build a MediaStream that mirrors the webcam through a canvas with a
// server-time timestamp burned into each frame. Returns the canvas stream
// plus a cleanup function used at stopRecording time.
function buildWatermarkedStream(rawStream) {
    const sourceVideo = document.getElementById("watermark-source");
    const canvas = document.getElementById("watermark-canvas");
    if (!sourceVideo || !canvas) {
        console.warn("Watermark DOM elements missing; recording without watermark");
        return { stream: rawStream.clone(), stop: function () {} };
    }

    const track = rawStream.getVideoTracks()[0];
    const settings = track ? track.getSettings() : {};
    const width = settings.width || sourceVideo.videoWidth || 640;
    const height = settings.height || sourceVideo.videoHeight || 480;
    canvas.width = width;
    canvas.height = height;

    sourceVideo.srcObject = rawStream;
    // play() can reject if the page hasn't seen user interaction; the
    // watermark <video> is muted+playsinline so autoplay is permitted.
    sourceVideo.play().catch(err => console.warn("watermark source play:", err));

    const ctx = canvas.getContext("2d");
    const fontSize = Math.max(14, Math.round(height / 28));
    ctx.font = `${fontSize}px monospace`;
    ctx.textBaseline = "bottom";

    let cancelled = false;
    let rafId = null;
    const useRVFC = typeof sourceVideo.requestVideoFrameCallback === "function";

    function drawFrame() {
        if (cancelled) return;
        if (sourceVideo.readyState >= 2) {
            ctx.drawImage(sourceVideo, 0, 0, canvas.width, canvas.height);
            const text = formatWatermarkTimestamp(new Date(Date.now() + serverTimeOffsetMs));
            const padding = Math.round(fontSize * 0.4);
            const textMetrics = ctx.measureText(text);
            const stripWidth = textMetrics.width + padding * 2;
            const stripHeight = fontSize + padding * 2;
            const x = canvas.width - stripWidth - padding;
            const y = canvas.height - padding;
            ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
            ctx.fillRect(x, y - stripHeight + padding, stripWidth, stripHeight);
            ctx.fillStyle = "#ffffff";
            ctx.fillText(text, x + padding, y);
        }
        if (useRVFC) {
            sourceVideo.requestVideoFrameCallback(drawFrame);
        } else {
            rafId = requestAnimationFrame(drawFrame);
        }
    }

    if (useRVFC) {
        sourceVideo.requestVideoFrameCallback(drawFrame);
    } else {
        rafId = requestAnimationFrame(drawFrame);
    }

    const watermarkedStream = canvas.captureStream(15);

    return {
        stream: watermarkedStream,
        stop: function () {
            cancelled = true;
            if (rafId) cancelAnimationFrame(rafId);
            try { sourceVideo.pause(); } catch (e) {}
            sourceVideo.srcObject = null;
            watermarkedStream.getTracks().forEach(t => t.stop());
        },
    };
}
let watermarkHandle = null;

// Read the server's wall-clock via the HTTP Date header on any same-origin
// response. Updates `serverTimeOffsetMs` so the watermark text reflects server
// time even when the candidate's system clock is wrong.
async function refreshServerTimeOffset() {
    try {
        const sentAt = Date.now();
        const resp = await fetch("/api/method/ping", {
            method: "GET",
            credentials: "same-origin",
            cache: "no-store",
        });
        const headerDate = resp.headers.get("Date");
        if (!headerDate) return;
        const parsed = Date.parse(headerDate);
        if (isNaN(parsed)) return;
        // Subtract half the RTT so the offset is measured at the midpoint
        // between request and response — closer to what the server thought
        // "now" was at the moment we asked.
        const rtt = Date.now() - sentAt;
        serverTimeOffsetMs = parsed + Math.round(rtt / 2) - Date.now();
    } catch (err) {
        console.warn("Failed to refresh server time offset:", err);
    }
}

async function sendVideoBlob(blob) {
    // Two-step upload: mint a short-lived, key-bound presigned PUT from the
    // server, then upload the chunk directly to S3/R2. The server never sees
    // the bytes, which keeps gunicorn workers free during the exam.
    //
    // We declare blob.size to the mint endpoint so the server signs an exact
    // Content-Length into the URL. The browser auto-sets Content-Length from
    // the body, so a tampered client cannot smuggle a larger payload without
    // breaking the signature.
    let mint;
    try {
        mint = await frappe.call({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.get_video_upload_url",
            type: "POST",
            args: {
                exam_submission: exam["exam_submission"],
                chunk_size: blob.size,
            },
        });
    } catch (err) {
        console.error("Failed to obtain video upload URL:", err);
        return;
    }


    const data = mint && mint.message;
    if (!data || !data.url) {
        console.error("Invalid upload URL response", mint);
        return;
    }

    if (data.max_bytes && blob.size > data.max_bytes) {
        console.warn("Video chunk exceeds max upload size; dropping",
            blob.size, ">", data.max_bytes);
        return;
    }

    try {
        const resp = await fetch(data.url, {
            method: data.method || "PUT",
            body: blob,
            headers: data.headers || { "Content-Type": "video/webm" },
            // Do not send cookies/credentials to the storage origin.
            credentials: "omit",
            mode: "cors",
        });
        if (!resp.ok) {
            const body = await resp.text().catch(() => "");
            console.error("S3 upload failed", resp.status, body);
        }
    } catch (err) {
        console.error("S3 upload network error:", err);
    }
}

// Single, shared webcam acquisition.
//
// The camera must be opened exactly once and the resulting MediaStream shared
// across every consumer (permission pre-check, the proctoring recorder, and the
// Gazer face tracker). Opening it more than once made later getUserMedia/Camera
// calls steal the device from earlier ones, firing spurious `track.ended`
// events that instantly terminated exams and leaving the face tracker with no
// frames. This memoises one acquisition: concurrent callers share the in-flight
// promise, and later callers get the already-live stream.
var sharedCameraStream = null;
var sharedCameraPromise = null;

function acquireCameraStream() {
    // Reuse a live stream if we already have one.
    if (sharedCameraStream &&
        sharedCameraStream.getVideoTracks().some(function (t) { return t.readyState === 'live'; })) {
        return Promise.resolve(sharedCameraStream);
    }
    // Join the in-flight acquisition if one is already running.
    if (sharedCameraPromise) {
        return sharedCameraPromise;
    }
    sharedCameraPromise = navigator.mediaDevices
        .getUserMedia({ video: true, audio: true })
        .then(function (s) {
            sharedCameraStream = s;
            sharedCameraPromise = null;
            return s;
        })
        .catch(function (err) {
            sharedCameraPromise = null;
            throw err;
        });
    return sharedCameraPromise;
}

// Expose for exam-index.js (loaded after this file) so the permission pre-check
// reuses the same acquisition rather than opening a second camera.
if (typeof window !== 'undefined') {
    window.acquireCameraStream = acquireCameraStream;
}

// Function to start recording
function startRecording() {
    // Prevent multiple initializations
    if (recordingInitialized) {
        console.log('Recording already initialized');
        return;
    }
    
    recordingInitialized = true;

    // Fire-and-forget; ok if it lands a beat after recording starts.
    refreshServerTimeOffset();

    // Reuse the single shared camera stream rather than opening the device
    // again — a second open would end the first stream's tracks.
    acquireCameraStream()
        .then(function (mediaStream) {
            stream = mediaStream;

            // Feed RecordRTC a canvas-derived stream so every frame carries a
            // server-time watermark burned into the pixels (survives download).
            watermarkHandle = buildWatermarkedStream(stream);
            recordingStream = watermarkHandle.stream;
            
            // Watch only the VIDEO track for disconnection. The shared stream
            // also carries an (unused) audio track from the permission check;
            // a mic ending must not be treated as a webcam disconnect.
            stream.getVideoTracks().forEach(track => {
                track.addEventListener('ended', function () {
                    const currentTime = Date.now();
                    if (currentTime - lastWebcamErrorTime > webcamErrorCooldown) {
                        console.error('Webcam was disabled or stopped');
                        sendMessage('Webcam was disabled or stopped', 'Warning', 'nowebcam');
                        lastWebcamErrorTime = currentTime;

                        // Show a less intrusive notification
                        showNotification('Webcam was disabled or stopped. Please fix the issue.', 'error');
                    }
                });
            });

            // Attach the original stream to the video element
            const videoElement = document.getElementById('webcam-stream');
            videoElement.srcObject = stream;
            
            // Set video properties to prevent autoplay issues
            videoElement.muted = true;
            videoElement.playsInline = true;
            
            // Handle video play with user interaction requirement
            const playVideo = () => {
                videoElement.play().catch(error => {
                    console.warn('Video autoplay prevented:', error);
                    // Video will start playing when user interacts with the page
                });
            };
            
            // Try to play immediately (will work if user has already interacted)
            playVideo();
            
            // Add one-time click listener to start video if autoplay failed
            const startVideoOnInteraction = () => {
                playVideo();
                document.removeEventListener('click', startVideoOnInteraction);
                document.removeEventListener('keydown', startVideoOnInteraction);
            };
            
            // Listen for any user interaction to start video
            document.addEventListener('click', startVideoOnInteraction, { once: true });
            document.addEventListener('keydown', startVideoOnInteraction, { once: true });

            // Initialize gazer after the video element is created and stream is attached
            // Use the main webcam-stream video element for gazer (better tracking with original stream)
            if (exam.enable_video_proctoring && !gazer) {
                try {
                    gazer = new Gazer("webcam-stream", {
                        postTrackingDataInterval: 15,
                        
                        // Display options
                        showFaceRectangle: false,
                        showGazeVector: false,
                        showEyePoints: false,
                        enableLogs: false, 
                        onFaceDetected: (faces) => {
                            const currentTime = Date.now();
                            if (faces.length > 0) {
                                faceCurrentlyVisible = true;
                                // Face is back: cancel any pending termination
                                cancelNoFaceCountdown();
                            } else {
                                faceCurrentlyVisible = false;
                                // Existing chat warning (cooldown-throttled)
                                if (currentTime - lastNoFaceAlertTime > noFaceAlertCooldown) {
                                    console.warn('No face detected in camera view');
                                    sendMessage('No face detected in camera view', 'Warning', 'noface');
                                    lastNoFaceAlertTime = currentTime;

                                    // Show a less intrusive notification
                                    showNotification('Please ensure your face is visible to the camera', 'warning');
                                }
                                // During an active exam, start the 60s grace countdown
                                if (exam.submission_status === "Started" && !examEnded) {
                                    startNoFaceCountdown();
                                }
                            }
                        },
                        // Callback functions
                        onPostTrackingData: (trackingData) => {
                            // Don't post tracking data before the exam has started
                            if (exam.submission_status !== "Started") {
                                return;
                            }
                            // Send tracking data to server
                            frappe.call({
                                method: "exampro.exam_pro.doctype.exam_submission.exam_submission.post_tracking_info",
                                type: "POST",
                                args: {
                                    'info': JSON.stringify({
                                        'exam_submission': exam["exam_submission"],
                                        'faceCountChanges': trackingData.faceCountChanges,
                                        'totalAwayTime': trackingData.totalAwayTime,
                                        'totalDistractedTime': trackingData.totalDistractedTime,
                                        'retinaLocations': trackingData.retinaLocations || []
                                    })
                                },
                                callback: (data) => {
                                },
                                error: (error) => {
                                    console.error("Failed to send tracking data:", error);
                                }
                            });
                        },
                        onError: (error) => {
                            console.error("Gazer error:", error);
                            // Don't show alert for gazer errors to prevent loops
                        }
                    });

                    // Apply low performance preset
                    gazer.setPerformanceMode('low');

                    // Apply relaxed sensitivity preset  
                    gazer.setSensitivityMode('relaxed');

                    // Start gazer for the candidate's session — Registered (so we can verify
                    // a face is visible before allowing Start) or Started (during the exam).
                    // Feed it the shared stream so it does NOT open the camera a second
                    // time via MediaPipe's Camera helper.
                    if (exam.submission_status === "Started" || exam.submission_status === "Registered") {
                        gazer.startWithStream(stream);
                    }
                } catch (error) {
                    console.error("Failed to initialize gazer:", error);
                    // Continue without gazer if it fails to initialize
                    gazer = null;
                }
            }

            if (exam["submission_status"] === "Started") { 
            // 150 kbps gives the watermark text enough pixels to remain
            // legible after VP8 encoding; the previous 8 kbps smeared text to
            // unreadable noise.
            const recorderOptions = {
                type: 'video',
                mimeType: 'video/webm',
                videoBitsPerSecond: 150000,
                disableLogs: true,
            };

            recorder = RecordRTC(recordingStream, recorderOptions);

            // Start recording
            recorder.startRecording();

            // Start sending recorded blobs to the server every 10 seconds
            recordingInterval = setInterval(function () {
                recorder.stopRecording(function () {
                    // Get the recorded blob
                    let blob = recorder.getBlob();

                    sendVideoBlob(blob);
                    // Reset the recorder with the same options.
                    recorder = RecordRTC(recordingStream, recorderOptions);

                    recorder.startRecording();
                });
            }, 10000);
            }
        })
        .catch(function (error) {
            console.error('Webcam detection error:', error);
            const currentTime = Date.now();
            if (currentTime - lastWebcamErrorTime > webcamErrorCooldown) {
                sendMessage('Webcam was not detected', 'Warning', 'nowebcam');
                lastWebcamErrorTime = currentTime;
                
                // Show a less intrusive notification
                showNotification('No webcam detected. Please check your camera permissions.', 'error');
            }
            
            // Reset recording flag if initialization failed
            recordingInitialized = false;
        });
}

// Function to stop recording
function stopRecording() {
    // Stop recording and clear the recording interval
    clearInterval(recordingInterval);

    const releaseStreams = function () {
        if (watermarkHandle) {
            try { watermarkHandle.stop(); } catch (e) {}
            watermarkHandle = null;
        }
        if (stream) {
            stream.getTracks().forEach(function (track) { track.stop(); });
        }
        if (recordingStream) {
            recordingStream.getTracks().forEach(function (track) { track.stop(); });
        }
    };

    if (recorder) {
        recorder.stopRecording(releaseStreams);
    } else {
        releaseStreams();
    }

    // Reset recording flag so it can be reinitialized if needed
    recordingInitialized = false;
}

function activateDetector(){
    if (!detector) {
        detector = new InactivityDetector({
            warningThreshold: 1,
            onInactive: (inactiveStr, secondsInactive) => {
                tabChangeStr = `Tab changed detected for ${secondsInactive} seconds.`;
                console.log(tabChangeStr);
                sendMessage(tabChangeStr, "Warning", "tabchange");
                examAlert(tabChangeStr, "Return to the window immediately!");
            },
            onActive: () => {
                console.log("User active again");
            },
            onMonitorChange: (lastScreens, currentScreens) => {
                monitorChangeStr = `Monitor changed from ${lastScreens} to ${currentScreens}`;
                sendMessage(monitorChangeStr, "Warning", "monitorchange");
                examAlert(monitorChangeStr);
            }
        });
        detector.init();
    }
}

frappe.ready(() => {
    $('#submitTopBtn').hide();
    updateOverviewMap();

    // Disable right-click context menu
    document.addEventListener('contextmenu', function(e) {
        e.preventDefault();
    });

    // Disable text selection
    document.addEventListener('selectstart', function(e) {
        e.preventDefault();
    });

    // Disable copy
    document.addEventListener('copy', function(e) {
        e.preventDefault();
    });

    // Disable screenshot-related key combinations
    document.addEventListener('keydown', function(e) {
        // Disable "Print Screen" (PrtSc)
        if (e.key === 'PrintScreen') {
            e.preventDefault();
            alert('Screenshots are disabled!');
        }

        // Disable Ctrl+Shift+S (Windows Snipping Tool shortcut)
        if (e.ctrlKey && e.shiftKey && e.key === 'S') {
            e.preventDefault();
            alert('Screenshots are disabled!');
        }

        // Disable Cmd+Shift+4 (MacOS screenshot shortcut)
        if (e.metaKey && e.shiftKey && e.key === '4') {
            e.preventDefault();
            alert('Screenshots are disabled!');
        }

        // Disable Ctrl+P (Print command)
        if (e.ctrlKey && e.key === 'P') {
            e.preventDefault();
            alert('Printing is disabled!');
        }
    });

    // check if exam is already started
    if (exam["submission_status"] === "Registered") {
        $("#quiz-btn").text("Start exam");
        $("#quiz-btn").show();
        $("#quiz-message").hide();
        $("#quiz-btn").click((e) => {
            e.preventDefault();
            startExam();
        });
    } else {
        $('#submitTopBtn').show();
        $("#quiz-form").removeClass("hide");
        // on first load, show the last question loaded
        getQuestion(exam["current_qs"]);
    }

    if (exam.submission_status === "Started" || exam.submission_status === "Registered") {
        if (exam.enable_video_proctoring) {
            startRecording();
        }
    }
    if (exam.submission_status === "Started") {
        // Add event listener for window unload (close)
        window.addEventListener('beforeunload', function (e) {
            sendMessage("Window closed", "Warning", "tabchange");
        });
        // Check if the navbar does not already have the class 'hidden'
        var $navbar = $('.navbar');
        if (!$navbar.hasClass('hidden')) {
            $navbar.addClass('hidden');
        }
        // Start the countdown timer
        updateTimer();
        activateDetector();
    }

    $("#nextQs").click((e) => {
        e.preventDefault();
        // submit the current answer, then load next one
        submitAnswer(true);

    });

    $("#finish").click((e) => {
        e.preventDefault();
        // submit the current answer
        submitAnswer(true);
    });

    $("#submitTopBtn").click((e) => {
        e.preventDefault();
        showSubmitConfirmPage();
    });

    // frappe.realtime.on('newcandidatemsg', (data) => {
    //     convertedTime = timeAgo(data.creation);
    //     addChatBubble(convertedTime, data.message, data.type_of_message)
    // });

    setInterval(function () {
        updateMessages(exam["exam_submission"]);
    }, 3000); // 3 seconds

    // Attach event listener for all inputs with names starting with "qs_"
    $(document).on('change', 'input[name^="qs_"]', function () {
        submitAnswer();
    });

    // Attach event listener for the "markedForLater" checkbox
    $(document).on('change', '#markedForLater', function() {
        // Only auto-submit for multiple choice questions
        if (currentQuestion && currentQuestion["type"] == "Choices") {
            submitAnswer();
        }
    });

    // Global updater for chat bubble timestamps
    setInterval(function() {
        $(".chat-time").each(function() {
            var ts = $(this).data("timestamp");
            $(this).text(timeAgo(ts));
        });
    }, 60000); // update every minute


});



function updateOverviewMap() {
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.exam_overview",
        args: {
            "exam_submission": exam.exam_submission,
        },
        success: (data) => {
            examOverview = data.message;
            // if this is the lastQs, change button
            if (currentQuestion) {
                if (currentQuestion["no"] === examOverview["total_questions"]) {
                    $('#nextQs').hide();
                    $('#finish').show();
                } else {
                    $('#nextQs').show();
                    $('#finish').hide();
                }
            }

            if (currentQuestion) {
            document.getElementById("answeredCount").innerHTML = data.message.total_answered.toString().padStart(2, '0');
            // document.getElementById("notattempted").innerHTML = data.message.total_not_attempted;
            document.getElementById("markedForLaterCount").innerHTML = data.message.total_marked_for_later.toString().padStart(2, '0');
            }
            $("#question-length").text(data.message.total_questions);

            // populate buttons
            if (data.message.total_questions != 0) {
                $("#button-grid").html('');
            }
            for (let i = 1; i <= data.message.total_questions; i++) {
                let btnCls = "btn btn-sm btn-outline-secondary d-flex align-items-center justify-content-between rounded-pill";
                let circleColor = "text-grey"; // Default grey for unanswered
                
                // Determine circle color based on question status
                if (data.message.submitted[i] && data.message.submitted[i].marked_for_later) {
                    circleColor = "text-warning"; // Yellow/orange for marked for later
                } else if (data.message.submitted[i] && data.message.submitted[i].answer) {
                    circleColor = "text-info"; // Blue for answered
                }
                
                // If this is the current question, highlight it with custom styling
                if (currentQuestion && i === currentQuestion["no"]) {
                    btnCls = "btn btn-sm btn-outline-dark d-flex align-items-center justify-content-between rounded-pill current-question-btn";
                    circleColor = "text-grey";
                }
                
                // Create a new button
                const button = $("<button></button>");
                button.addClass(btnCls);
                button.attr("id", "button-" + i);
                
                // Set the button content with the new structure
                button.html(`<i class="bi bi-circle-fill ${circleColor}"></i><span class="fw-bold text-dark">${i}</span>`);
                
                // Append the button to the grid
                $("#button-grid").append(button);
                
                // Add click event handler
                button.click((e) => {
                    navigateToQuestion(i);
                });
            }
        },
    });
};

// Function to handle navigation to a specific question via navigation cards
function navigateToQuestion(qsno) {
    // Clear any pending textarea submission timeout
    clearTimeout(submitAnswerTimeout);
    
    // Check if we're currently on a question and it's a subjective question
    if (currentQuestion && currentQuestion["type"] !== "Choices") {
        // For subjective questions, check if there's content in the textarea
        let textContent = $("#examTextInput").find("textarea").val();
        let mrkForLtr = $("#markedForLater").prop('checked');
        
        // Submit if there's meaningful content or if marked for later
        if ((textContent && textContent.trim() !== "") || mrkForLtr) {
            // Submit the current subjective answer before navigating
            frappe.call({
                method: "exampro.exam_pro.doctype.exam_submission.exam_submission.submit_question_response",
                type: "POST",
                async: false, // Use synchronous call to ensure submission completes before navigation
                args: {
                    'exam_submission': exam["exam_submission"],
                    'qs_name': currentQuestion["name"],
                    'qs_no': currentQuestion["no"],
                    'answer': textContent,
                    'markdflater': mrkForLtr ? 1 : 0,
                },
                callback: (data) => {
                    console.log("Submitted subjective answer before navigation.");
                    // Now navigate to the new question
                    getQuestion(qsno);
                },
                error: (error) => {
                    console.error("Error submitting answer before navigation:", error);
                    // Still navigate even if submission failed
                    getQuestion(qsno);
                }
            });
        } else {
            // No content to submit, just navigate
            getQuestion(qsno);
        }
    } else if (currentQuestion && currentQuestion["type"] == "Choices") {
        // For multiple choice questions, use the existing auto-submit logic
        submitAnswer(false);
        getQuestion(qsno);
    } else {
        // No current question, just navigate
        getQuestion(qsno);
    }
}

// Helper function to format image source (handles both URL and base64)
function getImageSrc(imageData) {
    if (!imageData) return null;
    
    try {
        // Check if it's already a data URL (base64)
        if (imageData.startsWith('data:')) {
            return imageData;
        }
        
        // Check if it's base64 without data URL prefix
        if (imageData.match(/^[A-Za-z0-9+/=]+$/)) {
            // Validate base64 by attempting to decode it
            atob(imageData);
            return `data:image/jpeg;base64,${imageData}`;
        }
        
        // Assume it's a regular URL
        return imageData;
    } catch (error) {
        console.warn('Invalid image data:', error);
        return null;
    }
}

function displayQuestion(current_qs) {
    // $("#quiz-form").fadeOut(300);
    currentQuestion = {
        "exam": exam.name,
        "no": current_qs.qs_no,
        "name": current_qs.name,
        "key": exam.name + "_question_" + current_qs.qs_no,
        "multiple": current_qs.multiple,
        "type": current_qs.type,
        "question": current_qs.question,
        "description_image": current_qs.description_image,
        "option_1": current_qs.option_1,
        "option_2": current_qs.option_2,
        "option_3": current_qs.option_3,
        "option_4": current_qs.option_4,
        "option_1_image": current_qs.option_1_image,
        "option_2_image": current_qs.option_2_image,
        "option_3_image": current_qs.option_3_image,
        "option_4_image": current_qs.option_4_image,
        "answer": current_qs.answer || '',
        "marked_for_later": current_qs.marked_for_later,
        "help_show": current_qs.help_show || "Do not show",
        "help_text": current_qs.help_text || "",
        "help_minimum_reading_time": current_qs.help_minimum_reading_time || 0,
        "help_quiz": current_qs.help_quiz || []
    }

    // Reset help-shown tracking for this question on every visit so navigating
    // away and back (or clicking the question in the navigator) replays the help.
    helpShownFor.delete(currentQuestion.no);

    // Pre-question help: show before revealing the question.
    if (
        currentQuestion.help_show === "Before question" &&
        currentQuestion.help_text
    ) {
        showHelpFlow(currentQuestion, function () {
            renderCurrentQuestion();
        });
        return;
    }

    renderCurrentQuestion();
}

function renderCurrentQuestion() {
    // Hide help panels in case they were visible.
    $("#help-panel").addClass("hide");
    $("#help-quiz-panel").addClass("hide");

    $("#quiz-form").removeClass("hide");
    $("#current-question").text(currentQuestion["no"])
    $('#markedForLater').prop("checked", false);

    // Set question attributes
    $('#question').attr({
        'data-name': currentQuestion["name"],
        'data-type': currentQuestion["type"],
        'data-multi': currentQuestion["multiple"]
    });

    // Set question number and instruction
    let instruction;
    if (currentQuestion["type"] == "Choices" && currentQuestion["multiple"]) {
        instruction = "Choose all answers that apply";
    } else if (currentQuestion["type"] == "Choices") {
        instruction = "Choose one answer";
    } else {
        instruction = "Enter the correct answer";
    }
    $('#question-number').html(`<span class="question-number-text">Question ${currentQuestion["no"]}</span> <span class="question-instruction">${instruction}</span>`);
    $('#current-question-number').text(`Question ${currentQuestion["no"]}`);

    // Set question text with description image
    $('#question-text').html('');
    
    // Create question content with optional description image
    let questionContentHtml = `<div class="question-content">
        <div class="question-text-content">${currentQuestion["question"]}</div>`;
    
    if (currentQuestion["description_image"]) {
        const imageSrc = getImageSrc(currentQuestion["description_image"]);
        if (imageSrc) {
            questionContentHtml += `
            <div class="question-description-image mt-3">
                <img src="${imageSrc}" class="img-fluid" alt="Question description image" 
                     style="max-width: 70%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"
                     onerror="this.style.display='none'; console.warn('Failed to load question description image');">
            </div>`;
        }
    }
    
    questionContentHtml += `</div>`;
    $('#question-text').append(questionContentHtml);

    // Populate choices or show input based on question type
    if (currentQuestion["type"] === "Choices") {
        let valuesToMatch = currentQuestion["answer"].split(','); // Extract numeric part
        $('#choices').show();
        $('#text-input').hide();

        let options = {
            "option_1": currentQuestion["option_1"],
            "option_2": currentQuestion["option_2"],
            "option_3": currentQuestion["option_3"],
            "option_4": currentQuestion["option_4"],
        }
        let choicesHtml = '';

        $.each(options, function (key, value) {
            if (value) {
                let inputType = currentQuestion["multiple"] ? 'checkbox' : 'radio';
                let explanation = currentQuestion[`explanation_${key}`];
                let explanationHtml = explanation ? `<small class="explanation ml-10">${explanation}</small>` : '';
                let checked = '';
                let optImg = currentQuestion[key + "_image"]
                if (valuesToMatch.includes(key.split("_")[1])) {
                    checked = "checked"
                }

                let optImgHtml = '';
                if (optImg) {
                    const imageSrc = getImageSrc(optImg);
                    if (imageSrc) {
                        optImgHtml = `
                        <div class="option-image mt-2">
                            <img src="${imageSrc}" class="img-fluid" alt="Option image" 
                                 style="max-width: 200px; height: auto; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.1);"
                                 onerror="this.style.display='none'; console.warn('Failed to load option image');">
                        </div>`;
                    }
                }
                
                choicesHtml += `
                    <label for="option_${currentQuestion["key"]}_${key}" class="w-100 mb-0" style="cursor: pointer;">
                        <div class="option-item ${checked ? 'selected' : ''}" style="border: 1px solid #dee2e6; border-radius: 8px; padding: 12px; margin-bottom: 8px; transition: all 0.2s ease;">
                            <div class="d-flex align-items-start">
                                <input class="option me-2 mt-1" value="${key}" type="${inputType}" name="qs_${currentQuestion["key"]}" ${checked} id="option_${currentQuestion["key"]}_${key}" style="margin-top: 2px;">
                                <div class="option-content flex-grow-1">
                                    <div class="option-text mb-0">${value}</div>
                                    ${optImgHtml}
                                    ${explanationHtml}
                                </div>
                            </div>
                        </div>
                    </label>`;
            }
        });
        if (currentQuestion["marked_for_later"]) {
            $('#markedForLater').prop("checked", true);
        }
        $('#examTextInput').hide();
        $('#choices').html('');
        $('#choices').append(choicesHtml);
        
        // Add event handler to update selected class
        $('.option').on('change', function() {
            if (currentQuestion["multiple"]) {
                // For checkboxes (multiple choice)
                const optionItem = $(this).closest('.option-item');
                if ($(this).is(':checked')) {
                    optionItem.addClass('selected').css({
                        'background-color': '#e3f2fd',
                        'border-color': '#2196f3',
                        'box-shadow': '0 2px 8px rgba(33, 150, 243, 0.2)'
                    });
                } else {
                    optionItem.removeClass('selected').css({
                        'background-color': '',
                        'border-color': '#dee2e6',
                        'box-shadow': '0 1px 4px rgba(0,0,0,0.1)'
                    });
                }
            } else {
                // For radio buttons (single choice)
                $('.option-item').removeClass('selected').css({
                    'background-color': '',
                    'border-color': '#dee2e6',
                    'box-shadow': '0 1px 4px rgba(0,0,0,0.1)'
                });
                $(this).closest('.option-item').addClass('selected').css({
                    'background-color': '#e3f2fd',
                    'border-color': '#2196f3',
                    'box-shadow': '0 2px 8px rgba(33, 150, 243, 0.2)'
                });
            }
        });
        
        // Apply initial styling for pre-selected options
        $('.option:checked').each(function() {
            $(this).closest('.option-item').addClass('selected').css({
                'background-color': '#e3f2fd',
                'border-color': '#2196f3',
                'box-shadow': '0 2px 8px rgba(33, 150, 243, 0.2)'
            });
        });
        
        // Add hover effects for better UX
        $('.option-item').hover(
            function() {
                if (!$(this).hasClass('selected')) {
                    $(this).css({
                        'background-color': '#f8f9fa',
                        'border-color': '#adb5bd'
                    });
                }
            },
            function() {
                if (!$(this).hasClass('selected')) {
                    $(this).css({
                        'background-color': '',
                        'border-color': '#dee2e6'
                    });
                }
            }
        );

    } else {
        $('#choices').hide();
        $('#examTextInput').show();
        var inputTextArea = $("#examTextInput").find("textarea");
        inputTextArea.val(currentQuestion["answer"]);
        
        // Restore marked for later state for subjective questions
        if (currentQuestion["marked_for_later"]) {
            $('#markedForLater').prop("checked", true);
        }
    }

};

function sendMessage(message, messageType, warningType) {
    if (currentQsNo > 1) {
        frappe.call({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.post_exam_message",
            type: "POST",
            args: {
                'exam_submission': exam["exam_submission"],
                'message': message,
                'type_of_message': messageType,
                'warning_type': warningType,
                'from': "Candidate"
            },
            callback: (data) => {
                console.log(data);
            },
        });
    }
}

function sendChatMessage() {
    var message = $('#chat-input').val().trim();
    if(message) {
        frappe.call({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.post_exam_message",
            type: "POST",
            args: {
                'exam_submission': exam["exam_submission"],
                'message': message,
                'type_of_message': 'General',
                'warning_type': '',
            },
            callback: (data) => {
                $('#chat-input').val('');
                updateMessages(exam.exam_submission);
            },
        });
    }
}

function startNoFaceCountdown() {
    if (noFaceTerminationTimer) return; // already counting down
    let secondsLeft = NO_FACE_GRACE_SECONDS;
    showNoFaceCountdownBanner(secondsLeft);
    noFaceCountdownInterval = setInterval(() => {
        secondsLeft -= 1;
        if (secondsLeft >= 0) {
            showNoFaceCountdownBanner(secondsLeft);
        }
    }, 1000);
    noFaceTerminationTimer = setTimeout(() => {
        clearInterval(noFaceCountdownInterval);
        noFaceCountdownInterval = null;
        noFaceTerminationTimer = null;
        terminateForNoFace();
    }, NO_FACE_GRACE_SECONDS * 1000);
}

function cancelNoFaceCountdown() {
    if (noFaceTerminationTimer) {
        clearTimeout(noFaceTerminationTimer);
        noFaceTerminationTimer = null;
    }
    if (noFaceCountdownInterval) {
        clearInterval(noFaceCountdownInterval);
        noFaceCountdownInterval = null;
    }
    hideNoFaceCountdownBanner();
}

function showNoFaceCountdownBanner(secondsLeft) {
    const banner = document.getElementById('noFaceBanner');
    if (!banner) return;
    banner.style.display = 'block';
    const countdownEl = document.getElementById('noFaceCountdown');
    if (countdownEl) countdownEl.textContent = secondsLeft;
}

function hideNoFaceCountdownBanner() {
    const banner = document.getElementById('noFaceBanner');
    if (banner) banner.style.display = 'none';
}

function terminateForNoFace() {
    if (examEnded) return;
    examEnded = true;
    cancelNoFaceCountdown();

    // Post directly: sendMessage() guards on currentQsNo > 1 which can be false
    // immediately after start. We need this critical message to always reach the server.
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.post_exam_message",
        type: "POST",
        args: {
            'exam_submission': exam["exam_submission"],
            'message': 'Exam terminated: face not visible to camera for 60 seconds.',
            'type_of_message': 'Critical',
            'warning_type': 'nofacetimeout',
        },
        callback: () => {
            stopRecording();
            if (detector) detector.destroy();
            window.location.href = "/exam/" + exam.exam_submission;
        },
        error: (error) => {
            console.error("Failed to post nofacetimeout:", error);
            window.location.href = "/exam/" + exam.exam_submission;
        }
    });
}

function endExam(isAutoSubmit) {
    if (!examEnded) {
        frappe.call({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.end_exam",
            type: "POST",
            args: {
                "exam_submission": exam["exam_submission"],
            },
            callback: (data) => {
                examEnded = true;
                stopRecording();
                if (detector) {
                    detector.destroy();
                }
                if (isAutoSubmit) {
                    window.location.href = "/exam?auto_submitted=1&submission=" + encodeURIComponent(exam.exam_submission);
                } else {
                    window.location.href = "/exam/" + exam.exam_submission;
                }
            }
        });
    }
};

function startExam() {
    // Check if media permissions are granted before starting exam (only if video proctoring is enabled)
    if (typeof checkMediaPermissionsBeforeStart === 'function' && !checkMediaPermissionsBeforeStart()) {
        return; // Don't start exam if permissions not granted
    }
    
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.start_exam",
        type: "POST",
        args: {
            "exam_submission": exam["exam_submission"],
        },
        callback: (data) => {
            // Update the exam end_time with the value returned from the server
            if (data.message && data.message.end_time) {
                exam.end_time = data.message.end_time;
            }
            
            $("#quiz-form").removeClass("hide");
            // getQuestion(1);
            // updateTimer();
            location.reload();
        }
    });
};

function getQuestion(qsno) {
    // Clear any pending textarea submission timeout
    clearTimeout(submitAnswerTimeout);
    // Callers (Next click, navigateToQuestion, subjective branches) save the
    // current answer before invoking getQuestion, so no save is done here.
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.get_question",
        type: "POST",
        args: {
            "exam_submission": exam["exam_submission"],
            "qsno": qsno,
        },
        callback: (data) => {
            // Hide exam summary and show quiz form
            $("#exam-summary").addClass("hide");
            $("#quiz-form").removeClass("hide");
            displayQuestion(data.message);
            currentQsNo = data.message.qs_no;
            updateOverviewMap();
        }
    });
};

function showSubmitConfirmPage() {
        // Clear any pending textarea submission timeout
        clearTimeout(submitAnswerTimeout);
        
        // Submit the current answer before showing the summary only for multiple choice questions
        if (currentQuestion && currentQuestion["type"] == "Choices") {
            submitAnswer(false);
        }
        
        // user wants to end the exam
        // Need to fetch the latest overview data to reflect changes from the last question
        frappe.call({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.exam_overview",
            args: {
                "exam_submission": exam.exam_submission,
            },
            async: false, // Use synchronous call to ensure we have updated data before displaying
            success: (data) => {
                examOverview = data.message;
                
                $("#exam-summary").removeClass("hide");
                $("#quiz-form").addClass("hide");

                $("#quiz-title").html();
                $('#quiz-box').removeClass("text-center");
                let messageHtml = `
                    <div class="d-flex justify-content-center">
                    <div class="card" style="max-width: 30rem;">
                        <div class="card-body">
                        <div class="d-flex align-items-center mb-3">
                            <i class="bi bi-clock me-2"></i>
                            <h6 class="mb-0">Time Remaining: <span class="ml-10 timer">--:--</span></h6>
                        </div>
                        <ul class="list-group list-group-flush">
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span class="mr-10">Total Questions</span>
                            <span>${examOverview.total_questions}</span>
                            </li>
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span class="mr-10">Total Answered</span>
                            <span>${examOverview.total_answered}</span>
                            </li>
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span class="mr-10">Marked for Review</span>
                            <span>${examOverview.total_marked_for_later}</span>
                            </li>
                        </ul>
                        </div>
                        <div class="card-footer">
                        <button class="btn btn-primary w-100" id="quizSubmit" onClick=endExam();>Submit Exam</button>
                        </div>
                    </div>
                    </div>
                    `
                $("#quiz-box").html(messageHtml);
            }
        });
}


function submitAnswer(loadNext) {
    // If a save is already in flight, drop this call. If the dropped call was a
    // Next/Finish click, remember it so the in-flight callback navigates after
    // the save resolves — preserves ordering without using deprecated sync XHR.
    if (isSubmittingAnswer) {
        if (loadNext) {
            pendingNavigation = true;
        }
        return;
    }

    let answer;
    var mrkForLtr = $("#markedForLater").prop('checked') ? 1 : 0;
    if (currentQuestion["type"] == "Choices") {
        let checkedValues = [];
        $("[name='" + "qs_" + currentQuestion["key"] + "']:checked").each(function () {
            const numericValue = $(this).val().split("_")[1];
            checkedValues.push(numericValue);
        });

        answer = checkedValues.join(",");
    } else {
        answer = $("#examTextInput").find("textarea").val();
        // For subjective questions, only submit when explicitly navigating (loadNext = true)
        // or when marked for later, but not for auto-save
        if (!loadNext && !mrkForLtr) {
            // Don't auto-save subjective answers unless marked for later
            return;
        }

        // When navigating (loadNext = true), handle empty subjective answers
        if (loadNext && !mrkForLtr && (!answer || answer.trim() === "")) {
            // Don't submit empty subjective answers when navigating, just load next question
            if (currentQuestion["no"] < examOverview["total_questions"]) {
                let nextQs = currentQuestion["no"] + 1;
                getQuestion(nextQs);
                updateOverviewMap();
            } else {
                showSubmitConfirmPage();
            }
            return;
        }
    }

    isSubmittingAnswer = true;
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.submit_question_response",
        type: "POST",
        args: {
            'exam_submission': exam["exam_submission"],
            'qs_name': currentQuestion["name"],
            'qs_no': currentQuestion["no"],
            'answer': answer,
            'markdflater': mrkForLtr,
        },
        callback: (data) => {
            isSubmittingAnswer = false;

            const shouldNavigate = loadNext || pendingNavigation;
            pendingNavigation = false;

            // If the user has manually moved to a different question while this save
            // was in flight (e.g. clicked a question button), don't override their
            // choice with a forced "next".
            const userStillOnSavedQs = currentQuestion && currentQuestion["no"] === data.message.qs_no;

            if (shouldNavigate && userStillOnSavedQs) {
                const advance = () => {
                    if (data.message.qs_no < examOverview["total_questions"]) {
                        let nextQs = data.message.qs_no + 1;
                        getQuestion(nextQs);
                        updateOverviewMap();
                    } else {
                        showSubmitConfirmPage();
                    }
                };

                const helpShow = currentQuestion.help_show;
                const isMCQ = currentQuestion.type === "Choices";
                const isWrong = isMCQ && data.message.is_correct === 0;
                const notMarkedForLater = mrkForLtr !== 1;
                const triggerPostHelp =
                    notMarkedForLater &&
                    !!currentQuestion.help_text &&
                    !helpShownFor.has(currentQuestion.no) &&
                    (helpShow === "After any answer" ||
                        (helpShow === "After wrong answer" && isWrong));

                if (triggerPostHelp) {
                    showHelpFlow(currentQuestion, advance);
                } else {
                    advance();
                }
            }
        },
        error: (error) => {
            console.error("Error submitting answer:", error);
            isSubmittingAnswer = false;
            if (loadNext || pendingNavigation) {
                pendingNavigation = false;
                showNotification("Could not save your answer. Please try again.", "error");
            }
        }
    });
};

function escapeHtml(value) {
    return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function setHelpNavigationLock(locked) {
    $("#navigation-card").toggleClass("help-locked", locked);
    $(".exam-navigation-btn").prop("disabled", locked);
}

function showHelpFlow(qs, onDone) {
    const qsNo = qs.no != null ? qs.no : qs.qs_no;
    helpShownFor.add(qsNo);
    setHelpNavigationLock(true);
    $("#quiz-form").addClass("hide");
    $("#help-quiz-panel").addClass("hide");
    // help_text is editor-authored HTML stored on the question doctype (same
    // trust level as the question body itself).
    $("#help-text-content").html(qs.help_text || "");
    const helpTitle = qs.help_show === "Before question"
        ? "Read before next question"
        : "Learn more about previous question";
    $("#help-panel-title, #help-quiz-panel-title").text(helpTitle);

    const quiz = qs.help_quiz || [];
    const totalSteps = 1 + quiz.length;
    $("#help-panel-step").text(`1/${totalSteps}`);
    $("#help-panel").removeClass("hide");

    const continueBtn = $("#helpContinueBtn");
    continueBtn.off("click").prop("disabled", true);

    startHelpReadingTimer(qs.help_minimum_reading_time || 0, function () {
        continueBtn.prop("disabled", false);
    });

    continueBtn.on("click", function () {
        if (quiz.length === 0) {
            $("#help-panel").addClass("hide");
            setHelpNavigationLock(false);
            onDone();
        } else {
            showHelpQuiz(quiz, totalSteps, onDone);
        }
    });
}

function startHelpReadingTimer(seconds, onComplete) {
    if (helpReadingTimer) {
        clearInterval(helpReadingTimer);
        helpReadingTimer = null;
    }
    const total = Math.max(0, Math.floor(seconds));
    if (total === 0) {
        $("#help-timer-text").text("");
        onComplete();
        return;
    }
    let remaining = total;
    $("#help-timer-text").text(`Please read for ${remaining}s before continuing`);
    helpReadingTimer = setInterval(function () {
        remaining -= 1;
        if (remaining <= 0) {
            clearInterval(helpReadingTimer);
            helpReadingTimer = null;
            $("#help-timer-text").text("");
            onComplete();
        } else {
            $("#help-timer-text").text(`Please read for ${remaining}s before continuing`);
        }
    }, 1000);
}

function showHelpQuiz(quiz, totalSteps, onDone) {
    $("#help-panel").addClass("hide");
    $("#help-quiz-panel").removeClass("hide");

    const submitBtn = $("#helpQuizSubmitBtn");
    const continueBtn = $("#helpQuizContinueBtn");

    let idx = 0;

    function renderRow() {
        $("#help-quiz-panel-step").text(`${idx + 2}/${totalSteps}`);
        const row = quiz[idx];
        let html = `<div class="help-quiz-row" data-correct="${escapeHtml(row.correct_choice)}">`;
        html += `<div class="help-quiz-question">${escapeHtml(row.quiz_question)}</div>`;
        ["1", "2", "3"].forEach(function (n) {
            const choice = row["choice_" + n];
            if (!choice) return;
            html += `<label><input type="radio" name="hq_current" value="${n}"> ${escapeHtml(choice)}</label>`;
        });
        html += `<div class="help-quiz-feedback"></div>`;
        html += `</div>`;
        $("#help-quiz-content").html(html);

        submitBtn.removeClass("hide").prop("disabled", false).off("click").on("click", onSubmit);
        continueBtn.addClass("hide").off("click").on("click", onContinue);
    }

    function onSubmit() {
        const $row = $(".help-quiz-row");
        const correct = String($row.data("correct"));
        const picked = $("input[name='hq_current']:checked").val();
        const fb = $row.find(".help-quiz-feedback");
        fb.removeClass("correct incorrect");
        if (!picked) {
            fb.text("No answer selected.").addClass("incorrect");
            return;
        }
        if (picked === correct) {
            fb.text("Correct.").addClass("correct");
        } else {
            fb.text(`Incorrect. Correct answer: ${correct}.`).addClass("incorrect");
        }
        submitBtn.addClass("hide");
        continueBtn.removeClass("hide");
    }

    function onContinue() {
        idx += 1;
        if (idx >= quiz.length) {
            $("#help-quiz-panel").addClass("hide");
            setHelpNavigationLock(false);
            onDone();
        } else {
            renderRow();
        }
    }

    renderRow();
}
