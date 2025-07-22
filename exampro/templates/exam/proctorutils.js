var videoStore = {};
var currentVideoIndex = {};
var videoBlobStore = {};
const MAX_BLOB_CACHE_SIZE = 4;
var activeChat = "";
const videos = document.getElementsByClassName("video");
const togglePlayBtn = document.getElementsByClassName("togglePlayBtn");

// Cache for storing the last known message for each candidate
var lastKnownMessages = {};

/**
 * A utility function to manage the FIFO queue-like behavior of the videoBlobStore.
 */
function addBlobToCache(exam_submission, index, blob) {
  if (!videoBlobStore[exam_submission]) {
    videoBlobStore[exam_submission] = [];
  }

  videoBlobStore[exam_submission].push({ index: index, blob: blob });

  // Ensure the cache stores only the max number of videos
  if (videoBlobStore[exam_submission].length > MAX_BLOB_CACHE_SIZE) {
    videoBlobStore[exam_submission].shift();
  }
}

/**
 * A utility function to retrieve a blob from the cache.
 */
function getBlobFromCache(exam_submission, index) {
  if (videoBlobStore[exam_submission]) {
    const cachedItem = videoBlobStore[exam_submission].find(
      (item) => item.index === index,
    );
    return cachedItem ? cachedItem.blob : null;
  }
  return null;
}

function addEventListenerToClass(className, eventType, handlerFunction) {
  var elements = document.getElementsByClassName(className);

  for (var i = 0; i < elements.length; i++) {
    elements[i].addEventListener(eventType, handlerFunction);
  }
}
function togglePlay() {
  // Find the closest '.video-container' ancestor
  const videoContainer = this.closest(".video-container");

  // Within that container, find the video element
  const video = videoContainer.querySelector("video");
  if (video.paused || video.ended) {
    video.play();
  } else {
    video.pause();
  }
}

function updatetogglePlayBtn() {
  // Find the closest '.video-container' ancestor from the video
  const videoContainer = this.closest(".video-container");
  console.log("Updating toggle play button for video container:", videoContainer);

  // Within that container, find the togglePlayBtn
  const togglePlayBtn = videoContainer.querySelector(".togglePlayBtn");
  togglePlayBtn.innerHTML = this.paused ? 
    '<i class="bi bi-play-fill"></i>' : 
    '<i class="bi bi-pause-fill"></i>';
}

function parseUnitTime(videoURL, addSeconds) {
  var url = new URL(videoURL);
  var filenameWithExtension = url.pathname.split("/").pop();
  var filename = filenameWithExtension.split(".")[0];

  var date = new Date(filename * 1000);
  var hours = String(date.getHours()).padStart(2, "0");
  var minutes = String(date.getMinutes()).padStart(2, "0");
  var seconds = String(date.getSeconds() + Math.floor(addSeconds)).padStart(
    2,
    "0",
  );

  return hours + ":" + minutes + ":" + seconds;
}

function handleProgress() {
  const videoContainer = this.closest(".video-container");
  let fTS = videoContainer.querySelector(".fileTimeStamp");
  let exam_submission = videoContainer.getAttribute("data-videoid");
  let islive = videoContainer.getAttribute("data-islive");

  // Within that container, find the video element
  const video = videoContainer.querySelector("video");
  // show timestamp only if current video is not live
  if (islive === "0") {
    fTS.innerText = parseUnitTime(
      videoStore[exam_submission][currentVideoIndex[exam_submission]],
      video.currentTime,
    );
  } else {
    fTS.innerText = "";
  }
}

