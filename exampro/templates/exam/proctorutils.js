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
  let videoId;
  
  // Check if this is a button or the video itself
  if (this.classList.contains('togglePlayBtn')) {
    // If it's the button, get ID from its ID attribute
    videoId = this.id.replace('togglePlayBtn-', '');
  } else if (this.classList.contains('video')) {
    // If it's the video, get ID directly
    videoId = this.getAttribute('data-videoid');
  } else {
    // Exit if we can't determine videoId
    return;
  }
  
  // Find the video element by ID
  const video = document.getElementById(videoId);
  
  // Exit if no video found
  if (!video) return;
  
  if (video.paused || video.ended) {
    video.play();
  } else {
    video.pause();
  }
}

function updatetogglePlayBtn() {
  // Get video ID from the video element's data attribute
  const videoId = this.getAttribute("data-videoid");
  
  // Use ID-specific selector to find the play button
  const togglePlayBtn = document.getElementById(`togglePlayBtn-${videoId}`);
  
  // Update the button based on video state
  if (togglePlayBtn) {
    togglePlayBtn.innerHTML = this.paused ? 
      '<i class="bi bi-play-fill"></i>' : 
      '<i class="bi bi-pause-fill"></i>';
  }
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

/**
 * Check if a video has been disconnected based on its timestamp
 * @param {string} videoURL - The URL of the video to check
 * @returns {boolean} - True if the video is considered disconnected
 */
function videoDisconnected(videoURL) {
  if (!videoURL) return true;
  
  try {
    const url = new URL(videoURL);
    const filenameWithExtension = url.pathname.split("/").pop();
    const filename = filenameWithExtension.split(".")[0];
    
    // Get timestamp from filename (assumed to be a unix timestamp)
    const videoTimestamp = parseInt(filename, 10) * 1000;
    const currentTime = new Date().getTime();
    
    // If the video is more than 30 seconds old, consider it disconnected
    return (currentTime - videoTimestamp) > 30000; // 30 seconds in milliseconds
  } catch (error) {
    console.error("Error checking video connection status:", error);
    return true; // Assume disconnected on error
  }
}

function handleProgress() {
  // Get video ID from the video element
  const exam_submission = this.getAttribute("data-videoid");
  if (!exam_submission) return;
  
  // Find the timestamp element using ID-specific selector
  let fTS = document.getElementById(`fileTimeStamp-${exam_submission}`);
  
  // Find the video container using ID-specific selector
  const videoContainer = document.querySelector(`.video-container[data-videoid="${exam_submission}"]`);
  if (!videoContainer) return;
  
  let islive = videoContainer.getAttribute("data-islive");

  // Exit early if required elements are not found
  if (!fTS || !videoStore[exam_submission]) return;
  
  // Reference to the video element (this)
  const video = this;
  
  // Show timestamp only if current video is not live
  if (islive === "0" && 
      currentVideoIndex[exam_submission] !== undefined && 
      videoStore[exam_submission] && 
      videoStore[exam_submission][currentVideoIndex[exam_submission]]) {
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
  // Get the exam submission ID from the element's ID
  const exam_submission = this.getAttribute("data-videoid");
  if (!exam_submission) return;
  
  playVideoAtIndex(exam_submission, this.value);
}

function playNextVideo() {
  // Get the exam submission ID from the element's ID
  const exam_submission = this.getAttribute("data-videoid");
  if (!exam_submission) {
    const buttonId = this.id;
    if (buttonId && buttonId.startsWith('skipFwd-')) {
      const videoId = buttonId.replace('skipFwd-', '');
      playVideoAtIndex(videoId, currentVideoIndex[videoId] + 1);
    }
    return;
  }
  
  playVideoAtIndex(exam_submission, currentVideoIndex[exam_submission] + 1);
}

function playLastVideo() {
  // Get the exam submission ID from the element's ID
  const exam_submission = this.getAttribute("data-videoid");
  if (!exam_submission) {
    const buttonId = this.id;
    if (buttonId && buttonId.startsWith('goLive-')) {
      const videoId = buttonId.replace('goLive-', '');
      if (!videoStore[videoId] || !videoStore[videoId].length) return;
      
      // Clear the timestamp
      const fTS = document.getElementById(`fileTimeStamp-${videoId}`);
      if (fTS) fTS.innerText = "";
      
      playVideoAtIndex(videoId, videoStore[videoId].length - 1);
    }
    return;
  }
  
  // Clear the timestamp using ID-specific selector
  const fTS = document.getElementById(`fileTimeStamp-${exam_submission}`);
  if (fTS) fTS.innerText = "";
  
  playVideoAtIndex(exam_submission, videoStore[exam_submission].length - 1);
}

function playPreviousVideo() {
  // Get the exam submission ID from the element's ID
  const exam_submission = this.getAttribute("data-videoid");
  if (!exam_submission) {
    const buttonId = this.id;
    if (buttonId && buttonId.startsWith('skipBack-')) {
      const videoId = buttonId.replace('skipBack-', '');
      playVideoAtIndex(videoId, currentVideoIndex[videoId] - 1);
    }
    return;
  }
  
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
    candName = this.querySelector(".card-body .card-subtitle").textContent;
    const videoContainer = document.querySelector(`.video-container[data-videoid="${videoId}"]`);
    if (!videoContainer) {
      console.error(`Video container not found for submission: ${videoId}`);
      return;
    }
    
    const video = videoContainer.querySelector("video");
    if (!video) {
      console.error(`Video element not found for submission: ${videoId}`);
      return;
    }
    
    videoSrc = video.src;
    
    // Check if the exam has been submitted
    if (videoContainer.getAttribute("data-submission-status") === "Submitted") {
      // Don't open modal if submission status is "Submitted"
      console.log("Chat disabled: Exam already submitted");
      return;
    }
    
  } else {
    // Called from video controls button with ID-specific selector
    videoId = this.getAttribute("data-videoid");
    if (!videoId) {
      console.error("No data-videoid attribute found on button");
      return;
    }
    
    // Find the video container using the videoId
    const videoContainer = document.querySelector(`.video-container[data-videoid="${videoId}"]`);
    if (!videoContainer) {
      console.error(`Video container not found for submission: ${videoId}`);
      return;
    }
    
    // Get the video element
    const video = document.getElementById(videoId);
    if (!video) {
      console.error(`Video element not found with ID: ${videoId}`);
      return;
    }
    
    videoSrc = video.src;
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
  
  // Get the modal element
  const chatModal = document.getElementById("chatModal");
  
  // Show the modal using Bootstrap 5 syntax (if available)
  if (bootstrap && bootstrap.Modal) {
    const modalInstance = new bootstrap.Modal(chatModal);
    modalInstance.show();
  } else {
    // Fallback to jQuery method for older Bootstrap versions
    try {
      $("#chatModal").modal("show");
    } catch (error) {
      console.error("Error showing modal:", error);
      alert("Could not open chat. Please refresh the page and try again.");
      return;
    }
  }
  
  $("#candidateName").text(candName);
  activeChat = videoId;
  $("#chat-messages").empty();
  existingMessages[videoId] = [];
  
  console.log(`Chat modal opened for: ${candName} (${videoId})`);

  setInterval(function () {
    updateProcMessages(videoId);
  }, 1000); // 1 seconds
}

function onLoanMetaData() {
  // Get video ID directly from the video element
  const exam_submission = this.getAttribute("data-videoid");
  if (!exam_submission) return;
  
  const video = this; // The video element is 'this'
  const videoContainer = document.querySelector(`.video-container[data-videoid="${exam_submission}"]`);
  if (!videoContainer) return;
  
  // Use ID-specific selector for skip forward button
  let skipfwd = document.getElementById(`skipFwd-${exam_submission}`);
  const offlineOverlay = document.getElementById(`offline-overlay-${exam_submission}`);

  if (video.src === "") {
    videoContainer.classList.add("border", "border-primary");
  } else {
    videoContainer.classList.remove("border", "border-primary");
    
    // Check if we have video data for this submission
    if (!videoStore[exam_submission] || !videoStore[exam_submission].length) return;
    
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
      if (skipfwd) skipfwd.disabled = true;
      // check if the last video is 30 sec old
      if (!video.paused) {
        if (!disconnected) {
            videoContainer.setAttribute("data-islive", "1");
          } else {
            videoContainer.setAttribute("data-islive", "0");
        }
      }
    } else {
      if (skipfwd) skipfwd.disabled = false;
      if (!disconnected) {
        videoContainer.setAttribute("data-islive", "0");
      } else {
        videoContainer.setAttribute("data-islive", "0");
      }
    }
  }
}


// Initialize event listeners
function setupVideoEventListeners() {
  // Process all videos
  Array.from(document.getElementsByClassName("video")).forEach(video => {
    const exam_submission = video.getAttribute("data-videoid");
    if (!exam_submission) return;
    
    // Add event listeners to video elements
    video.addEventListener("click", togglePlay);
    video.addEventListener("play", updatetogglePlayBtn);
    video.addEventListener("pause", updatetogglePlayBtn);
    video.addEventListener("timeupdate", handleProgress);
    video.addEventListener("loadedmetadata", onLoanMetaData);
    
    // Add event listeners to control elements using ID-specific selectors
    const togglePlayBtn = document.getElementById(`togglePlayBtn-${exam_submission}`);
    if (togglePlayBtn) togglePlayBtn.addEventListener("click", togglePlay);
    
    const goLiveBtn = document.getElementById(`goLive-${exam_submission}`);
    if (goLiveBtn) goLiveBtn.addEventListener("click", playLastVideo);
    
    const skipBackBtn = document.getElementById(`skipBack-${exam_submission}`);
    if (skipBackBtn) skipBackBtn.addEventListener("click", playPreviousVideo);
    
    const skipFwdBtn = document.getElementById(`skipFwd-${exam_submission}`);
    if (skipFwdBtn) skipFwdBtn.addEventListener("click", playNextVideo);
    
    const chatBtn = document.getElementById(`chat-btn-${exam_submission}`);
    if (chatBtn) {
      // Remove any existing event listeners first to prevent duplicates
      chatBtn.removeEventListener("click", openChatModal);
      chatBtn.addEventListener("click", openChatModal);
      console.log(`Added click listener to chat button for ${exam_submission}`);
    }
  });
  
  // Set up event listeners for message cards in the sidebar
  document.querySelectorAll('.message-card').forEach(card => {
    card.removeEventListener('click', openChatModal);
    card.addEventListener('click', openChatModal);
    card.style.cursor = 'pointer';
  });
}

// Call setup function initially
setupVideoEventListeners();

// Remove the class-based approach to avoid double event binding
// addEventListenerToClass("menu", "click", openChatModal);

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
        if (!vid) return;
        
        // Set data-videoid attribute on video if not already set
        if (!vid.getAttribute('data-videoid')) {
          vid.setAttribute('data-videoid', exam_submission);
        }
        
        let container = document.querySelector(`.video-container[data-videoid="${exam_submission}"]`);
        if (!container) return;
        
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
        
        // Make sure control elements have ID-specific IDs
        updateControlElementIds();
        
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
      
      // Create a set of existing submissions for checking new entries
      const existingSubmissions = new Set(Object.keys(videoStore));
      const newSubmissions = [];
      const missingMessageCards = [];
      
      data.message.forEach(msg => {
        // Check if this is a new submission that doesn't have a video tile yet
        if (!existingSubmissions.has(msg.exam_submission)) {
          newSubmissions.push(msg);
          return;
        }
        
        // Check if message card exists for this submission
        const card = document.querySelector(`.message-card[data-submission="${msg.exam_submission}"]`);
        
        // If the submission has a video tile but no message card, create one
        if (!card) {
          missingMessageCards.push(msg);
          return;
        }

        // Process existing message cards
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
      
      // Process submissions that have video tiles but no message cards
      if (missingMessageCards.length > 0) {
        console.log(`Found ${missingMessageCards.length} submissions missing message cards:`, missingMessageCards);
        addMissingMessageCards(missingMessageCards);
      }
      
      // Process new submissions that need video tiles
      if (newSubmissions.length > 0) {
        console.log(`Found ${newSubmissions.length} new submissions to add:`, newSubmissions);
        addNewVideoTiles(newSubmissions);
      }
    }
  });
}

