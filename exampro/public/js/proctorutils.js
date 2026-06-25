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
    terminatedCandidates: window.proctorData?.terminatedCandidates || [],
    liveCandidatesCount: window.proctorData?.submissions?.length || 0,
    pendingCandidatesCount: window.proctorData?.pendingCandidates?.length || 0,
    terminatedCandidatesCount: window.proctorData?.terminatedCandidates?.length || 0,
    fullWidth: false,
    
    // Chat modal properties
    showChatModal: false,
    currentChatSubmission: '',
    currentChatCandidate: '',
    currentChatAttentionScore: null,
    chatMessage: '',
    chatUpdateInterval: null,
    
    // Video properties
    videoStore: {},
    videoPlayers: {}, // VideoPlayer instance per submission
    videoBlobStore: {},
    existingMessages: {},
    offlineStatus: {}, // Track offline status for each submission
    
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
        // Skip video processing if video proctoring is disabled
        if (!submission.enable_video_proctoring) {
          console.log(`Video proctoring is disabled for ${submission.name}, skipping video processing`);
          continue;
        }
        
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

        // Push the chunk list into the per-submission VideoPlayer (does not
        // disturb current playback; just keeps the array in sync).
        const player = this.getPlayer(examSubmission);
        if (player) {
          player.setChunks(this.videoStore[examSubmission]);
        }

        if (this._modalVideoPlayer && this.currentChatSubmission === examSubmission) {
          this._modalVideoPlayer.setChunks(this.videoStore[examSubmission]);
        }

        console.log(`Processed ${videoList.length} videos for ${examSubmission}`);
        
        // Check if candidate is offline based on latest video timestamp
        const currentTime = Math.floor(Date.now() / 1000); // Current Unix timestamp
        const wasOffline = this.offlineStatus[examSubmission] || false;
        let isOffline = false;
        
        if (videoList.length > 0) {
          const latestVideoTimestamp = videoList[videoList.length - 1].unixtimestamp;
          const timeDifference = currentTime - latestVideoTimestamp;
          isOffline = timeDifference > 15; // Offline if last video is older than 15 seconds
        } else {
          isOffline = true; // No videos means offline
        }
        
        // Update offline status
        this.offlineStatus[examSubmission] = isOffline;
        
        // Get DOM elements
        const video = document.getElementById(examSubmission);
        const offlineOverlay = document.getElementById(`offline-overlay-${examSubmission}`);
        const videoContainer = document.querySelector(`.video-container[data-videoid="${examSubmission}"]`);
        
        if (isOffline) {
          // Show offline message and disable controls
          if (offlineOverlay) {
            offlineOverlay.classList.add('show');
          }
          if (videoContainer) {
            videoContainer.setAttribute("data-islive", "0");
          }
          if (video) {
            // video.controls = false;
            video.pause();
          }
          console.log(`${examSubmission} is offline - last video older than 15 seconds`);
        } else {
          // Hide offline message and enable controls
          if (offlineOverlay) {
            offlineOverlay.classList.remove('show');
          }
          if (videoContainer) {
            videoContainer.setAttribute("data-islive", "1");
          }
          // if (video) {
          //   video.controls = true;
          // }
          
          // If was previously offline and now online, play the latest video
          if (wasOffline && this.videoStore[examSubmission] && this.videoStore[examSubmission].length > 0) {
            console.log(`${examSubmission} came back online - playing latest video`);
            this.playVideoAtIndex(examSubmission, this.videoStore[examSubmission].length - 1);
          } else if (this.videoStore[examSubmission] && this.videoStore[examSubmission].length > 0) {
            // Only auto-play if the video is not currently playing something
            if (video && (video.paused || video.ended || !video.src)) {
              this.playVideoAtIndex(examSubmission, this.videoStore[examSubmission].length - 1);
            }
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
    
    async updateCandidateLists() {
      try {
        const data = await this.apiCall({
          method: "exampro.www.proctor.get_proctor_candidates",
        });
        if (!data.message) return;

        const live = data.message.live_submissions || [];
        const pending = data.message.pending_candidates || [];
        const terminated = data.message.terminated_candidates || [];

        // Detect newly live candidates (were pending, now started)
        const currentNames = new Set(this.submissions.map(s => s.name));
        const newLive = live.filter(s => !currentNames.has(s.name));

        this.submissions = live;
        this.pendingCandidates = pending;
        this.terminatedCandidates = terminated;

        this.liveCandidatesCount = live.length;
        this.pendingCandidatesCount = pending.length;
        this.terminatedCandidatesCount = terminated.length;

        if (this.currentChatSubmission) {
          const current = live.find(s => s.name === this.currentChatSubmission);
          if (current) this.currentChatAttentionScore = current.attention_score ?? null;
        }

        // Kick off video loading for any newly appeared submissions
        for (const s of newLive) {
          if (!s.enable_video_proctoring) continue;
          try {
            const vdata = await this.apiCall({
              method: "exampro.exam_pro.doctype.exam_submission.exam_submission.proctor_video_list",
              args: { exam_submission: s.name }
            });
            if (vdata.message && vdata.message.videos) {
              this.processVideoData(s.name, vdata.message.videos);
            }
          } catch (e) {
            console.error(`Failed to load videos for new submission ${s.name}:`, e);
          }
        }

        // Re-render feather icons for any new DOM elements
        this.$nextTick(() => {
          if (typeof feather !== 'undefined') feather.replace();
        });
      } catch (error) {
        console.error('Failed to update candidate lists:', error);
      }
    },
    
    // Lazily create a VideoPlayer for the given submission, bound to its
    // per-card DOM elements. Returns null if video proctoring is disabled or
    // the video element isn't in the DOM yet.
    getPlayer(examSubmission) {
      const submission = this.submissions.find(s => s.name === examSubmission);
      if (submission && !submission.enable_video_proctoring) {
        return null;
      }
      if (this.videoPlayers[examSubmission]) {
        return this.videoPlayers[examSubmission];
      }
      const videoEl = document.getElementById(examSubmission);
      if (!videoEl || typeof VideoPlayer === 'undefined') {
        return null;
      }
      const player = new VideoPlayer({
        videoEl,
        skipBackBtn: document.getElementById(`skipBack-${examSubmission}`),
        skipForwardBtn: document.getElementById(`skipFwd-${examSubmission}`),
        playPauseBtn: null, // togglePlay is wired through Alpine for proctoring-disabled check
        goLiveBtn: null,    // playLastVideo is wired through Alpine for same reason
      });
      this.videoPlayers[examSubmission] = player;
      return player;
    },

    notifyProctoringDisabled() {
      if (typeof frappe !== 'undefined' && frappe.show_alert) {
        frappe.show_alert({
          message: 'Video proctoring is disabled for this exam',
          indicator: 'orange'
        });
      } else {
        alert('Video proctoring is disabled for this exam');
      }
    },

    // Video control methods
    togglePlay(examSubmission) {
      const submission = this.submissions.find(s => s.name === examSubmission);
      if (submission && !submission.enable_video_proctoring) {
        this.notifyProctoringDisabled();
        return;
      }
      const player = this.getPlayer(examSubmission);
      if (player) player.togglePlay();
    },

    playVideoAtIndex(examSubmission, index) {
      const player = this.getPlayer(examSubmission);
      if (player) player.playAt(index);
    },

    playNextVideo(examSubmission) {
      const player = this.getPlayer(examSubmission);
      if (player) player.next();
    },

    playPreviousVideo(examSubmission) {
      const player = this.getPlayer(examSubmission);
      if (player) player.prev();
    },

    playLastVideo(examSubmission) {
      const player = this.getPlayer(examSubmission);
      if (player) player.goLive();
    },
    
    toggleOfflineStatus(examSubmission) {
      const offlineOverlay = document.getElementById(`offline-overlay-${examSubmission}`);
      const video = document.getElementById(examSubmission);
      const videoContainer = document.querySelector(`.video-container[data-videoid="${examSubmission}"]`);
      
      if (offlineOverlay) {
        if (offlineOverlay.classList.contains('show')) {
          // Bring back online
          offlineOverlay.classList.remove('show');
          if (videoContainer) {
            videoContainer.setAttribute("data-islive", "1");
          }
          // if (video) {
          //   video.controls = true;
          // }
          this.offlineStatus[examSubmission] = false;
          
          // Play latest video if available
          if (this.videoStore[examSubmission] && this.videoStore[examSubmission].length > 0) {
            this.playVideoAtIndex(examSubmission, this.videoStore[examSubmission].length - 1);
          }
        } else {
          // Mark as offline
          offlineOverlay.classList.add('show');
          if (videoContainer) {
            videoContainer.setAttribute("data-islive", "0");
          }
          if (video) {
            video.controls = false;
            video.pause();
          }
          this.offlineStatus[examSubmission] = true;
        }
      }
    },
    
    // Check if a candidate is currently offline
    isOffline(examSubmission) {
      return this.offlineStatus[examSubmission] || false;
    },
    
    // Chat methods
    openChatModal(submission) {
      console.log('Opening chat modal for:', submission);
      
      // Check if chat is enabled for this submission
      if (!submission.enable_chat) {
        console.log('Chat is disabled for this submission');
        if (typeof frappe !== 'undefined' && frappe.show_alert) {
          frappe.show_alert({
            message: 'Chat is disabled for this exam',
            indicator: 'orange'
          });
        } else {
          alert('Chat is disabled for this exam');
        }
        return;
      }
      
      this.currentChatSubmission = submission.name;
      this.currentChatCandidate = submission.candidate_name;
      this.currentChatAttentionScore = submission.attention_score ?? null;
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
      
      // Reset to Video tab
      const videoTab = document.querySelector('#chatModal .modal-media-tabs .nav-link[href="#modal-tab-video"]');
      const ssTab = document.querySelector('#chatModal .modal-media-tabs .nav-link[href="#modal-tab-screenshots"]');
      const videoPane = document.getElementById('modal-tab-video');
      const ssPane = document.getElementById('modal-tab-screenshots');
      if (videoTab) videoTab.classList.add('active');
      if (ssTab) ssTab.classList.remove('active');
      if (videoPane) { videoPane.classList.add('show', 'active'); }
      if (ssPane) { ssPane.classList.remove('show', 'active'); }

      // Initialize modal VideoPlayer with current chunks
      this.initModalVideoPlayer(submission.name);

      // Load screenshots into the modal
      this.loadModalScreenshots(submission.name);

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

      if (typeof feather !== 'undefined') feather.replace();

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

      // Destroy modal video player
      if (this._modalVideoPlayer) {
        this._modalVideoPlayer.destroy();
        this._modalVideoPlayer = null;
      }
    },

    initModalVideoPlayer(examSubmission) {
      if (this._modalVideoPlayer) {
        this._modalVideoPlayer.destroy();
        this._modalVideoPlayer = null;
      }
      if (typeof VideoPlayer === 'undefined') return;

      this._modalVideoPlayer = new VideoPlayer({
        videoEl: '#modal-player-video',
        prevBtn: '#modal-player-prev',
        nextBtn: '#modal-player-next',
        playPauseBtn: '#modal-player-play',
        skipBackBtn: '#modal-player-skip-back',
        skipForwardBtn: '#modal-player-skip-fwd',
        goLiveBtn: '#modal-player-live',
        indexField: '#modal-player-index',
      });

      const chunks = this.videoStore[examSubmission] || [];
      if (chunks.length > 0) {
        this._modalVideoPlayer.loadChunks(chunks);
        this._modalVideoPlayer.goLive();
      }
    },

    async loadModalScreenshots(examSubmission) {
      const gallery = document.getElementById('modal-screenshot-gallery');
      const viewer = document.getElementById('modal-screenshot-viewer');
      const emptyMsg = document.getElementById('modal-screenshot-empty');
      if (!gallery) return;

      gallery.innerHTML = '';
      if (viewer) viewer.classList.add('hidden');
      if (emptyMsg) emptyMsg.classList.remove('hidden');

      try {
        const data = await this.apiCall({
          method: 'exampro.exam_pro.doctype.exam_submission.exam_submission.get_screenshot_list',
          args: { exam_submission: examSubmission },
        });
        const screenshots = (data.message && data.message.screenshots) || [];
        if (screenshots.length === 0) return;

        if (emptyMsg) emptyMsg.classList.add('hidden');

        const self = this;
        screenshots.forEach(function (ss, idx) {
          const thumb = document.createElement('img');
          thumb.src = ss.url;
          thumb.style.cssText = 'height:80px;border-radius:4px;cursor:pointer;border:2px solid transparent;flex-shrink:0;';
          thumb.dataset.index = idx;
          thumb.onclick = function () { self._showModalScreenshot(screenshots, idx); };
          gallery.appendChild(thumb);
        });

        this._showModalScreenshot(screenshots, 0);
      } catch (error) {
        console.error('Failed to load screenshots for modal:', error);
      }
    },

    _showModalScreenshot(list, idx) {
      const img = document.getElementById('modal-screenshot-full');
      const viewer = document.getElementById('modal-screenshot-viewer');
      const indexEl = document.getElementById('modal-ss-index');
      const captionEl = document.getElementById('modal-ss-caption');
      const gallery = document.getElementById('modal-screenshot-gallery');

      if (!img || !viewer) return;
      viewer.classList.remove('hidden');
      img.src = list[idx].url;
      if (indexEl) indexEl.textContent = (idx + 1) + '/' + list.length;

      if (captionEl) {
        const m = String(list[idx].filename).match(/^(\d+)/);
        if (m) {
          const d = new Date(Number(m[1]));
          captionEl.textContent = d.toLocaleString();
        } else {
          captionEl.textContent = list[idx].filename;
        }
      }

      if (gallery) {
        gallery.querySelectorAll('img').forEach(function (t, i) {
          t.style.borderColor = i === idx ? '#0d6efd' : 'transparent';
        });
      }

      const self = this;
      const prevBtn = document.getElementById('modal-ss-prev');
      const nextBtn = document.getElementById('modal-ss-next');
      if (prevBtn) prevBtn.onclick = function () { if (idx > 0) self._showModalScreenshot(list, idx - 1); };
      if (nextBtn) nextBtn.onclick = function () { if (idx < list.length - 1) self._showModalScreenshot(list, idx + 1); };
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

        // Fetch immediately so the message appears without waiting for the next poll
        await this.updateChatMessages(this.currentChatSubmission);
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
      setInterval(async () => {
        await this.updateVideoList();
        await this.updateSidebarMessages();
      }, 5000);

      setInterval(async () => {
        await this.updateCandidateLists();
      }, 30000);
    }
  };
}

// Make the proctorApp function globally available
window.proctorApp = proctorApp;