function playVideoAtIndex(exam_submission, index) {
  currentVideoIndex[exam_submission] = index;
  var vid = document.getElementById(exam_submission);

  const cachedBlob = getBlobFromCache(exam_submission, index);
  if (cachedBlob) {
    vid.src = URL.createObjectURL(cachedBlob);
    vid.load();
    vid.play();
  } else {
    // Download the current video and store it as a blob
    fetch(videoStore[exam_submission][currentVideoIndex[exam_submission]])
      .then((response) => response.blob())
      .then((blob) => {
        addBlobToCache(exam_submission, index, blob);
        vid.src = URL.createObjectURL(blob);
        vid.load();
        vid.play();
      })
      .catch((error) => {
        console.error("Error downloading video:", error);
      });
  }

  // Prepare the next video in the background if it exists
  if (
    currentVideoIndex[exam_submission] + 1 <
    videoStore[exam_submission].length
  ) {
    var nextIndex = currentVideoIndex[exam_submission] + 1;

    // Only download the next video if it's not already in the cache
    if (!getBlobFromCache(exam_submission, nextIndex)) {
      fetch(videoStore[exam_submission][nextIndex])
        .then((response) => response.blob())
        .then((blob) => {
          addBlobToCache(exam_submission, nextIndex, blob);
        })
        .catch((error) => {
          console.error("Error downloading next video:", error);
        });
    }

    // Set an event listener to switch to the next video when the current one ends
    vid.onended = function () {
      currentVideoIndex[exam_submission]++;
      const nextCachedBlob = getBlobFromCache(
        exam_submission,
        currentVideoIndex[exam_submission],
      );
      if (nextCachedBlob) {
        vid.src = URL.createObjectURL(nextCachedBlob);
        vid.load();
        vid.play();
        // Optionally preload the next video if there is one
        if (
          currentVideoIndex[exam_submission] + 1 <
          videoStore[exam_submission].length
        ) {
          playVideoAtIndex(exam_submission, currentVideoIndex[exam_submission]);
        }
      }
    };
  }
}

function playVideoAtIndexOld(exam_submission, index) {
  currentVideoIndex[exam_submission] = index;
  var vid = document.getElementById(exam_submission);

  if (currentVideoIndex[exam_submission] < videoStore[exam_submission].length) {
    vid.src = videoStore[exam_submission][currentVideoIndex[exam_submission]];
    vid.load();
    vid.play();
  } else {
    console.log("End of playlist");
  }
}

function handleSliderUpdate() {
  // Find the closest '.video-container' ancestor
  const videoContainer = this.closest(".video-container");
  let exam_submission = videoContainer.getAttribute("data-videoid");
  playVideoAtIndex(exam_submission, this.value);
}

function playNextVideo() {
  const videoContainer = this.closest(".video-container");
  let exam_submission = videoContainer.getAttribute("data-videoid");
  playVideoAtIndex(exam_submission, currentVideoIndex[exam_submission] + 1);
}

function playLastVideo() {
  const videoContainer = this.closest(".video-container");
  let exam_submission = videoContainer.getAttribute("data-videoid");
  let fTS = videoContainer.querySelector(".fileTimeStamp");
  fTS.innerText = "";

  playVideoAtIndex(exam_submission, videoStore[exam_submission].length - 1);
}

function playPreviousVideo() {
  const videoContainer = this.closest(".video-container");
  let exam_submission = videoContainer.getAttribute("data-videoid");
  playVideoAtIndex(exam_submission, currentVideoIndex[exam_submission] - 1);
}

function appendMessage(convertedTime, text, sender) {
  const chatMessages = document.getElementById('chat-messages');

  const messageElement = document.createElement('div');
  messageElement.className = `d-flex flex-column mb-2`;

  const timestampElement = document.createElement('div');
  timestampElement.className = `${sender === 'Candidate' ? 'chat-timestamp' : 'chat-timestamp-right'}`;
  timestampElement.textContent = convertedTime;

  const contentElement = document.createElement('div');
  contentElement.className = `chat-bubble ${sender === 'Candidate' ? 'chat-left' : 'chat-right'}`;
  contentElement.textContent = text;
  
  messageElement.appendChild(timestampElement);
  messageElement.appendChild(contentElement);
  
  chatMessages.appendChild(messageElement);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

const updateProcMessages = (exam_submission) => {
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
              appendMessage(convertedTime, chatmsg.message, chatmsg.from);
              existingMessages[exam_submission].push(chatmsg.creation);
          });

      },
  });

};