frappe.ready(() => {
  console.log("Initializing ExamPro Proctor Dashboard");
  
  // Set the timestamp for when we started
  window.dashboardStartTime = new Date();
  
  // Initialize the page components
  updateControlElementIds(); // Set up ID-specific elements
  setupVideoEventListeners(); // Set up event listeners

  // First run of updates
  updateVideoList();
  updateSidebarMessages();
  
  // Set up interval for regular updates
  setInterval(function () {
    // Update existing videos
    updateVideoList();
    
    // Check for new submissions and update sidebar
    updateSidebarMessages();
    
    // Ensure all event listeners are properly set up
    setupVideoEventListeners();
    
    // Setup dynamic observer for new content
    setupDynamicObservers();
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

/**
 * Adds new video tiles and message cards for newly added submissions
 * @param {Array} newSubmissions - Array of new submission objects
 */
function addNewVideoTiles(newSubmissions) {
  if (!newSubmissions || !newSubmissions.length) return;

  // Get the video grid container
  const videoGrid = document.querySelector('.row.mt-4');
  if (!videoGrid) {
    console.error("Could not find video grid container");
    return;
  }
  
  // Get the messages sidebar container
  const messagesSidebar = document.querySelector('.messages-sidebar');
  if (!messagesSidebar) {
    console.error("Could not find messages sidebar container");
    // Continue anyway as we can still add video tiles
  }

  // Create and add new video tiles for each submission
  newSubmissions.forEach(submission => {
    const exam_submission = submission.exam_submission;
    const candidate_name = submission.candidate_name || "Unknown Candidate";
    const message = submission.message || "Exam started";
    const status = submission.status || "registered";
    
    // Check if a video tile already exists for this submission
    const existingTile = document.querySelector(`[data-videoid="${exam_submission}"]`);
    if (existingTile) {
      console.log(`Video tile already exists for ${candidate_name} (${exam_submission}), skipping duplicate creation`);
      return; // Skip to next submission
    }

    // Create column container for video tile
    const colDiv = document.createElement('div');
    colDiv.className = 'col-md-3 col-sm-6 mb-3';

    // Create video card HTML
    colDiv.innerHTML = `
      <div class="card video-card">
        <div class="card-header p-2 d-flex justify-content-between align-items-center">
          <small class="text-truncate me-2">${candidate_name}</small>
        </div>
        <div class="card-body p-0">
          <div class="video-container" data-videoid="${exam_submission}"
              data-candidatename="${candidate_name}" data-islive="0">
            <video class="video" id="${exam_submission}" data-videoid="${exam_submission}" preload="metadata">
              <p>Your browser doesn't support HTML5 video.</p>
            </video>
          </div>
          <!-- Offline Overlay -->
          <div class="offline-overlay" id="offline-overlay-${exam_submission}">
            <div class="offline-button" onclick="toggleOfflineStatus('${exam_submission}')">
              <i class="bi bi-wifi-off"></i>
              <span>Offline</span>
            </div>
          </div>
          <!-- Controls moved below video as centered button group -->
          <div class="video-controls">
            <small class="file-timestamp fileTimeStamp" id="fileTimeStamp-${exam_submission}"></small>
            <button class="controls__button togglePlayBtn" id="togglePlayBtn-${exam_submission}" title="Toggle Play" data-videoid="${exam_submission}">
              <i class="bi bi-play-fill"></i>
            </button>
            <button class="controls__button skipBack" id="skipBack-${exam_submission}" title="Skip back" data-videoid="${exam_submission}">
              <i class="bi bi-rewind-fill"></i>
            </button>
            <button class="controls__button skipFwd" id="skipFwd-${exam_submission}" title="Skip forward" data-videoid="${exam_submission}">
              <i class="bi bi-fast-forward-fill"></i>
            </button>
            <button type="button" class="controls__button chat-btn menu" id="chat-btn-${exam_submission}" title="Chat" data-videoid="${exam_submission}">
              <i class="bi bi-chat-square-text-fill"></i>
            </button>
          </div>
        </div>
      </div>
    `;

    // Add the new column to the grid
    videoGrid.appendChild(colDiv);
    
    // Add a message card to the sidebar if the sidebar exists
    if (messagesSidebar) {
      // Check if a message card for this submission already exists
      const existingCard = document.querySelector(`.message-card[data-submission="${exam_submission}"]`);
      
      if (!existingCard) {
        // Prepare submission data for the message card
        const submissionData = {
          name: exam_submission,
          candidate_name: candidate_name
        };
        
        // Create a new message card using our utility function
        const messageCard = addNewSidebarMessageCard(submissionData);
        
        // Update the status badge if needed
        if (status) {
          const statusBadge = messageCard.querySelector('.status-badge');
          if (statusBadge) {
            statusBadge.className = `status-badge status-${status.toLowerCase()}`;
            statusBadge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
          }
        }
        
        // Update the message text if needed
        if (message) {
          const messageElement = messageCard.querySelector('.card-text.message-text');
          if (messageElement) {
            messageElement.textContent = message;
          }
        }
        
        console.log(`Added new message card for ${candidate_name} (${exam_submission})`);
        
        // Update the last known message for this submission
        lastKnownMessages[exam_submission] = {
          message: message,
          status: status,
          timestamp: new Date()
        };
        
        // Add animation to highlight the new message card
        messageCard.classList.add('has-new-message');
        
        // Remove animation class after animation completes
        setTimeout(() => {
          messageCard.classList.remove('has-new-message');
        }, 2000);
      }
    }
    
    console.log(`Added new video tile for ${candidate_name} (${exam_submission})`);
    
    // Initialize the video controls and fetch videos for this submission
    updateControlElementIds();
    
    // Update the video counter
    const liveCountBadge = document.querySelector('.btn-primary .badge');
    if (liveCountBadge) {
      const currentCount = parseInt(liveCountBadge.textContent) || 0;
      liveCountBadge.textContent = currentCount + 1;
    }
    
    // Fetch videos for this new submission
    fetchVideosForSubmission(exam_submission);
  });
}

/**
 * Fetch videos for a specific exam submission
 */
function fetchVideosForSubmission(exam_submission) {
  frappe.call({
    method: "exampro.exam_pro.doctype.exam_submission.exam_submission.proctor_video_list",
    args: {
      exam_submission: exam_submission,
    },
    callback: (data) => {
      if (!data.message || !data.message.videos) {
        console.error(`No videos found for submission: ${exam_submission}`);
        return;
      }
      
      var vid = document.getElementById(exam_submission);
      if (!vid) return;
      
      let container = document.querySelector(`.video-container[data-videoid="${exam_submission}"]`);
      if (!container) return;
      
      container.classList.remove("hidden");
      
      // Convert API response to an array of objects
      let videoList = Object.entries(data.message.videos).map(
        ([unixtimestamp, videourl]) => {
          return { unixtimestamp: parseInt(unixtimestamp, 10), videourl };
        },
      );
      
      // Sort them
      videoList.sort((a, b) => a.unixtimestamp - b.unixtimestamp);

      videoStore[exam_submission] = videoList.map((video) => video.videourl);
      
      // Check connection status
      if (videoStore[exam_submission].length > 0) {
        const lastVideoUrl = videoStore[exam_submission][videoStore[exam_submission].length - 1];
        const disconnected = videoDisconnected(lastVideoUrl);
        const offlineOverlay = document.getElementById(`offline-overlay-${exam_submission}`);
        
        if (disconnected && offlineOverlay) {
          offlineOverlay.classList.add("show");
          updateMessageCardStatus(exam_submission, "offline");
        } else if (offlineOverlay) {
          offlineOverlay.classList.remove("show");
          updateMessageCardStatus(exam_submission, "started");
        }
      }
      
      // Play the latest video
      if (videoStore[exam_submission] && videoStore[exam_submission].length > 0) {
        playVideoAtIndex(
          exam_submission,
          videoStore[exam_submission].length - 1,
        );
        console.log(`Started playing video for ${exam_submission}`);
      }
    },
  });
}

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

// Function to convert control elements to use ID-specific selectors
function updateControlElementIds() {
    // Find all video containers
    const videoContainers = document.querySelectorAll('.video-container');
    
    videoContainers.forEach(container => {
        const exam_submission = container.getAttribute('data-videoid');
        if (!exam_submission) return;
        
        // Find video element within this container and ensure it has data-videoid attribute
        const video = container.querySelector('video');
        if (video && !video.getAttribute('data-videoid')) {
            video.setAttribute('data-videoid', exam_submission);
        }
        
        // Check if control elements already have proper IDs
        // If IDs are already set correctly in HTML, this will be skipped
        const elements = {
            togglePlayBtn: container.querySelector('.togglePlayBtn'),
            skipBack: container.querySelector('.skipBack'),
            skipFwd: container.querySelector('.skipFwd'),
            goLive: container.querySelector('.goLive'),
            fileTimeStamp: container.querySelector('.fileTimeStamp'),
            chatBtn: container.querySelector('.chat-btn')
        };
        
        // Set ID attributes and data-videoid for each element if needed
        Object.entries(elements).forEach(([key, element]) => {
            if (element) {
                // Set ID if not already set correctly
                const expectedId = `${key === 'chatBtn' ? 'chat-btn' : key}-${exam_submission}`;
                if (element.id !== expectedId) {
                    element.id = expectedId;
                }
                
                // Add data-videoid attribute to all control elements if not present
                if (!element.getAttribute('data-videoid')) {
                    element.setAttribute('data-videoid', exam_submission);
                }
            }
        });
    });
    
    // After updating IDs, set up the event listeners
    setupVideoEventListeners();
}

// Function to set up dynamic observers for new content
function setupDynamicObservers() {
    // Set up mutation observer to watch for new video cards being added
    if (!window.videoGridObserver) {
        const videoGrid = document.querySelector('.row.mt-4');
        if (videoGrid) {
            window.videoGridObserver = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                    if (mutation.type === 'childList' && mutation.addedNodes.length) {
                        // New nodes added to the video grid
                        console.log("New video cards detected, updating controls and listeners");
                        updateControlElementIds();
                        setupVideoEventListeners();
                    }
                }
            });
            
            // Start observing the video grid for added/removed nodes
            window.videoGridObserver.observe(videoGrid, {
                childList: true,
                subtree: false
            });
        }
    }
    
    // Set up mutation observer for message sidebar
    if (!window.sidebarObserver) {
        const messagesSidebar = document.querySelector('.messages-sidebar');
        if (messagesSidebar) {
            window.sidebarObserver = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                    if (mutation.type === 'childList' && mutation.addedNodes.length) {
                        // New messages added to the sidebar
                        console.log("New message cards detected, updating event listeners");
                        document.querySelectorAll('.message-card').forEach(card => {
                            if (!card.hasEventListener) {
                                card.addEventListener('click', openChatModal);
                                card.style.cursor = 'pointer';
                                card.hasEventListener = true;
                            }
                        });
                    }
                }
            });
            
            // Start observing the messages sidebar for added/removed nodes
            window.sidebarObserver.observe(messagesSidebar, {
                childList: true,
                subtree: true
            });
        }
    }
}

