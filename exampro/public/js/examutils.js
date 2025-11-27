const existingMessages = {};

const examAlert = (alertTitle, alertText) => {
    $('#alertTitle').text(alertTitle);
    $('#alertText').text(alertText);
    $('#examAlert').modal('show');
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
                    frappe.msgprint({
                        title: 'Critial',
                        message: chatmsg.message ,
                        primary_action:{
                            action(values) {
                                window.location.reload();
                            }
                        }
                    });
                    setTimeout(function() {
                        window.location.reload()
                    }, 5000); // 5 seconds delay
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

// Helper Slide Modal Functions
let helperSlideData = {
    questionNo: 0,
    questionText: '',
    helpContent: '',
    helpQuiz: [],
    currentQuizIndex: 0,
    onComplete: null
};

const initHelperSlideModal = () => {
    if ($('#helperSlideModal').length) return;

    const modalHtml = `
    <div class="modal fade" id="helperSlideModal" tabindex="-1" data-backdrop="static" data-keyboard="false">
        <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header bg-primary text-white">
                    <h5 class="modal-title">
                        <span id="helperSlideTitle">Question Help</span>
                    </h5>
                </div>
                <div class="modal-body">
                    <div class="mb-3 p-3 bg-light rounded">
                        <small class="text-muted">Question <span id="helperQuestionNo"></span></small>
                        <div id="helperQuestionText" class="mt-1"></div>
                    </div>

                    <!-- Page 1: Help Content -->
                    <div id="helperContentPage">
                        <div id="helperContentText" class="p-3 border rounded"></div>
                        <div class="text-right mt-3">
                            <button type="button" class="btn btn-primary" id="helperNextToQuiz">
                                Continue to Quiz <i class="fa fa-arrow-right ml-1"></i>
                            </button>
                        </div>
                    </div>

                    <!-- Page 2: Quiz -->
                    <div id="helperQuizPage" style="display: none;">
                        <div class="mb-3">
                            <small class="text-muted">Quiz <span id="helperQuizProgress"></span></small>
                        </div>
                        <div id="helperQuizQuestion" class="mb-3 font-weight-bold"></div>
                        <div id="helperQuizChoices" class="mb-3"></div>
                        <div id="helperQuizFeedback" class="mb-3" style="display: none;"></div>
                        <div class="text-right">
                            <button type="button" class="btn btn-primary" id="helperSubmitQuiz">Submit Answer</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>`;

    $('body').append(modalHtml);

    // Event handlers
    $('#helperNextToQuiz').on('click', () => {
        if (helperSlideData.helpQuiz.length > 0) {
            $('#helperContentPage').hide();
            $('#helperQuizPage').show();
            renderHelperQuiz();
        } else {
            closeHelperSlideModal();
        }
    });

    $('#helperSubmitQuiz').on('click', submitHelperQuizAnswer);
};

const showHelperSlideModal = (questionNo, questionText, helpContent, helpQuiz, onComplete) => {
    initHelperSlideModal();

    helperSlideData = {
        questionNo,
        questionText,
        helpContent,
        helpQuiz: helpQuiz || [],
        currentQuizIndex: 0,
        onComplete
    };

    $('#helperQuestionNo').text(questionNo);
    $('#helperQuestionText').html(questionText);
    $('#helperContentText').html(helpContent || 'No additional help content available.');

    // Reset to first page
    $('#helperContentPage').show();
    $('#helperQuizPage').hide();
    $('#helperQuizFeedback').hide();

    // Update button text based on quiz availability
    if (helperSlideData.helpQuiz.length > 0) {
        $('#helperNextToQuiz').text('Continue to Quiz ').append('<i class="fa fa-arrow-right ml-1"></i>');
    } else {
        $('#helperNextToQuiz').text('Close');
    }

    $('#helperSlideModal').modal('show');
};

const renderHelperQuiz = () => {
    const quiz = helperSlideData.helpQuiz[helperSlideData.currentQuizIndex];
    if (!quiz) return;

    $('#helperQuizProgress').text(`${helperSlideData.currentQuizIndex + 1} of ${helperSlideData.helpQuiz.length}`);
    $('#helperQuizQuestion').text(quiz.question);

    const choicesHtml = ['choice_1', 'choice_2', 'choice_3', 'choice_4']
        .filter(key => quiz[key])
        .map((key, idx) => {
            const choiceLabel = `Choice ${idx + 1}`;
            return `
            <div class="form-check mb-2">
                <input class="form-check-input" type="radio" name="helperQuizChoice"
                       id="helperChoice${idx + 1}" value="${choiceLabel}">
                <label class="form-check-label" for="helperChoice${idx + 1}">
                    ${quiz[key]}
                </label>
            </div>`;
        }).join('');

    $('#helperQuizChoices').html(choicesHtml);
    $('#helperQuizFeedback').hide();
    $('#helperSubmitQuiz').prop('disabled', false).text('Submit Answer');
};

const submitHelperQuizAnswer = () => {
    const selectedAnswer = $('input[name="helperQuizChoice"]:checked').val();
    if (!selectedAnswer) {
        $('#helperQuizFeedback')
            .removeClass('alert-success alert-danger')
            .addClass('alert alert-warning')
            .text('Please select an answer.')
            .show();
        return;
    }

    const quiz = helperSlideData.helpQuiz[helperSlideData.currentQuizIndex];
    const isCorrect = selectedAnswer === quiz.correct_choice;

    if (isCorrect) {
        $('#helperQuizFeedback')
            .removeClass('alert-warning alert-danger')
            .addClass('alert alert-success')
            .text('Correct!')
            .show();

        // Move to next quiz or close
        setTimeout(() => {
            helperSlideData.currentQuizIndex++;
            if (helperSlideData.currentQuizIndex < helperSlideData.helpQuiz.length) {
                renderHelperQuiz();
            } else {
                closeHelperSlideModal();
            }
        }, 1000);
    } else {
        $('#helperQuizFeedback')
            .removeClass('alert-warning alert-success')
            .addClass('alert alert-danger')
            .text('Incorrect. Please try again.')
            .show();
    }
};

const closeHelperSlideModal = () => {
    $('#helperSlideModal').modal('hide');
    if (helperSlideData.onComplete) {
        helperSlideData.onComplete();
    }
};

const checkAndShowHelperSlide = (response, questionNo, questionText, onComplete) => {
    if (response.help_slide || (response.help_quiz && response.help_quiz.length > 0)) {
        showHelperSlideModal(
            questionNo,
            questionText,
            response.help_slide,
            response.help_quiz,
            onComplete
        );
        return true;
    }
    return false;
};