function openChatModal(event) {
  let videoId, candName, videoSrc;
  
  if (this.classList.contains('message-card')) {
    // Called from sidebar card click
    videoId = this.getAttribute("data-submission");
    candName = this.querySelector(".card-subtitle").textContent;
    const videoContainer = document.querySelector(`.video-container[data-videoid="${videoId}"]`);
    const video = videoContainer.querySelector("video");
    videoSrc = video.src;
    // Check if the exam has been submitted
    if (videoContainer.getAttribute("data-submission-status") === "Submitted") {
      // Don't open modal if submission status is "Submitted"
      console.log("Chat disabled: Exam already submitted");
      return;
    }
    
  } else {
    // Called from video controls
    const videoContainer = this.closest(".video-container");
    const video = videoContainer.querySelector("video");
    videoSrc = video.src;
    videoId = videoContainer.getAttribute("data-videoid");
    candName = videoContainer.getAttribute("data-candidatename");

    // Check if the exam has been submitted
    if (videoContainer.getAttribute("data-submission-status") === "Submitted") {
      // Don't open modal if submission status is "Submitted"
      console.log("Chat disabled: Exam already submitted");
      return;
    }

  }

  const modalVideo = document.getElementById("modalVideoElement");
  modalVideo.src = videoSrc;
  $("#chatModal").modal("show");
  $("#candidateName").text(candName);
  activeChat = videoId;
  $("#chat-messages").empty();
  existingMessages[videoId] = [];

  setInterval(function () {
    updateProcMessages(videoId);
  }, 1000); // 1 seconds
}

function onLoanMetaData() {
  const videoContainer = this.closest(".video-container");
  const video = videoContainer.querySelector("video");
  let skipfwd = videoContainer.querySelector(".skipFwd");
  let exam_submission = videoContainer.getAttribute("data-videoid");
  const offlineOverlay = document.getElementById(`offline-overlay-${exam_submission}`);

  if (video.src === "") {
    videoContainer.classList.add("border", "border-primary");
  } else {
    videoContainer.classList.remove("border", "border-primary");
    // if currentidx is length-1, then we are playing last video
    let disconnected = videoDisconnected(
      videoStore[exam_submission][videoStore[exam_submission].length - 1],
    );
    
    // Show/hide offline overlay based on connection status
    if (disconnected) {
      if (offlineOverlay) {
        offlineOverlay.classList.add("show");
      }
      // Update the message sidebar status badge to "Offline"
      updateMessageCardStatus(exam_submission, "offline");
    } else {
      if (offlineOverlay) {
        offlineOverlay.classList.remove("show");
      }
      // Update the message sidebar status badge to "Started"
      updateMessageCardStatus(exam_submission, "started");
    }
    
    if (
      currentVideoIndex[exam_submission] ==
      videoStore[exam_submission].length - 1
    ) {
      skipfwd.disabled = true;
      // check if the last video is 30 sec old
      if (!video.paused) {
        if (!disconnected) {
            videoContainer.setAttribute("data-islive", "1");
          } else {
            videoContainer.setAttribute("data-islive", "0");
        }
      }
    } else {
      skipfwd.disabled = false;
      if (!disconnected) {
        videoContainer.setAttribute("data-islive", "0");
      } else {
        videoContainer.setAttribute("data-islive", "0");
      }
    }
  }
}


addEventListenerToClass("togglePlayBtn", "click", togglePlay);
addEventListenerToClass("video", "click", togglePlay);
addEventListenerToClass("video", "play", updatetogglePlayBtn);
addEventListenerToClass("video", "pause", updatetogglePlayBtn);
addEventListenerToClass("video", "timeupdate", handleProgress);
// addEventListenerToClass("video", "ended", playNextVideo);
addEventListenerToClass("goLive", "click", playLastVideo);
addEventListenerToClass("skipBack", "click", playPreviousVideo);
addEventListenerToClass("skipFwd", "click", playNextVideo);
addEventListenerToClass("menu", "click", openChatModal);
addEventListenerToClass("video", "loadedmetadata", onLoanMetaData);