// Run both initialization functions when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    injectStyles();
    updateControlElementIds();
    setupDynamicObservers();
});

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

/**
 * Adds a new message card to the sidebar for a new submission
 * @param {Object} submission - The submission object with candidate info
 */
function addNewSidebarMessageCard(submission) {
  console.log("Adding new sidebar message card for:", submission.name);
  
  // Find the message sidebar (try different possible selectors)
  let messageSidebar = document.querySelector(".message-sidebar .messages-container");
  if (!messageSidebar) {
    messageSidebar = document.querySelector(".messages-sidebar");
  }
  if (!messageSidebar) {
    console.error("Message sidebar not found with any selector, cannot add message card");
    return;
  }
  
  // Create a new message card using the exact same structure as in proctor.html
  const messageCard = document.createElement("div");
  messageCard.className = "card mb-2 message-card";
  messageCard.setAttribute("data-submission", submission.name);
  
  // Add inner HTML structure that matches proctor.html exactly
  messageCard.innerHTML = `
    <div class="card-body p-2">
      <div class="d-flex justify-content-between align-items-center mb-1">
        <h6 class="card-subtitle text-muted mb-0">${submission.candidate_name}</h6>
        <span class="badge status-badge status-registered" data-submission-status="Registered">Registered</span>
      </div>
      <p class="card-text message-text mb-0">No messages yet</p>
    </div>
  `;
  
  // Add click event listener
  messageCard.addEventListener('click', openChatModal);
  messageCard.style.cursor = 'pointer';
  
  // Add hover effects
  messageCard.addEventListener('mouseenter', function() {
    // Try multiple selectors to find the video element
    let videoCard = document.querySelector(`.card-body [data-videoid="${submission.name}"]`);
    if (!videoCard) {
      videoCard = document.querySelector(`[data-videoid="${submission.name}"]`);
    }
    
    if (videoCard && videoCard.closest('.card')) {
      const parentCard = videoCard.closest('.card');
      parentCard.classList.add('video-card-highlighted');
      parentCard.style.transform = 'scale(1.02)';
      parentCard.style.transition = 'all 0.3s ease';
      parentCard.style.boxShadow = '0 4px 20px rgba(0, 123, 255, 0.3)';
      parentCard.style.borderColor = '#007bff';
    }
  });
  
  messageCard.addEventListener('mouseleave', function() {
    // Try multiple selectors to find the video element
    let videoCard = document.querySelector(`.card-body [data-videoid="${submission.name}"]`);
    if (!videoCard) {
      videoCard = document.querySelector(`[data-videoid="${submission.name}"]`);
    }
    
    if (videoCard && videoCard.closest('.card')) {
      const parentCard = videoCard.closest('.card');
      parentCard.classList.remove('video-card-highlighted');
      parentCard.style.transform = 'scale(1)';
      parentCard.style.boxShadow = '';
      parentCard.style.borderColor = '';
    }
  });
  
  // Add the card to the sidebar
  messageSidebar.appendChild(messageCard);
  
  // Update the message counter
  const messageCounter = document.querySelector(".message-counter");
  if (messageCounter) {
    const currentCount = parseInt(messageCounter.textContent) || 0;
    messageCounter.textContent = currentCount + 1;
  }
  
  return messageCard;
}

