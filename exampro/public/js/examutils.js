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
    if (messageFrom === "Candidate") {
        var chatTimestamp = $('<div class="chat-timestamp-right">' + timestamp + '</div>');
    } else {
        var chatTimestamp = $('<div class="chat-timestamp">' + timestamp + '</div>');
    }

    var msgWithPill = message;
    if (messageType === "Warning") {
        msgWithPill = '<span class="badge badge-warning mr-1">Warning</span>' + message;
    } else if (messageType === "Critical") {
        msgWithPill = '<span class="badge badge-danger mr-1">Critical</span>' + message;
    }
    if (messageFrom === "Candidate") {
        var chatBubble = $('<div class="chat-bubble chat-right">' + msgWithPill + '</div>');
    } else {
        var chatBubble = $('<div class="chat-bubble chat-left">' + msgWithPill + '</div>');
    }
    
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

                convertedTime = timeAgo(chatmsg.creation);
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
                    addChatBubble(convertedTime, chatmsg.message, chatmsg.type_of_message, chatmsg.from);
                }

                existingMessages[exam_submission].push(chatmsg.creation);
            });

        },
    });

    $('#chat-input').on('click', function() {
        $('#messages .chat-container').scrollTop($('#messages .chat-container')[0].scrollHeight);
    });
};