function updateVideoList() {
  for (var i = 0; i < videos.length; i++) {
    // Check if the element is an HTML5 video
    if (videos[i].nodeName !== "VIDEO") {
      continue; // Skip to the next iteration of the loop
    }
    let exam_submission = videos[i].getAttribute("data-videoid");
    frappe.call({
      method:
        "exampro.exam_pro.doctype.exam_submission.exam_submission.proctor_video_list",
      args: {
        exam_submission: exam_submission,
      },
      success: (data) => {
        var vid = document.getElementById(exam_submission);
        let container = vid.closest(".video-container");
        container.classList.remove("hidden");
        // convert api response to an array of objects
        let videoList = Object.entries(data.message.videos).map(
          ([unixtimestamp, videourl]) => {
            return { unixtimestamp: parseInt(unixtimestamp, 10), videourl };
          },
        );
        // sort them
        videoList.sort((a, b) => a.unixtimestamp - b.unixtimestamp);

        videoStore[exam_submission] = videoList.map((video) => video.videourl);
        
        // Check connection status before playing video
        if (videoStore[exam_submission].length > 0) {
          const lastVideoUrl = videoStore[exam_submission][videoStore[exam_submission].length - 1];
          const disconnected = videoDisconnected(lastVideoUrl);
          const offlineOverlay = document.getElementById(`offline-overlay-${exam_submission}`);
          
          if (disconnected && offlineOverlay) {
            offlineOverlay.classList.add("show");
            // Update the message sidebar status badge to "Offline"
            updateMessageCardStatus(exam_submission, "offline");
          } else if (offlineOverlay) {
            offlineOverlay.classList.remove("show");
            // Update the message sidebar status badge to "Started"
            updateMessageCardStatus(exam_submission, "started");
          }
        }
        
        playVideoAtIndex(
          exam_submission,
          videoStore[exam_submission].length - 1,
        );
      },
    });
  }
}

function updateSidebarMessages() {
  frappe.call({
    method: "exampro.www.proctor.get_latest_messages",
    callback: (data) => {
      if (!data.message) return;
      
      data.message.forEach(msg => {
        const card = document.querySelector(`.message-card[data-submission="${msg.exam_submission}"]`);
        if (!card) return;

        const messageText = card.querySelector('.message-text');
        const statusBadge = card.querySelector('.status-badge');
        
        // Get last known message for this candidate
        const lastMessage = lastKnownMessages[msg.exam_submission];
        
        // Check if either message or status has changed
        const messageChanged = !lastMessage || lastMessage.message !== msg.message;
        const statusChanged = !lastMessage || lastMessage.status !== msg.status;
        
        if (messageChanged || statusChanged) {
          // Update the message
          messageText.textContent = msg.message;
          
          // Update status
          if (statusBadge) {
            statusBadge.className = `badge status-badge status-${msg.status.toLowerCase()}`;
            statusBadge.textContent = msg.status;
          }
          
          // Remove existing animation class if present
          card.classList.remove('has-new-message');
          
          // Trigger reflow to restart animation
          void card.offsetWidth;
          
          // Add animation class
          card.classList.add('has-new-message');
          
          // Remove animation class after animation completes
          setTimeout(() => {
            if (card.classList.contains('has-new-message')) {
              card.classList.remove('has-new-message');
            }
          }, 2000);
          
          // Update cache
          lastKnownMessages[msg.exam_submission] = {
            message: msg.message,
            status: msg.status,
            timestamp: new Date()
          };
        }
      });
    }
  });
}

