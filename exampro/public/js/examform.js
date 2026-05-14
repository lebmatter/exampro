var hiddenTime = 0;
var visibleTime = 0;
var examOverview;
var currentQuestion;
var detector;
var gazer;
var lastNoFaceAlertTime = 0;
var noFaceAlertCooldown = 5000;
var lastWebcamErrorTime = 0;
var webcamErrorCooldown = 5000;
var recordingInitialized = false;
var submitAnswerTimeout;
var isSubmittingAnswer = false;
var pendingNavigation = false;
var faceCurrentlyVisible = false;
var noFaceTerminationTimer = null;
var noFaceCountdownInterval = null;
var NO_FACE_GRACE_SECONDS = 60;

// ── VIOLATION SNAPSHOTS ───────────────────────────────────────────────────────
// Initialised inside startRecording() once the webcam stream is live.
var violationSnapshots = null;
// ─────────────────────────────────────────────────────────────────────────────

function showNotification(message, type = 'info') {
    if (typeof toastr !== 'undefined') {
        switch (type) {
            case 'warning': toastr.warning(message); break;
            case 'error':   toastr.error(message);   break;
            case 'success': toastr.success(message); break;
            default:        toastr.info(message);
        }
    } else {
        console.log(`[${type.toUpperCase()}] ${message}`);
        const notification = document.createElement('div');
        notification.style.cssText = `
            position:fixed;top:20px;right:20px;
            background:${type==='error'?'#f44336':type==='warning'?'#ff9800':'#2196f3'};
            color:white;padding:12px 20px;border-radius:4px;z-index:10000;
            font-size:14px;max-width:300px;box-shadow:0 2px 10px rgba(0,0,0,0.2);`;
        notification.textContent = message;
        document.body.appendChild(notification);
        setTimeout(() => { if (notification.parentNode) notification.parentNode.removeChild(notification); }, 5000);
    }
}

