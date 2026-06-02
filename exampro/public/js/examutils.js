const existingMessages = {};

const examAlert = (alertTitle, alertText) => {
    $('#alertTitle').text(alertTitle);
    $('#alertText').text(alertText);
    $('#examAlert').modal('show');
}

// --- Audible alarm (WebAudio) -----------------------------------------------
// Proctoring warnings and terminations need an audio cue, not just a toast.
// A short beep is synthesized with WebAudio so no binary asset has to ship.
// Browsers keep the AudioContext suspended until a user gesture, so we resume
// it on the first interaction (see unlockExamAudio, wired up in examform.js).
let _examAudioCtx = null;

function _getExamAudioCtx() {
    if (_examAudioCtx) return _examAudioCtx;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    try {
        _examAudioCtx = new Ctx();
    } catch (e) {
        return null;
    }
    return _examAudioCtx;
}

// Resume a suspended AudioContext. Call from a user-gesture handler so later
// programmatic alarms are allowed to play.
function unlockExamAudio() {
    const ctx = _getExamAudioCtx();
    if (ctx && ctx.state === "suspended") {
        ctx.resume().catch(function () {});
    }
}

// Play a short alarm. `urgent` uses a higher pitch and an extra beep — used for
// terminations and the final no-face countdown stretch.
function playAlarm(urgent) {
    const ctx = _getExamAudioCtx();
    if (!ctx) return;
    if (ctx.state === "suspended") {
        // Best effort; blocked until a gesture has unlocked the context.
        ctx.resume().catch(function () {});
    }
    const beeps = urgent ? 3 : 2;
    const beepDur = 0.18;
    const gap = 0.12;
    const now = ctx.currentTime;
    for (let i = 0; i < beeps; i++) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "square";
        osc.frequency.value = urgent ? 880 : 660;
        const start = now + i * (beepDur + gap);
        const end = start + beepDur;
        // Short attack/decay envelope to avoid audible clicks.
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.25, start + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, end);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(start);
        osc.stop(end + 0.02);
    }
}

// Blocking termination/critical alert. Reuses the #examAlert modal but makes it
// non-dismissible and turns the footer button into an acknowledge action that
// navigates away — replacing the old silent 5-second auto-reload that wiped the
// notice before the candidate could read it.
const criticalExamAlert = (message, onAcknowledge) => {
    $('#alertTitle').text('Exam Ended');
    $('#alertText').text(message);

    // Make the modal blocking: hide the header close (X); the footer button
    // becomes the only way out and performs the navigation.
    $('#examAlert .modal-header .btn[data-bs-dismiss]').hide();

    const $btn = $('#alertCloseButton');
    $btn.text('OK').removeAttr('data-bs-dismiss');
    $btn.off('click').on('click', function () {
        if (typeof onAcknowledge === 'function') {
            onAcknowledge();
        } else {
            window.location.reload();
        }
    });

    const modalEl = document.getElementById('examAlert');
    if (modalEl && typeof bootstrap !== 'undefined' && bootstrap.Modal) {
        const inst = bootstrap.Modal.getOrCreateInstance(modalEl, {
            backdrop: 'static',
            keyboard: false
        });
        inst.show();
    } else {
        // jQuery fallback
        $('#examAlert').modal({ backdrop: 'static', keyboard: false });
        $('#examAlert').modal('show');
    }

    playAlarm(true);
};

if (typeof window !== "undefined") {
    window.playAlarm = playAlarm;
    window.unlockExamAudio = unlockExamAudio;
    window.criticalExamAlert = criticalExamAlert;
}

function timeAgo(timestamp) {
    const currentTime = new Date();
    const providedTime = new Date(timestamp);
    const timeDifference = currentTime - providedTime;
    const minutesDifference = Math.floor(timeDifference / (1000 * 60));

    if (minutesDifference < 1) {
        return 'Just now';
    } else if (minutesDifference === 1) {
        return '1 minute ago';
    } else if (minutesDifference < 60) {
        return minutesDifference + ' minutes ago';
    } else if (minutesDifference < 120) {
        return '1 hour ago';
    } else if (minutesDifference < 1440) {
        return Math.floor(minutesDifference / 60) + ' hours ago';
    } else if (minutesDifference < 2880) {
        return '1 day ago';
    } else {
        return Math.floor(minutesDifference / 1440) + ' days ago';
    }
}

// check if the last video is before 30 seconds
function videoDisconnected(lastVideoURL) {
    var url = new URL(lastVideoURL);
    var filenameWithExtension = url.pathname.split("/").pop();
    var filename = filenameWithExtension.split(".")[0];

    var currentTimestamp = Math.floor(Date.now() / 1000);
    var differenceInSeconds = Math.floor(currentTimestamp - filename);
    if (differenceInSeconds >= 30) {
        return true;
    } else {
        return false;
    }

}

const addChatBubble = (timestamp, message, messageType, messageFrom) => {
    var chatContainer = $('#chat-messages');
    var timestampDivClass = messageFrom === "Candidate" ? "chat-timestamp-right" : "chat-timestamp";
    // Store original timestamp as data-timestamp
    var chatTimestamp = $('<div class="' + timestampDivClass + '"><span class="chat-time" data-timestamp="' + timestamp + '">' + timeAgo(timestamp) + '</span></div>');

    var msgWithPill = message;
    if (messageType === "Warning") {
        msgWithPill = '<span class="badge badge-warning mr-1">Warning</span>' + message;
    } else if (messageType === "Critical") {
        msgWithPill = '<span class="badge badge-danger mr-1">Critical</span>' + message;
    }
    var chatBubble = $('<div class="' + (messageFrom === "Candidate" ? "chat-bubble chat-right" : "chat-bubble chat-left") + '">' + msgWithPill + '</div>');

    var chatWrapper = $('<div class="d-flex flex-column mb-2"></div>');
    chatWrapper.append(chatTimestamp);
    chatWrapper.append(chatBubble);
    // Append the new chat bubble to the chat messages container
    chatContainer.append(chatWrapper);
}

const updateMessages = (exam_submission) => {
    if (!(exam_submission in existingMessages)) {
        existingMessages[exam_submission] = [];
    }
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.exam_messages",
        args: {
            'exam_submission': exam_submission,
        },
        callback: (data) => {
            msgData = data.message["messages"];
            $("#msgCount").text(msgData.length);
            // loop through msgs and add alerts
            // Add new messages as alerts to the Bootstrap div
            msgData.forEach(chatmsg => {
                // check msg already processed
                if (existingMessages[exam_submission].includes(chatmsg.creation)) {
                    return;
                }

                if (chatmsg.type_of_message === "Critical") {
                    // Blocking, acknowledged alert with an audible alarm. The
                    // page navigates only when the candidate clicks OK — no
                    // silent auto-reload that wipes the notice before it's read.
                    criticalExamAlert(chatmsg.message, function () {
                        window.location.reload();
                    });
                } else {
                    addChatBubble(chatmsg.creation, chatmsg.message, chatmsg.type_of_message, chatmsg.from);
                }

                existingMessages[exam_submission].push(chatmsg.creation);
            });

        },
    });

    $('#chat-input').on('click', function() {
        $('#messages .chat-container').scrollTop($('#messages .chat-container')[0].scrollHeight);
    });
};