frappe.ready(() => {
  // Add click handlers for sidebar message cards
  document.querySelectorAll('.message-card').forEach(card => {
    card.addEventListener('click', openChatModal);
    card.style.cursor = 'pointer';
  });

  setInterval(function () {
    updateVideoList();
    updateSidebarMessages();
    // Re-attach click handlers to any new cards
    document.querySelectorAll('.message-card').forEach(card => {
      card.removeEventListener('click', openChatModal);
      card.addEventListener('click', openChatModal);
      card.style.cursor = 'pointer';
    });
  }, 5000); // 5 seconds
  
  // frappe.realtime.on('newproctorvideo', (data) => {
  //     videoStore[data.exam_submission].push(data.url);
  // });

  // frappe.realtime.on('newproctormsg', (data) => {
  //     convertedTime = timeAgo(data.creation);
  //     if (data.exam_submission === activeChat) {
  //         addChatBubble(convertedTime, data.message, data.type_of_message)
  //     }
  // });

  // chatModal controls
  // Handle send button click event
  $("#proc-send-message").click(function () {
    var message = $("#chat-input").val();
    sendProcMessage(message);
    $("#chat-input").val("");
  });

  // Handle enter key press event
  $("#chat-input").keypress(function (e) {
    if (e.which == 13) {
      var message = $("#chat-input").val();
      sendProcMessage(message);
      $("#chat-input").val("");
    }
  });

  $("#terminateExam").click(function () {
    var result = prompt(
      "Do you want to terminate this candidate's exam? Confirm by typing `Terminate Exam`. This step is irreversable.",
    );
    if (result === "Terminate Exam") {
      frappe.call({
        method:
          "exampro.exam_pro.doctype.exam_submission.exam_submission.terminate_exam",
        type: "POST",
        args: {
          exam_submission: activeChat,
        },
        callback: (data) => {
          let confrm = confirm("Exam terminated!");
          if (confrm) {
            window.location.reload();
          }
        },
      });
    } else {
      alert("Invalid input given.");
    }
  });

  // Function to send a message
  function sendProcMessage(message) {
    if (message.trim() !== "") {
      frappe.call({
        method:
          "exampro.exam_pro.doctype.exam_submission.exam_submission.post_exam_message",
        type: "POST",
        args: {
          exam_submission: activeChat,
          message: message,
          type_of_message: "General",
          from: "Proctor"
        },
        callback: (data) => {
          console.log(data);
        },
      });
    }
  }

  $("#chatModal").on("hidden.bs.modal", function () {
    activeChat = "";
  });


  var $examStatus = $('.examstatus');

  if ($examStatus.text() === 'Started') {
      $examStatus.removeClass();
      $examStatus.addClass('badge status-badge status-started');
  } else if ($examStatus.text() === 'Terminated') {
      $examStatus.removeClass();
      $examStatus.addClass('badge status-badge status-terminated');
  }

});


// Message Card Hover - Video Card Highlight Effect
document.addEventListener('DOMContentLoaded', function() {
    
    // Get all message cards
    const messageCards = document.querySelectorAll('.message-card');
    
    // Function to add highlight effect to video card
    function highlightVideoCard(submissionId) {
        const videoContainer = document.querySelector(`[data-videoid="${submissionId}"]`);
        if (videoContainer) {
            const videoCard = videoContainer.closest('.card');
            if (videoCard) {
                videoCard.classList.add('video-card-highlighted');
                
                // Add a subtle animation
                videoCard.style.transform = 'scale(1.02)';
                videoCard.style.transition = 'all 0.3s ease';
                videoCard.style.boxShadow = '0 4px 20px rgba(0, 123, 255, 0.3)';
                videoCard.style.borderColor = '#007bff';
            }
        }
    }
    
    // Function to remove highlight effect from video card
    function removeHighlightVideoCard(submissionId) {
        const videoContainer = document.querySelector(`[data-videoid="${submissionId}"]`);
        if (videoContainer) {
            const videoCard = videoContainer.closest('.card');
            if (videoCard) {
                videoCard.classList.remove('video-card-highlighted');
                
                // Remove the animation
                videoCard.style.transform = 'scale(1)';
                videoCard.style.boxShadow = '';
                videoCard.style.borderColor = '';
            }
        }
    }
    
    // Add event listeners to message cards
    messageCards.forEach(messageCard => {
        const submissionId = messageCard.getAttribute('data-submission');
        
        if (submissionId) {
            // Mouse enter event
            messageCard.addEventListener('mouseenter', function() {
                highlightVideoCard(submissionId);
            });
            
            // Mouse leave event
            messageCard.addEventListener('mouseleave', function() {
                removeHighlightVideoCard(submissionId);
            });
        }
    });
    
    // Optional: Add reverse effect - highlight message card when hovering over video card
    const videoCards = document.querySelectorAll('.video-card');
    
    videoCards.forEach(videoCard => {
        const videoContainer = videoCard.querySelector('[data-videoid]');
        if (videoContainer) {
            const videoId = videoContainer.getAttribute('data-videoid');
            
            // Mouse enter event on video card
            videoCard.addEventListener('mouseenter', function() {
                const messageCard = document.querySelector(`[data-submission="${videoId}"]`);
                if (messageCard) {
                    messageCard.classList.add('message-card-highlighted');
                    messageCard.style.backgroundColor = 'rgba(0, 123, 255, 0.1)';
                    messageCard.style.borderLeftColor = '#007bff';
                    messageCard.style.borderLeftWidth = '4px';
                    messageCard.style.transition = 'all 0.3s ease';
                }
            });
            
            // Mouse leave event on video card
            videoCard.addEventListener('mouseleave', function() {
                const messageCard = document.querySelector(`[data-submission="${videoId}"]`);
                if (messageCard) {
                    messageCard.classList.remove('message-card-highlighted');
                    messageCard.style.backgroundColor = '';
                    messageCard.style.borderLeftColor = '#e0e0e0';
                    messageCard.style.borderLeftWidth = '4px';
                }
            });
        }
    });
});

