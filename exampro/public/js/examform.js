var hiddenTime = 0;
var visibleTime = 0;
var examOverview;
var currentQuestion;
var detector;

// Function to update the countdown timer
function updateTimer() {
    if (!examEnded) {
        var remainingTime = new Date(exam.end_time) - new Date().getTime();
        if (remainingTime <= 0) {
            // Display "0m 0s" when time is up
            document.getElementById("timer").innerHTML = "00:00";
            endExam();
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
let recordingInterval;

function sendVideoBlob(blob) {
    let xhr = new XMLHttpRequest();
    const unixTimestamp = Math.floor(Date.now() / 1000);
    xhr.open('POST', '/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.upload_video', true);
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);

    let form_data = new FormData();
    form_data.append('file', blob, unixTimestamp + ".webm");
    form_data.append('exam_submission', exam["exam_submission"])
    xhr.send(form_data);
}

// Function to start recording
function startRecording() {
    // Get the webcam stream
    const constraints = {
        audio: false,
        video: true
    };

    navigator.mediaDevices.getUserMedia(constraints)
        .then(function (mediaStream) {
            stream = mediaStream;
            // Add track event listeners
            stream.getTracks().forEach(track => {
                track.addEventListener('ended', function () {
                    examAlert(
                        'Webcam was disabled or stopped',
                        'Exam will be terminated. Refresh the page or fix the issue.'
                    );
                    sendMessage('Webcam was disabled or stopped', 'Warning', 'nowebcam');
                });
            });

            // Attach the stream to the video element
            document.getElementById('webcam-stream').srcObject = stream;

            if (exam["submission_status"] === "Started") { 
            // Create a recorder instance
            recorder = RecordRTC(stream, {
                type: 'video',
                mimeType: 'video/webm',
                videoBitsPerSecond: 8000

            });

            // Start recording
            recorder.startRecording();

            // Start sending recorded blobs to the server every 10 seconds
            recordingInterval = setInterval(function () {
                recorder.stopRecording(function () {
                    // Get the recorded blob
                    let blob = recorder.getBlob();

                    sendVideoBlob(blob);
                    // Reset the recorder
                    recorder = RecordRTC(stream, { type: 'video' });
                    recorder.startRecording();
                });
            }, 10000);
            }
        })
        .catch(function (error) {
            examAlert(
                'No webcam detected',
                'Exam will be terminated. Refresh the page or fix the issue.'
            );
            sendMessage('Webcam was not detected', 'Warning', 'nowebcam');
        });
}

// Function to stop recording
function stopRecording() {
    // Stop recording and clear the recording interval
    clearInterval(recordingInterval);
    if (recorder) {
        recorder.stopRecording(function () {
            // Release the stream
            if (stream) {
                stream.getTracks().forEach(function (track) {
                    track.stop();
                });
            }
        });
    } else if (stream) {
        // If recorder is not defined but stream exists, stop the tracks
        stream.getTracks().forEach(function (track) {
            track.stop();
        });
    }
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
        $("#start-banner").addClass("hide");
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

    var collapseElement = $('#videoCollapse');
    collapseElement.on('shown.bs.collapse', function () {
        $('#toggleButton').text('Hide Video');
    });
    collapseElement.on('hidden.bs.collapse', function () {
        $('#toggleButton').text('Show Video');
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
        submitAnswer();
    });


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

            // document.getElementById("answered").innerHTML = data.message.total_answered;
            // document.getElementById("notattempted").innerHTML = data.message.total_not_attempted;
            document.getElementById("markedforlater").innerHTML = data.message.total_marked_for_later;
            $("#question-length").text(data.message.total_questions);

            // populate buttons
            if (data.message.total_questions != 0) {
                $("#button-grid").html('');
            }
            for (let i = 1; i <= data.message.total_questions; i++) {
                let btnCls = "btn-outline-secondary";
                let btnStyle = "";
                
                // Determine button style based on question status
                if (data.message.submitted[i] && data.message.submitted[i].marked_for_later) {
                    btnCls = "btn-warning text-white";
                    btnStyle = "";
                } else if (data.message.submitted[i] && data.message.submitted[i].answer) {
                    btnCls = "btn-outline-success";
                    btnStyle = "border-width: 2px;";
                }
                
                // If this is the current question, highlight it
                if (currentQuestion && i === currentQuestion["no"]) {
                    btnCls = "btn-primary";
                }
                
                // Create a new button
                const button = $("<button></button>");
                button.addClass("exam-map-btn btn " + btnCls);
                button.attr("id", "button-" + i);
                button.attr("style", btnStyle);
                
                // Set the button content based on question status
                if (data.message.submitted[i] && data.message.submitted[i].marked_for_later) {
                    button.html(answrLater + ' ' + i);
                } else if (data.message.submitted[i] && data.message.submitted[i].answer) {
                    button.html(answrdCheck + ' ' + i);
                } else {
                    button.text(i);
                }
                
                // Append the button to the grid
                $("#button-grid").append(button);
                
                // Add click event handler
                button.click((e) => {
                    getQuestion(i);
                });
            }
        },
    });
};

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
        "marked_for_later": current_qs.marked_for_later
    }

    $("#start-banner").addClass("hide");
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
                     style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"
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
                let explanation = current_qs[`explanation_${key}`];
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
    }

    if (exam.time) {
        $('#exam-timer').attr('data-time', exam.time);
        $('#exam-timer').show();
    } else {
        $('#exam-timer').hide();
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

function endExam() {
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
                window.location.href = "/exam/" + exam.exam_submission;
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
            
            $("#start-banner").addClass("hide");
            $("#quiz-form").removeClass("hide");
            // getQuestion(1);
            // updateTimer();
            location.reload();
        }
    });
};

function getQuestion(qsno) {
    // Only submit the current answer if we're on a question after the first one
    if (currentQuestion && currentQuestion.no > 1) {
        submitAnswer(false);
    }
    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.get_question",
        type: "POST",
        args: {
            "exam_submission": exam["exam_submission"],
            "qsno": qsno,
        },
        callback: (data) => {
            displayQuestion(data.message);
            currentQsNo = data.message.qs_no;
            updateOverviewMap();
        }
    });
};

function showSubmitConfirmPage() {
        // Submit the current answer before showing the summary
        submitAnswer(false);
        
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
                
                $("#start-banner").removeClass("hide");
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
                        <button class="btn btn-success w-100" id="quizSubmit" onClick=endExam();>Submit Exam</button>
                        </div>
                    </div>
                    </div>
                    `
                $("#quiz-box").html(messageHtml);
            }
        });
}


function submitAnswer(loadNext) {
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
    }

    frappe.call({
        method: "exampro.exam_pro.doctype.exam_submission.exam_submission.submit_question_response",
        type: "POST",
        async: false,
        args: {
            'exam_submission': exam["exam_submission"],
            'qs_name': currentQuestion["name"],
            'answer': answer,
            'markdflater': mrkForLtr,
        },
        callback: (data) => {
            console.log("submitted answer.");
            // check if this is the last question
            if (loadNext) {
                if (data.message.qs_no < examOverview["total_questions"]) {
                    let nextQs = data.message.qs_no + 1
                    getQuestion(nextQs);
                    updateOverviewMap();
                } else {
                    showSubmitConfirmPage();
                }
            }
        },
    });
};