// ── FIX BUG 3: Screen-share overlay ──────────────────────────────────────────
// Problem: startExam() calls location.reload() after the exam starts.
// After reload, status is "Started" so startExam() is never called again,
// meaning requestScreenCapture() is never called again, so _screenStream is
// always null and every screen snapshot is empty.
//
// Fix: when the page loads in "Started" state (i.e. after the reload),
// show a full-screen overlay that requires the candidate to click a button.
// That click IS a user gesture, so getDisplayMedia() can be called from it.
// The overlay must be dismissed before the candidate can interact with the exam.
function showScreenShareOverlay() {
    // Don't show if video proctoring is off or overlay already exists
    if (!exam.enable_video_proctoring) return;
    if (document.getElementById('screenShareOverlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'screenShareOverlay';
    overlay.style.cssText = `
        position:fixed;inset:0;z-index:99999;
        background:rgba(15,15,15,0.92);
        display:flex;align-items:center;justify-content:center;
        font-family:inherit;`;

    overlay.innerHTML = `
        <div style="background:#fff;border-radius:12px;padding:40px 48px;max-width:480px;
                    width:90%;text-align:center;box-shadow:0 8px 40px rgba(0,0,0,0.4);">
            <div style="font-size:48px;margin-bottom:16px;">🖥️</div>
            <h3 style="margin:0 0 12px;font-size:1.4rem;color:#1a1a1a;">Screen Monitoring Required</h3>
            <p style="margin:0 0 24px;color:#555;line-height:1.6;">
                This exam requires screen monitoring. When the browser dialog appears,
                select <strong>"Entire Screen"</strong> and click <em>Share</em>.
            </p>
            <button id="screenShareBtn"
                style="background:#1a73e8;color:#fff;border:none;border-radius:8px;
                       padding:14px 32px;font-size:1rem;cursor:pointer;width:100%;
                       font-weight:600;transition:background 0.2s;">
                Enable Screen Monitoring
            </button>
            <p style="margin:16px 0 0;font-size:0.8rem;color:#999;">
                The exam cannot proceed without screen sharing.
            </p>
        </div>`;

    document.body.appendChild(overlay);

    // Button click = user gesture → getDisplayMedia can be called here
    document.getElementById('screenShareBtn').addEventListener('click', async function () {
        this.disabled = true;
        this.textContent = 'Waiting for permission…';

        if (!violationSnapshots) {
            console.warn('[ScreenShare] violationSnapshots not ready yet.');
            this.disabled = false;
            this.textContent = 'Enable Screen Monitoring';
            return;
        }

        const granted = await violationSnapshots.requestScreenCapture();

        if (granted) {
            overlay.remove();
            activateDetector(); // Start detecting tab changes ONLY after screen share is granted
        } else {
            // User cancelled — re-enable button so they can try again
            this.disabled = false;
            this.textContent = 'Try Again';
            const note = overlay.querySelector('p:last-of-type');
            note.style.color = '#d32f2f';
            note.textContent = 'Screen sharing is required. Please click "Try Again" and select "Entire Screen".';
        }
    });
}
// ─────────────────────────────────────────────────────────────────────────────

function updateTimer() {
    if (!examEnded) {
        var remainingTime = new Date(exam.end_time) - new Date().getTime();
        if (remainingTime <= 0) {
            document.getElementById("exam-timer").innerHTML = "00:00";
            examAlert("Time's Up!", "Your exam time has expired. Click OK to proceed.");
            endExam(true);
            return;
        }
        var minutes = Math.floor((remainingTime % (1000 * 60 * 60)) / (1000 * 60));
        var seconds = Math.floor((remainingTime % (1000 * 60)) / 1000);
        if (remainingTime > (1000 * 60 * 60)) {
            var hours = Math.floor(remainingTime / (1000 * 60 * 60));
            $(".timer").text(`${hours.toString().padStart(2,'0')}:${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`);
        } else {
            $(".timer").text(`${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`);
        }
        setTimeout(updateTimer, 1000);
    }
}

const answrdCheck = `<i class="bi bi-check-circle"></i>`;
const answrLater  = `<i class="bi bi-clock-history"></i>`;
var examEnded  = false;
var currentQsNo = 1;
let recorder;
let stream;
let recordingStream;
let recordingInterval;

function sendVideoBlob(blob) {
    let xhr = new XMLHttpRequest();
    const unixTimestamp = Math.floor(Date.now() / 1000);
    xhr.open('POST', '/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.upload_video', true);
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);
    let form_data = new FormData();
    form_data.append('file', blob, unixTimestamp + ".webm");
    form_data.append('exam_submission', exam["exam_submission"]);
    xhr.send(form_data);
}

function startRecording() {
    if (recordingInitialized) {
        console.log('Recording already initialized');
        return;
    }
    recordingInitialized = true;

    navigator.mediaDevices.getUserMedia({ audio: false, video: true })
        .then(function (mediaStream) {
            stream = mediaStream;
            recordingStream = stream.clone();

            stream.getTracks().forEach(track => {
                track.addEventListener('ended', function () {
                    const currentTime = Date.now();
                    if (currentTime - lastWebcamErrorTime > webcamErrorCooldown) {
                        console.error('Webcam was disabled or stopped');
                        sendMessage('Webcam was disabled or stopped', 'Warning', 'nowebcam');
                        lastWebcamErrorTime = currentTime;
                        showNotification('Webcam was disabled or stopped. Please fix the issue.', 'error');
                    }
                });
            });

            const videoElement = document.getElementById('webcam-stream');
            videoElement.srcObject  = stream;
            videoElement.muted      = true;
            videoElement.playsInline = true;

            const playVideo = () => {
                videoElement.play().catch(error => {
                    console.warn('Video autoplay prevented:', error);
                });
            };
            playVideo();

            const startVideoOnInteraction = () => {
                playVideo();
                document.removeEventListener('click',   startVideoOnInteraction);
                document.removeEventListener('keydown', startVideoOnInteraction);
            };
            document.addEventListener('click',   startVideoOnInteraction, { once: true });
            document.addEventListener('keydown', startVideoOnInteraction, { once: true });

            // ── Initialise ViolationSnapshotManager ───────────────────────────
            // Must come AFTER the video element has the stream attached so that
            // _captureWebcam() can draw from a live frame.
            if (exam.enable_video_proctoring && !violationSnapshots) {
                try {
                    violationSnapshots = new ViolationSnapshotManager({
                        examSubmission:      exam['exam_submission'],
                        webcamElementId:     'webcam-stream',
                        onSnapshotCaptured:  (type, urls) => {
                            console.log(`[Proctoring] Snapshot saved — type: ${type}`, urls);
                        },
                        onSnapshotError:     (type, err) => {
                            console.warn(`[Proctoring] Snapshot failed — type: ${type}`, err);
                        },
                        onScreenShareGranted: () => {
                            console.log('[Proctoring] Screen share active.');
                        },
                        onScreenShareDenied: () => {
                            console.warn('[Proctoring] Screen share denied.');
                        },
                    });
                } catch (e) {
                    console.error('[Proctoring] Could not initialise ViolationSnapshotManager:', e);
                    violationSnapshots = null;
                }
            }

            // ── FIX BUG 3: Show screen-share overlay on "Started" page load ──
            // When the page reloads after startExam(), status is "Started".
            // startExam() is never called again, so requestScreenCapture() would
            // never be invoked. The overlay forces a user-gesture click here.
            if (exam.enable_video_proctoring && exam.submission_status === 'Started') {
                // Small delay so the webcam feed renders first — better UX
                setTimeout(showScreenShareOverlay, 800);
            }
            // ─────────────────────────────────────────────────────────────────

            // Initialise Gazer
            if (exam.enable_video_proctoring && !gazer) {
                try {
                    gazer = new Gazer("webcam-stream", {
                        postTrackingDataInterval: 15,
                        showFaceRectangle: false,
                        showGazeVector:    false,
                        showEyePoints:     false,
                        enableLogs:        false,

                        onFaceDetected: (faces) => {
                            const currentTime = Date.now();
                            if (faces.length === 1) {
                                faceCurrentlyVisible = true;
                                cancelNoFaceCountdown();

                            } else if (faces.length === 0) {
                                faceCurrentlyVisible = false;

                                // ── FIX BUG 5: snapshot guard is separate from alert cooldown ──
                                // Previously both shared lastNoFaceAlertTime, causing snapshots
                                // to be silently skipped whenever the alert cooldown was active.
                                if (violationSnapshots && exam.submission_status === 'Started' && !examEnded) {
                                    violationSnapshots.capture('noface', 'No face detected in webcam.');
                                }

                                if (exam.submission_status === "Started" && !examEnded) {
                                    startNoFaceCountdown();
                                }

                            } else {
                                // faces.length > 1 — multiple people
                                faceCurrentlyVisible = true;
                                cancelNoFaceCountdown();

                                if (violationSnapshots && exam.submission_status === 'Started' && !examEnded) {
                                    violationSnapshots.capture(
                                        'multiplefaces',
                                        `${faces.length} faces detected in webcam.`
                                    );
                                }
                            }
                        },

                        onGazeChange: (gazeState, gazeData) => {
                            if (gazeState === 'away' &&
                                exam.submission_status === 'Started' &&
                                !examEnded &&
                                violationSnapshots) {
                                violationSnapshots.capture(
                                    'gazeaway',
                                    'Candidate gaze directed away from the screen.'
                                );
                            }
                        },

                        onPostTrackingData: (trackingData) => {
                            if (exam.submission_status !== "Started") return;
                            frappe.call({
                                method: "exampro.exam_pro.doctype.exam_submission.exam_submission.post_tracking_info",
                                type: "POST",
                                args: {
                                    'info': JSON.stringify({
                                        'exam_submission':     exam["exam_submission"],
                                        'faceCountChanges':    trackingData.faceCountChanges,
                                        'totalAwayTime':       trackingData.totalAwayTime,
                                        'totalDistractedTime': trackingData.totalDistractedTime,
                                        'retinaLocations':     trackingData.retinaLocations || []
                                    })
                                },
                                callback: (data) => {},
                                error:    (error) => { console.error("Failed to send tracking data:", error); }
                            });
                        },

                        onError: (error) => {
                            console.error("Gazer error:", error);
                        }
                    });

                    gazer.setPerformanceMode('low');
                    gazer.setSensitivityMode('relaxed');

                    if (exam.submission_status === "Started" || exam.submission_status === "Registered") {
                        gazer.start();
                    }
                } catch (error) {
                    console.error("Failed to initialize gazer:", error);
                    gazer = null;
                }
            }

            if (exam["submission_status"] === "Started") {
                recorder = RecordRTC(recordingStream, {
                    type:             'video',
                    mimeType:         'video/webm',
                    videoBitsPerSecond: 8000,
                    disableLogs:       true
                });
                recorder.startRecording();

                recordingInterval = setInterval(function () {
                    recorder.stopRecording(function () {
                        let blob = recorder.getBlob();
                        sendVideoBlob(blob);
                        recorder = RecordRTC(recordingStream, { type: 'video', disableLogs: true });
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
                showNotification('No webcam detected. Please check your camera permissions.', 'error');
            }
            recordingInitialized = false;
        });
}

function stopRecording() {
    clearInterval(recordingInterval);
    if (recorder) {
        recorder.stopRecording(function () {
            if (stream)          stream.getTracks().forEach(t => t.stop());
            if (recordingStream) recordingStream.getTracks().forEach(t => t.stop());
        });
    } else {
        if (stream)          stream.getTracks().forEach(t => t.stop());
        if (recordingStream) recordingStream.getTracks().forEach(t => t.stop());
    }
    recordingInitialized = false;
}

function activateDetector() {
    if (!detector) {
        detector = new InactivityDetector({
            warningThreshold: 1,

            // Fires the instant the page is hidden / window loses focus.
            // The webcam still has the last live frame at this moment.
            onInactivityStart: () => {
                if (violationSnapshots && exam.submission_status === 'Started' && !examEnded) {
                    violationSnapshots.capture(
                        'tabchange',
                        'Candidate switched away from the exam tab or window.'
                    );
                }
            },

            onInactive: (inactiveStr, secondsInactive) => {
                tabChangeStr = `Tab changed detected for ${secondsInactive} seconds.`;
                console.log(tabChangeStr);

                // Secondary capture on return — queued separately so both
                // the departure and return moments are recorded.
                if (violationSnapshots && exam.submission_status === 'Started' && !examEnded) {
                    violationSnapshots.capture(
                        'tabchange',
                        `Candidate was away for ${secondsInactive}s. Reason: ${inactiveStr}`
                    );
                }
            },

            onActive: () => {
                console.log("User active again");
            },

            onMonitorChange: (lastScreens, currentScreens) => {
                monitorChangeStr = `Monitor changed from ${lastScreens} to ${currentScreens}`;
                console.log(monitorChangeStr);

                if (violationSnapshots && exam.submission_status === 'Started' && !examEnded) {
                    violationSnapshots.capture(
                        'monitorchange',
                        `Monitor configuration changed: ${lastScreens} → ${currentScreens}.`
                    );
                }
            }
        });
        detector.init();
    }
}

frappe.ready(() => {
    updateOverviewMap();

    document.addEventListener('contextmenu', e => e.preventDefault());
    document.addEventListener('selectstart', e => e.preventDefault());
    document.addEventListener('copy',        e => e.preventDefault());

    document.addEventListener('keydown', function (e) {
        if (e.key === 'PrintScreen')                         { e.preventDefault(); alert('Screenshots are disabled!'); }
        if (e.ctrlKey && e.shiftKey && e.key === 'S')        { e.preventDefault(); alert('Screenshots are disabled!'); }
        if (e.metaKey && e.shiftKey && e.key === '4')        { e.preventDefault(); alert('Screenshots are disabled!'); }
        if (e.ctrlKey && e.key === 'P')                      { e.preventDefault(); alert('Printing is disabled!'); }
    });

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
        getQuestion(exam["current_qs"]);
    }

    if (exam.submission_status === "Started" || exam.submission_status === "Registered") {
        if (exam.enable_video_proctoring) {
            startRecording();
        }
    }

    if (exam.submission_status === "Started") {
        window.addEventListener('beforeunload', function (e) {
            // Log it if needed, but snapshots aren't possible here.
            // sendMessage("Window closed", "Warning", "tabchange");
        });
        var $navbar = $('.navbar');
        if (!$navbar.hasClass('hidden')) $navbar.addClass('hidden');
        updateTimer();
        
        // Only activate detector immediately if video proctoring is OFF.
        // If ON, it will be activated after screen share is granted in showScreenShareOverlay.
        if (!exam.enable_video_proctoring) {
            activateDetector();
        }
    }

    $("#nextQs").click((e) => { e.preventDefault(); submitAnswer(true); });
    $("#finish").click((e)  => { e.preventDefault(); submitAnswer(true); });
    $("#submitTopBtn").click((e) => { e.preventDefault(); showSubmitConfirmPage(); });

    setInterval(function () { updateMessages(exam["exam_submission"]); }, 3000);

    $(document).on('change', 'input[name^="qs_"]', function () { submitAnswer(); });

    $(document).on('change', '#markedForLater', function () {
        if (currentQuestion && currentQuestion["type"] == "Choices") submitAnswer();
    });

    setInterval(function () {
        $(".chat-time").each(function () {
            var ts = $(this).data("timestamp");
            $(this).text(timeAgo(ts));
        });
    }, 60000);
});


function updateOverviewMap() {
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.exam_overview",
        args: { "exam_submission": exam.exam_submission },
        success: (data) => {
            examOverview = data.message;
            if (currentQuestion) {
                if (currentQuestion["no"] === examOverview["total_questions"]) {
                    $('#nextQs').hide(); $('#finish').show();
                } else {
                    $('#nextQs').show(); $('#finish').hide();
                }
                document.getElementById("answeredCount").innerHTML     = data.message.total_answered.toString().padStart(2,'0');
                document.getElementById("markedForLaterCount").innerHTML = data.message.total_marked_for_later.toString().padStart(2,'0');
            }
            $("#question-length").text(data.message.total_questions);

            if (data.message.total_questions != 0) $("#button-grid").html('');

            for (let i = 1; i <= data.message.total_questions; i++) {
                let btnCls     = "btn btn-sm btn-outline-secondary d-flex align-items-center justify-content-between rounded-pill";
                let circleColor = "text-grey";

                if (data.message.submitted[i] && data.message.submitted[i].marked_for_later) {
                    circleColor = "text-warning";
                } else if (data.message.submitted[i] && data.message.submitted[i].answer) {
                    circleColor = "text-info";
                }

                if (currentQuestion && i === currentQuestion["no"]) {
                    btnCls      = "btn btn-sm btn-outline-dark d-flex align-items-center justify-content-between rounded-pill current-question-btn";
                    circleColor = "text-grey";
                }

                const button = $("<button></button>");
                button.addClass(btnCls).attr("id", "button-" + i);
                button.html(`<i class="bi bi-circle-fill ${circleColor}"></i><span class="fw-bold text-dark">${i}</span>`);
                $("#button-grid").append(button);
                button.click((e) => { navigateToQuestion(i); });
            }
        },
    });
}

function navigateToQuestion(qsno) {
    clearTimeout(submitAnswerTimeout);

    if (currentQuestion && currentQuestion["type"] !== "Choices") {
        let textContent = $("#examTextInput").find("textarea").val();
        let mrkForLtr   = $("#markedForLater").prop('checked');

        if ((textContent && textContent.trim() !== "") || mrkForLtr) {
            frappe.call({
                method: "exampro.exam_pro.doctype.exam_submission.exam_submission.submit_question_response",
                type:   "POST",
                async:  false,
                args: {
                    'exam_submission': exam["exam_submission"],
                    'qs_name':  currentQuestion["name"],
                    'qs_no':    currentQuestion["no"],
                    'answer':   textContent,
                    'markdflater': mrkForLtr ? 1 : 0,
                },
                callback: (data) => { getQuestion(qsno); },
                error:    (error) => { console.error("Error submitting answer before navigation:", error); getQuestion(qsno); }
            });
        } else {
            getQuestion(qsno);
        }
    } else if (currentQuestion && currentQuestion["type"] == "Choices") {
        submitAnswer(false);
        getQuestion(qsno);
    } else {
        getQuestion(qsno);
    }
}

function getImageSrc(imageData) {
    if (!imageData) return null;
    try {
        if (imageData.startsWith('data:')) return imageData;
        if (imageData.match(/^[A-Za-z0-9+/=]+$/)) { atob(imageData); return `data:image/jpeg;base64,${imageData}`; }
        return imageData;
    } catch (error) {
        console.warn('Invalid image data:', error); return null;
    }
}

function displayQuestion(current_qs) {
    currentQuestion = {
        "exam":              exam.name,
        "no":                current_qs.qs_no,
        "name":              current_qs.name,
        "key":               exam.name + "_question_" + current_qs.qs_no,
        "multiple":          current_qs.multiple,
        "type":              current_qs.type,
        "question":          current_qs.question,
        "description_image": current_qs.description_image,
        "option_1":          current_qs.option_1,
        "option_2":          current_qs.option_2,
        "option_3":          current_qs.option_3,
        "option_4":          current_qs.option_4,
        "option_1_image":    current_qs.option_1_image,
        "option_2_image":    current_qs.option_2_image,
        "option_3_image":    current_qs.option_3_image,
        "option_4_image":    current_qs.option_4_image,
        "answer":            current_qs.answer || '',
        "marked_for_later":  current_qs.marked_for_later
    };

    $("#quiz-form").removeClass("hide");
    $("#current-question").text(currentQuestion["no"]);
    $('#markedForLater').prop("checked", false);

    $('#question').attr({
        'data-name':  currentQuestion["name"],
        'data-type':  currentQuestion["type"],
        'data-multi': currentQuestion["multiple"]
    });

    let instruction;
    if      (currentQuestion["type"] == "Choices" && currentQuestion["multiple"]) instruction = "Choose all answers that apply";
    else if (currentQuestion["type"] == "Choices")                                instruction = "Choose one answer";
    else                                                                           instruction = "Enter the correct answer";

    $('#question-number').html(`<span class="question-number-text">Question ${currentQuestion["no"]}</span> <span class="question-instruction">${instruction}</span>`);
    $('#current-question-number').text(`Question ${currentQuestion["no"]}`);

    $('#question-text').html('');
    let qHtml = `<div class="question-content"><div class="question-text-content">${currentQuestion["question"]}</div>`;
    if (currentQuestion["description_image"]) {
        const src = getImageSrc(currentQuestion["description_image"]);
        if (src) qHtml += `<div class="question-description-image mt-3"><img src="${src}" class="img-fluid" alt="Question image" style="max-width:70%;height:auto;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);" onerror="this.style.display='none'"></div>`;
    }
    qHtml += `</div>`;
    $('#question-text').append(qHtml);

    if (currentQuestion["type"] === "Choices") {
        let valuesToMatch = currentQuestion["answer"].split(',');
        $('#choices').show(); $('#text-input').hide();

        let options = {
            "option_1": currentQuestion["option_1"],
            "option_2": currentQuestion["option_2"],
            "option_3": currentQuestion["option_3"],
            "option_4": currentQuestion["option_4"],
        };
        let choicesHtml = '';

        $.each(options, function (key, value) {
            if (value) {
                let inputType   = currentQuestion["multiple"] ? 'checkbox' : 'radio';
                let explanation = current_qs[`explanation_${key}`];
                let explanationHtml = explanation ? `<small class="explanation ml-10">${explanation}</small>` : '';
                let checked = valuesToMatch.includes(key.split("_")[1]) ? "checked" : '';
                let optImg  = currentQuestion[key + "_image"];
                let optImgHtml = '';
                if (optImg) {
                    const src = getImageSrc(optImg);
                    if (src) optImgHtml = `<div class="option-image mt-2"><img src="${src}" class="img-fluid" alt="Option image" style="max-width:200px;height:auto;border-radius:6px;" onerror="this.style.display='none'"></div>`;
                }
                choicesHtml += `
                    <label for="option_${currentQuestion["key"]}_${key}" class="w-100 mb-0" style="cursor:pointer;">
                        <div class="option-item ${checked ? 'selected' : ''}" style="border:1px solid #dee2e6;border-radius:8px;padding:12px;margin-bottom:8px;transition:all 0.2s ease;">
                            <div class="d-flex align-items-start">
                                <input class="option me-2 mt-1" value="${key}" type="${inputType}" name="qs_${currentQuestion["key"]}" ${checked} id="option_${currentQuestion["key"]}_${key}" style="margin-top:2px;">
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

        if (currentQuestion["marked_for_later"]) $('#markedForLater').prop("checked", true);
        $('#examTextInput').hide();
        $('#choices').html('').append(choicesHtml);

        $('.option').on('change', function () {
            if (currentQuestion["multiple"]) {
                const oi = $(this).closest('.option-item');
                if ($(this).is(':checked')) {
                    oi.addClass('selected').css({'background-color':'#e3f2fd','border-color':'#2196f3','box-shadow':'0 2px 8px rgba(33,150,243,0.2)'});
                } else {
                    oi.removeClass('selected').css({'background-color':'','border-color':'#dee2e6','box-shadow':'0 1px 4px rgba(0,0,0,0.1)'});
                }
            } else {
                $('.option-item').removeClass('selected').css({'background-color':'','border-color':'#dee2e6','box-shadow':'0 1px 4px rgba(0,0,0,0.1)'});
                $(this).closest('.option-item').addClass('selected').css({'background-color':'#e3f2fd','border-color':'#2196f3','box-shadow':'0 2px 8px rgba(33,150,243,0.2)'});
            }
        });

        $('.option:checked').each(function () {
            $(this).closest('.option-item').addClass('selected').css({'background-color':'#e3f2fd','border-color':'#2196f3','box-shadow':'0 2px 8px rgba(33,150,243,0.2)'});
        });

        $('.option-item').hover(
            function () { if (!$(this).hasClass('selected')) $(this).css({'background-color':'#f8f9fa','border-color':'#adb5bd'}); },
            function () { if (!$(this).hasClass('selected')) $(this).css({'background-color':'','border-color':'#dee2e6'}); }
        );

    } else {
        $('#choices').hide(); $('#examTextInput').show();
        $("#examTextInput").find("textarea").val(currentQuestion["answer"]);
        if (currentQuestion["marked_for_later"]) $('#markedForLater').prop("checked", true);
    }
}

function sendMessage(message, messageType, warningType) {
    if (currentQsNo > 1) {
        frappe.call({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.post_exam_message",
            type: "POST",
            args: {
                'exam_submission': exam["exam_submission"],
                'message':         message,
                'type_of_message': messageType,
                'warning_type':    warningType,
                'from':            "Candidate"
            },
            callback: (data) => { console.log(data); },
        });
    }
}

function sendChatMessage() {
    var message = $('#chat-input').val().trim();
    if (message) {
        frappe.call({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.post_exam_message",
            type: "POST",
            args: {
                'exam_submission': exam["exam_submission"],
                'message':         message,
                'type_of_message': 'General',
                'warning_type':    '',
            },
            callback: (data) => { $('#chat-input').val(''); updateMessages(exam.exam_submission); },
        });
    }
}

function startNoFaceCountdown() {
    if (noFaceTerminationTimer) return;
    let secondsLeft = NO_FACE_GRACE_SECONDS;
    showNoFaceCountdownBanner(secondsLeft);
    noFaceCountdownInterval = setInterval(() => {
        secondsLeft -= 1;
        if (secondsLeft >= 0) showNoFaceCountdownBanner(secondsLeft);
    }, 1000);
    noFaceTerminationTimer = setTimeout(() => {
        clearInterval(noFaceCountdownInterval);
        noFaceCountdownInterval = null;
        noFaceTerminationTimer  = null;
        terminateForNoFace();
    }, NO_FACE_GRACE_SECONDS * 1000);
}

function cancelNoFaceCountdown() {
    if (noFaceTerminationTimer)  { clearTimeout(noFaceTerminationTimer);   noFaceTerminationTimer  = null; }
    if (noFaceCountdownInterval) { clearInterval(noFaceCountdownInterval); noFaceCountdownInterval = null; }
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

    const snapshotPromise = violationSnapshots
        ? violationSnapshots.capture('noface', 'Exam terminated: face not visible to camera for 60 seconds.')
        : Promise.resolve();

    const terminatePromise = new Promise((resolve) => {
        frappe.call({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.post_exam_message",
            type: "POST",
            args: {
                'exam_submission': exam["exam_submission"],
                'message':         'Exam terminated: face not visible to camera for 60 seconds.',
                'type_of_message': 'Critical',
                'warning_type':    'nofacetimeout',
            },
            callback: resolve,
            error: (error) => { console.error("Failed to post nofacetimeout:", error); resolve(); }
        });
    });

    const timeout = new Promise((resolve) => setTimeout(resolve, 5000));
    Promise.race([Promise.all([snapshotPromise, terminatePromise]), timeout]).finally(() => {
        stopRecording();
        if (detector)          detector.destroy();
        if (violationSnapshots) violationSnapshots.destroy();
        window.location.href = "/exam/" + exam.exam_submission;
    });
}

function endExam(isAutoSubmit) {
    if (!examEnded) {
        frappe.call({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.end_exam",
            type: "POST",
            args: { "exam_submission": exam["exam_submission"] },
            callback: (data) => {
                examEnded = true;
                stopRecording();
                if (detector)           detector.destroy();
                if (violationSnapshots) violationSnapshots.destroy();
                if (isAutoSubmit) {
                    window.location.href = "/exam?auto_submitted=1&submission=" + encodeURIComponent(exam.exam_submission);
                } else {
                    window.location.href = "/exam/" + exam.exam_submission;
                }
            }
        });
    }
}

// ── startExam ──────────────────────────────────────────────────────────────────
// "Registered" path: call the API to mark the exam Started, then reload.
// Do NOT request screen share here — location.reload() destroys any stream
// obtained at this point, so it would be wasted work that also triggers a
// spurious violation (window loses focus during the browser permission dialog).
// The full-screen overlay shown after reload (in showScreenShareOverlay, called
// from startRecording when status === 'Started') handles screen share correctly
// with a single, clean user-gesture click.
async function startExam() {
    if (typeof checkMediaPermissionsBeforeStart === 'function' && !checkMediaPermissionsBeforeStart()) return;

    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.start_exam",
        type: "POST",
        args: { "exam_submission": exam["exam_submission"] },
        callback: (data) => {
            if (data.message && data.message.end_time) {
                exam.end_time = data.message.end_time;
            }
            $("#quiz-form").removeClass("hide");
            location.reload();
        }
    });
}

function getQuestion(qsno) {
    clearTimeout(submitAnswerTimeout);
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.get_question",
        type: "POST",
        args: { "exam_submission": exam["exam_submission"], "qsno": qsno },
        callback: (data) => {
            $("#exam-summary").addClass("hide");
            $("#quiz-form").removeClass("hide");
            displayQuestion(data.message);
            currentQsNo = data.message.qs_no;
            updateOverviewMap();
        }
    });
}

function showSubmitConfirmPage() {
    clearTimeout(submitAnswerTimeout);
    if (currentQuestion && currentQuestion["type"] == "Choices") submitAnswer(false);

    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.exam_overview",
        args:   { "exam_submission": exam.exam_submission },
        async:  false,
        success: (data) => {
            examOverview = data.message;
            $("#exam-summary").removeClass("hide");
            $("#quiz-form").addClass("hide");
            $("#quiz-title").html();
            $('#quiz-box').removeClass("text-center");
            let messageHtml = `
                <div class="d-flex justify-content-center">
                <div class="card" style="max-width:30rem;">
                    <div class="card-body">
                    <div class="d-flex align-items-center mb-3">
                        <i class="bi bi-clock me-2"></i>
                        <h6 class="mb-0">Time Remaining: <span class="ml-10 timer">--:--</span></h6>
                    </div>
                    <ul class="list-group list-group-flush">
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span class="mr-10">Total Questions</span><span>${examOverview.total_questions}</span>
                        </li>
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span class="mr-10">Total Answered</span><span>${examOverview.total_answered}</span>
                        </li>
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span class="mr-10">Marked for Review</span><span>${examOverview.total_marked_for_later}</span>
                        </li>
                    </ul>
                    </div>
                    <div class="card-footer">
                    <button class="btn btn-primary w-100" id="quizSubmit" onClick=endExam();>Submit Exam</button>
                    </div>
                </div>
                </div>`;
            $("#quiz-box").html(messageHtml);
        }
    });
}

function submitAnswer(loadNext) {
    if (isSubmittingAnswer) {
        if (loadNext) pendingNavigation = true;
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
        if (!loadNext && !mrkForLtr) return;
        if (loadNext && !mrkForLtr && (!answer || answer.trim() === "")) {
            if (currentQuestion["no"] < examOverview["total_questions"]) {
                getQuestion(currentQuestion["no"] + 1);
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
            'qs_name':    currentQuestion["name"],
            'qs_no':      currentQuestion["no"],
            'answer':     answer,
            'markdflater': mrkForLtr,
        },
        callback: (data) => {
            isSubmittingAnswer = false;
            const shouldNavigate   = loadNext || pendingNavigation;
            pendingNavigation      = false;
            const userStillOnSavedQs = currentQuestion && currentQuestion["no"] === data.message.qs_no;

            if (shouldNavigate && userStillOnSavedQs) {
                if (data.message.qs_no < examOverview["total_questions"]) {
                    getQuestion(data.message.qs_no + 1);
                    updateOverviewMap();
                } else {
                    showSubmitConfirmPage();
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
}