// Function to toggle offline status when button is clicked
function toggleOfflineStatus(exam_submission) {
    const offlineOverlay = document.getElementById(`offline-overlay-${exam_submission}`);
    
    if (offlineOverlay) {
        // If already showing, then hide it (user manually reconnecting)
        if (offlineOverlay.classList.contains('show')) {
            offlineOverlay.classList.remove('show');
            
            // Mark container as live
            const videoContainer = document.querySelector(`.video-container[data-videoid="${exam_submission}"]`);
            if (videoContainer) {
                videoContainer.setAttribute("data-islive", "1");
                
                // Update the message sidebar status badge to "Started"
                updateMessageCardStatus(exam_submission, "started");
                
                // Refresh video (optional)
                playLastVideo.call(videoContainer.querySelector('.goLive'));
            }
        }
    }
}

// CSS styles to be added to the existing stylesheet
const additionalStyles = `
    /* Video card highlight effect */
    .video-card-highlighted {
        border: 2px solid #007bff !important;
        box-shadow: 0 4px 20px rgba(0, 123, 255, 0.3) !important;
        transform: scale(1.02) !important;
        transition: all 0.3s ease !important;
        z-index: 10 !important;
        position: relative !important;
    }
    
    /* Message card highlight effect */
    .message-card-highlighted {
        background-color: rgba(0, 123, 255, 0.1) !important;
        border-left-color: #007bff !important;
        transition: all 0.3s ease !important;
    }
    
    /* Smooth transitions for all cards */
    .message-card, .video-card {
        transition: all 0.3s ease;
    }
    
    /* Optional: Add a glow effect */
    .video-card-highlighted::before {
        content: '';
        position: absolute;
        top: -2px;
        left: -2px;
        right: -2px;
        bottom: -2px;
        background: linear-gradient(45deg, #007bff, #0056b3);
        border-radius: 8px;
        z-index: -1;
        opacity: 0.3;
        filter: blur(6px);
    }
`;

// Function to inject additional CSS styles
function injectStyles() {
    const styleSheet = document.createElement('style');
    styleSheet.textContent = additionalStyles;
    document.head.appendChild(styleSheet);
}

// Inject styles when DOM is loaded
document.addEventListener('DOMContentLoaded', injectStyles);

/**
 * Updates the status badge in the message sidebar for a specific exam submission
 * @param {string} exam_submission - The exam submission ID
 * @param {string} status - The status to set: 'started', 'offline', 'terminated', etc.
 */
function updateMessageCardStatus(exam_submission, status) {
    const messageCard = document.querySelector(`.message-card[data-submission="${exam_submission}"]`);
    
    if (messageCard) {
        const statusBadge = messageCard.querySelector('.status-badge');
        
        if (statusBadge) {
            // Remove all status classes
            statusBadge.classList.remove('status-started', 'status-offline', 'status-terminated', 'status-registered');
            
            // Add appropriate status class
            statusBadge.classList.add(`status-${status.toLowerCase()}`);
            
            // Update the text content (capitalize first letter for display)
            statusBadge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            
            // Store the status in the data attribute for future reference
            statusBadge.setAttribute('data-submission-status', status.charAt(0).toUpperCase() + status.slice(1));
            
            // Add a subtle animation to highlight the change
            messageCard.classList.remove('has-new-message');
            void messageCard.offsetWidth; // Force reflow to restart animation
            messageCard.classList.add('has-new-message');
            
            // Remove animation class after it completes
            setTimeout(() => {
                messageCard.classList.remove('has-new-message');
            }, 2000);
        }
    }
}