/**
 * Adds message cards for submissions that have video tiles but no message cards
 * @param {Array} submissions - Array of submission objects
 */
function addMissingMessageCards(submissions) {
  if (!submissions || !submissions.length) return;
  
  submissions.forEach(submission => {
    console.log(`Adding missing message card for ${submission.exam_submission}`);
    
    // Prepare submission data in the format expected by addNewSidebarMessageCard
    const submissionData = {
      name: submission.exam_submission,
      candidate_name: submission.candidate_name || "Unknown Candidate"
    };
    
    // Create a new message card for this submission
    const messageCard = addNewSidebarMessageCard(submissionData);
    
    // If the submission has a status, update the card's status badge
    if (submission.status) {
      const statusBadge = messageCard.querySelector('.status-badge');
      if (statusBadge) {
        statusBadge.className = `status-badge status-${submission.status.toLowerCase()}`;
        statusBadge.textContent = submission.status;
      }
    }
    
    // If the submission has a message, update the card's message text
    if (submission.message) {
      const messageElement = messageCard.querySelector('.card-text.message-text');
      if (messageElement) {
        messageElement.textContent = submission.message;
      }
    }
    
    // Update cache
    lastKnownMessages[submission.exam_submission] = {
      message: submission.message || "",
      status: submission.status || "Registered",
      timestamp: new Date()
    };
  });
}