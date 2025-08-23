/**
 * ExamPro Proctor Dashboard - Alpine.js App
 * Modern reactive proctor dashboard with Alpine.js and enhanced API calls
 */

// Alpine.js Proctor App
function proctorApp() {
  return {
    // Data properties
    submissions: window.proctorData?.submissions || [],
    latestMessages: window.proctorData?.latestMessages || [],
    pendingCandidates: window.proctorData?.pendingCandidates || [],
    liveCandidatesCount: window.proctorData?.submissions?.length || 0,
    pendingCandidatesCount: window.proctorData?.pendingCandidates?.length || 0,
    
    // Chat modal properties
    showChatModal: false,
    currentChatSubmission: '',
    currentChatCandidate: '',
    chatMessage: '',
    chatUpdateInterval: null,
    
    // Video properties
    videoStore: {},
    currentVideoIndex: {},
    videoBlobStore: {},
    existingMessages: {},
    
    // Initialize the app
    async init() {
      console.log('Initializing Proctor Dashboard');
      console.log('Initial submissions:', this.submissions);
      console.log('Initial latestMessages:', this.latestMessages);
      
      // Set the timestamp for when we started
      window.dashboardStartTime = new Date();
      
      // Set up Bootstrap modal event listeners
      const modalElement = document.getElementById('chatModal');
      if (modalElement) {
        modalElement.addEventListener('hidden.bs.modal', () => {
          this.showChatModal = false;
          this.currentChatSubmission = '';
          this.currentChatCandidate = '';
          
          // Clear the chat update interval
          if (this.chatUpdateInterval) {
            clearInterval(this.chatUpdateInterval);
            this.chatUpdateInterval = null;
          }
        });
      }
      
      // Initialize components
      this.setupVideoEventListeners();
      this.startUpdateIntervals();
      
      // Initial data load
      await this.updateVideoList();
      await this.updateSidebarMessages();
      this.updateCandidateCounts();
    },
    
    // API call wrapper using authApiCall
    async apiCall(options) {
      try {
        return await authApiCall(options);
      } catch (error) {
        console.error('API call failed:', error);
        if (typeof frappe !== 'undefined' && frappe.show_alert) {
          frappe.show_alert({
            message: 'API call failed: ' + error.message,
            indicator: 'red'
          });
        }
        throw error;
      }
    },
    
    // Update video list from server
    async updateVideoList() {
      for (const submission of this.submissions) {
        try {
          const data = await this.apiCall({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.proctor_video_list",
            args: { exam_submission: submission.name }
          });
          
          if (data.message && data.message.videos) {
            this.processVideoData(submission.name, data.message.videos);
          }
        } catch (error) {
          console.error(`Failed to load videos for ${submission.name}:`, error);
        }
      }
    },
    
    // Process video data
    processVideoData(examSubmission, videos) {
      try {
        if (!videos || typeof videos !== 'object') {
          console.log('No videos data available for', examSubmission);
          return;
        }
        
        // Convert API response to an array of objects
        let videoList = Object.entries(videos).map(([unixtimestamp, videourl]) => {
          return { unixtimestamp: parseInt(unixtimestamp, 10), videourl };
        });
        
        // Sort them by timestamp
        videoList.sort((a, b) => a.unixtimestamp - b.unixtimestamp);
        this.videoStore[examSubmission] = videoList.map((video) => video.videourl);
        
        console.log(`Processed ${videoList.length} videos for ${examSubmission}`);
        
        // Play the latest video if available and not currently playing
        if (this.videoStore[examSubmission] && this.videoStore[examSubmission].length > 0) {
          const video = document.getElementById(examSubmission);
          // Only auto-play if the video is not currently playing something
          if (video && (video.paused || video.ended || !video.src)) {
            this.playVideoAtIndex(examSubmission, this.videoStore[examSubmission].length - 1);
          }
        }
      } catch (error) {
        console.error('Error processing video data for', examSubmission, error);
      }
    },
    
    // Update sidebar messages
    async updateSidebarMessages() {
      try {
        const data = await this.apiCall({
          method: "exampro.www.proctor.get_latest_messages"
        });
        
        if (data.message) {
          this.latestMessages = data.message;
        }
      } catch (error) {
        console.error('Failed to update sidebar messages:', error);
      }
    },
    
    // Update candidate counts
    updateCandidateCounts() {
      this.liveCandidatesCount = this.submissions.length;
      this.pendingCandidatesCount = this.pendingCandidates.length;
    },
    
    // Video control methods
    togglePlay(examSubmission) {
      const video = document.getElementById(examSubmission);
      if (video) {
        if (video.paused || video.ended) {
          video.play().catch(error => {
            if (error.name === 'AbortError') {
              console.log('Video play was aborted, which is normal when switching videos quickly');
            } else if (error.name === 'NotAllowedError') {
              console.log('Video autoplay not allowed, user interaction required');
            } else {
              console.error('Error playing video:', error);
            }
          });
        } else {
          video.pause();
        }
      }
    },
    
    playVideoAtIndex(examSubmission, index) {
      this.currentVideoIndex[examSubmission] = index;
      const vid = document.getElementById(examSubmission);
      
      if (vid && this.videoStore[examSubmission] && this.videoStore[examSubmission][index]) {
        // Pause and abort any current loading
        vid.pause();
        
        // Check if the source is different to avoid unnecessary reloads
        const newSrc = this.videoStore[examSubmission][index];
        if (vid.src !== newSrc) {
          vid.src = newSrc;
          
          // Handle loading with proper error handling
          const loadVideo = async () => {
            try {
              vid.load();
              await vid.play();
            } catch (error) {
              if (error.name === 'AbortError') {
                console.log('Video loading was aborted, which is normal when switching videos quickly');
              } else if (error.name === 'NotAllowedError') {
                console.log('Video autoplay not allowed, user interaction required');
              } else {
                console.error('Error playing video:', error);
              }
            }
          };
          
          loadVideo();
        } else {
          // Same source, just play
          vid.play().catch(error => {
            if (error.name !== 'AbortError') {
              console.error('Error playing video:', error);
            }
          });
        }
      }
    },
    
    playNextVideo(examSubmission) {
      if (!this.videoStore[examSubmission] || this.videoStore[examSubmission].length === 0) {
        console.log('No videos available for', examSubmission);
        return;
      }
      
      const currentIndex = this.currentVideoIndex[examSubmission] || 0;
      const nextIndex = currentIndex + 1;
      
      if (nextIndex < this.videoStore[examSubmission].length) {
        this.playVideoAtIndex(examSubmission, nextIndex);
      } else {
        console.log('Already at the last video for', examSubmission);
      }
    },
    
    playPreviousVideo(examSubmission) {
      if (!this.videoStore[examSubmission] || this.videoStore[examSubmission].length === 0) {
        console.log('No videos available for', examSubmission);
        return;
      }
      
      const currentIndex = this.currentVideoIndex[examSubmission] || 0;
      const prevIndex = Math.max(0, currentIndex - 1);
      
      if (prevIndex !== currentIndex) {
        this.playVideoAtIndex(examSubmission, prevIndex);
      } else {
        console.log('Already at the first video for', examSubmission);
      }
    },
    
    playLastVideo(examSubmission) {
      if (this.videoStore[examSubmission] && this.videoStore[examSubmission].length > 0) {
        this.playVideoAtIndex(examSubmission, this.videoStore[examSubmission].length - 1);
      } else {
        console.log('No videos available for', examSubmission);
      }
    },
    
    toggleOfflineStatus(examSubmission) {
      const offlineOverlay = document.getElementById(`offline-overlay-${examSubmission}`);
      if (offlineOverlay) {
        if (offlineOverlay.classList.contains('show')) {
          offlineOverlay.classList.remove('show');
          const videoContainer = document.querySelector(`.video-container[data-videoid="${examSubmission}"]`);
          if (videoContainer) {
            videoContainer.setAttribute("data-islive", "1");
          }
        }
      }
    },
    
    // Chat methods
    openChatModal(submission) {
      console.log('Opening chat modal for:', submission);
      this.currentChatSubmission = submission.name;
      this.currentChatCandidate = submission.candidate_name;
      this.chatMessage = '';
      
      // Clear existing messages and reset
      const chatMessages = document.getElementById('chat-messages');
      if (chatMessages) {
        chatMessages.innerHTML = '';
      }
      this.existingMessages[submission.name] = [];
      
      // Clear any existing interval
      if (this.chatUpdateInterval) {
        clearInterval(this.chatUpdateInterval);
      }
      
      // Set up interval for updating messages
      this.chatUpdateInterval = setInterval(() => {
        if (this.currentChatSubmission === submission.name) {
          this.updateChatMessages(submission.name);
        }
      }, 1000);
      
      // Set up video source in modal
      const video = document.getElementById(submission.name);
      const modalVideo = document.getElementById('modalVideoElement');
      if (video && modalVideo && video.src) {
        modalVideo.src = video.src;
      }
      
      // Show modal using Bootstrap's modal API
      const modalElement = document.getElementById('chatModal');
      if (modalElement) {
        // Use Bootstrap 5 modal API
        let modalInstance;
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
          modalInstance = new bootstrap.Modal(modalElement);
          modalInstance.show();
        } else if (typeof $ !== 'undefined') {
          // Fallback to jQuery
          $('#chatModal').modal('show');
        }
        this.showChatModal = true;
      }
      
      // Load initial messages
      this.updateChatMessages(submission.name);
    },
    
    closeChatModal() {
      // Hide modal using Bootstrap's modal API
      const modalElement = document.getElementById('chatModal');
      if (modalElement) {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
          const modalInstance = bootstrap.Modal.getInstance(modalElement);
          if (modalInstance) {
            modalInstance.hide();
          }
        } else if (typeof $ !== 'undefined') {
          // Fallback to jQuery
          $('#chatModal').modal('hide');
        }
      }
      
      this.showChatModal = false;
      this.currentChatSubmission = '';
      this.currentChatCandidate = '';
      
      // Clear the chat update interval
      if (this.chatUpdateInterval) {
        clearInterval(this.chatUpdateInterval);
        this.chatUpdateInterval = null;
      }
    },
    
    async updateChatMessages(examSubmission) {
      try {
        const data = await this.apiCall({
          method: "exampro.exam_pro.doctype.exam_submission.exam_submission.exam_messages",
          args: { exam_submission: examSubmission }
        });
        
        if (data.message && data.message.messages) {
          const messages = data.message.messages;
          
          messages.forEach(chatmsg => {
            if (!this.existingMessages[examSubmission]) {
              this.existingMessages[examSubmission] = [];
            }
            
            if (!this.existingMessages[examSubmission].includes(chatmsg.creation)) {
              const convertedTime = this.timeAgo(chatmsg.creation);
              this.appendMessage(convertedTime, chatmsg.message, chatmsg.from);
              this.existingMessages[examSubmission].push(chatmsg.creation);
            }
          });
        }
      } catch (error) {
        console.error('Failed to update chat messages:', error);
      }
    },
    
    async sendMessage() {
      if (!this.chatMessage.trim()) return;
      
      const message = this.chatMessage.trim();
      this.chatMessage = '';
      
      try {
        // Add message immediately to UI
        const currentTime = new Date().toISOString();
        this.appendMessage(this.timeAgo(currentTime), message, "Proctor");
        
        // Send to server
        await this.apiCall({
          method: "exampro.exam_pro.doctype.exam_submission.exam_submission.post_exam_message",
          type: "POST",
          args: {
            exam_submission: this.currentChatSubmission,
            message: message,
            type_of_message: "General",
            from: "Proctor"
          }
        });
        
        // Auto-scroll to bottom
        if (typeof autoScrollToBottom === 'function') {
          autoScrollToBottom();
        }
      } catch (error) {
        console.error('Failed to send message:', error);
      }
    },
    
    async terminateExam() {
      const result = prompt(
        "Do you want to terminate this candidate's exam? Confirm by typing `Terminate Exam`. This step is irreversible."
      );
      
      if (result === "Terminate Exam") {
        try {
          await this.apiCall({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.terminate_exam",
            type: "POST",
            args: { exam_submission: this.currentChatSubmission }
          });
          
          const confrm = confirm("Exam terminated!");
          if (confrm) {
            window.location.reload();
          }
        } catch (error) {
          console.error('Failed to terminate exam:', error);
          alert('Failed to terminate exam: ' + error.message);
        }
      } else {
        alert("Invalid input given.");
      }
    },
    
    // Utility methods
    appendMessage(convertedTime, text, sender) {
      const chatMessages = document.getElementById('chat-messages');
      if (!chatMessages) return;
      
      const messageElement = document.createElement('div');
      messageElement.className = 'd-flex flex-column mb-2';
      
      const timestampElement = document.createElement('div');
      timestampElement.className = sender === 'Candidate' ? 'chat-timestamp' : 'chat-timestamp-right';
      timestampElement.textContent = convertedTime;
      
      const contentElement = document.createElement('div');
      contentElement.className = `chat-bubble ${sender === 'Candidate' ? 'chat-left' : 'chat-right'}`;
      contentElement.textContent = text;
      
      messageElement.appendChild(timestampElement);
      messageElement.appendChild(contentElement);
      chatMessages.appendChild(messageElement);
      
      // Auto-scroll
      setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }, 100);
    },
    
    timeAgo(timestamp) {
      // Use the existing timeAgo function from examutils.js if available
      if (typeof timeAgo === 'function' && window.timeAgo !== this.timeAgo) {
        return window.timeAgo(timestamp);
      }
      
      const currentTime = new Date();
      const providedTime = new Date(timestamp);
      const timeDifference = currentTime - providedTime;
      const minutesDifference = Math.floor(timeDifference / (1000 * 60));
      
      if (minutesDifference < 1) return 'Just now';
      if (minutesDifference === 1) return '1 minute ago';
      if (minutesDifference < 60) return minutesDifference + ' minutes ago';
      if (minutesDifference < 120) return '1 hour ago';
      if (minutesDifference < 1440) return Math.floor(minutesDifference / 60) + ' hours ago';
      if (minutesDifference < 2880) return '1 day ago';
      return Math.floor(minutesDifference / 1440) + ' days ago';
    },
    
    setupVideoEventListeners() {
      // Set up video event listeners using existing methods
      // This will be called after DOM is ready
      this.$nextTick(() => {
        // Initialize video controls and event listeners
        if (typeof setupVideoEventListeners === 'function') {
          setupVideoEventListeners();
        }
      });
    },
    
    startUpdateIntervals() {
      // Set up periodic updates
      setInterval(async () => {
        await this.updateVideoList();
        await this.updateSidebarMessages();
        this.updateCandidateCounts();
      }, 5000); // Update every 5 seconds
    }
  };
}

// Make the proctorApp function globally available
window.proctorApp = proctorApp;