function proctorArchiveApp() {
  return {
    submissions: window.archiveData?.submissions || [],
    latestMessages: window.archiveData?.latestMessages || [],
    fullWidth: false,

    currentPage: 1,
    pageSize: 12,

    currentSubmission: '',
    currentCandidate: '',
    currentAttentionScore: null,
    currentStatus: '',

    videoStore: {},
    videoPlayers: {},
    existingMessages: {},

    _modalVideoPlayer: null,
    _gazeData: null,
    _gazeRendered: false,

    get totalPages() {
      return Math.max(1, Math.ceil(this.submissions.length / this.pageSize));
    },

    get paginatedSubmissions() {
      var start = (this.currentPage - 1) * this.pageSize;
      return this.submissions.slice(start, start + this.pageSize);
    },

    async init() {
      await this.updateVideoList(this.paginatedSubmissions);

      this.$nextTick(function () {
        if (typeof feather !== 'undefined') feather.replace();
      });
    },

    async goToPage(page) {
      if (page < 1 || page > this.totalPages) return;
      this.currentPage = page;
      await this.updateVideoList(this.paginatedSubmissions);
      this.$nextTick(function () {
        if (typeof feather !== 'undefined') feather.replace();
      });
    },

    nextPage() {
      this.goToPage(this.currentPage + 1);
    },

    prevPage() {
      this.goToPage(this.currentPage - 1);
    },

    async apiCall(options) {
      try {
        return await authApiCall(options);
      } catch (error) {
        console.error('API call failed:', error);
        throw error;
      }
    },

    getSubmissionScore(name) {
      var sub = this.submissions.find(function (s) { return s.name === name; });
      return sub ? sub.attention_score : null;
    },

    async updateVideoList(submissionList) {
      var list = submissionList || this.paginatedSubmissions;
      for (var i = 0; i < list.length; i++) {
        var submission = list[i];
        if (!submission.enable_video_proctoring) continue;
        if (this.videoStore[submission.name]) continue;

        try {
          var data = await this.apiCall({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.proctor_video_list",
            args: { exam_submission: submission.name }
          });

          if (data.message && data.message.videos) {
            this.processVideoData(submission.name, data.message.videos);
          }
        } catch (error) {
          console.error('Failed to load videos for ' + submission.name + ':', error);
        }
      }
    },

    processVideoData(examSubmission, videos) {
      if (!videos || typeof videos !== 'object') return;

      var videoList = Object.entries(videos).map(function (entry) {
        return { unixtimestamp: parseInt(entry[0], 10), videourl: entry[1] };
      });
      videoList.sort(function (a, b) { return a.unixtimestamp - b.unixtimestamp; });
      this.videoStore[examSubmission] = videoList.map(function (v) { return v.videourl; });

      var player = this.getPlayer(examSubmission);
      if (player) {
        player.setChunks(this.videoStore[examSubmission]);
      }

      if (this._modalVideoPlayer && this.currentSubmission === examSubmission) {
        this._modalVideoPlayer.setChunks(this.videoStore[examSubmission]);
      }

      var video = document.getElementById(examSubmission);
      if (video && (video.paused || video.ended || !video.src) && this.videoStore[examSubmission].length > 0) {
        this.playVideoAtIndex(examSubmission, 0);
      }
    },

    getPlayer(examSubmission) {
      var submission = this.submissions.find(function (s) { return s.name === examSubmission; });
      if (submission && !submission.enable_video_proctoring) return null;
      if (this.videoPlayers[examSubmission]) return this.videoPlayers[examSubmission];

      var videoEl = document.getElementById(examSubmission);
      if (!videoEl || typeof VideoPlayer === 'undefined') return null;

      var player = new VideoPlayer({
        videoEl: videoEl,
        skipBackBtn: document.getElementById('skipBack-' + examSubmission),
        skipForwardBtn: document.getElementById('skipFwd-' + examSubmission),
        playPauseBtn: null,
        goLiveBtn: null,
      });
      this.videoPlayers[examSubmission] = player;
      return player;
    },

    togglePlay(examSubmission) {
      var submission = this.submissions.find(function (s) { return s.name === examSubmission; });
      if (submission && !submission.enable_video_proctoring) return;
      var player = this.getPlayer(examSubmission);
      if (player) player.togglePlay();
    },

    playVideoAtIndex(examSubmission, index) {
      var player = this.getPlayer(examSubmission);
      if (player) player.playAt(index);
    },

    playNextVideo(examSubmission) {
      var player = this.getPlayer(examSubmission);
      if (player) player.next();
    },

    playPreviousVideo(examSubmission) {
      var player = this.getPlayer(examSubmission);
      if (player) player.prev();
    },

    async openModal(submission) {
      this.currentSubmission = submission.name;
      this.currentCandidate = submission.candidate_name;
      this.currentAttentionScore = submission.attention_score ?? null;
      this.currentStatus = submission.status || '';

      var chatMessages = document.getElementById('archive-chat-messages');
      if (chatMessages) chatMessages.innerHTML = '';
      this.existingMessages[submission.name] = [];

      this._gazeData = null;
      this._gazeRendered = false;

      // Reset to Video tab
      var videoTab = document.querySelector('#archiveModal .modal-media-tabs .nav-link[href="#archive-tab-video"]');
      var ssTab = document.querySelector('#archiveModal .modal-media-tabs .nav-link[href="#archive-tab-screenshots"]');
      var gazeTab = document.querySelector('#archiveModal .modal-media-tabs .nav-link[href="#archive-tab-gaze"]');
      var videoPane = document.getElementById('archive-tab-video');
      var ssPane = document.getElementById('archive-tab-screenshots');
      var gazePane = document.getElementById('archive-tab-gaze');
      if (videoTab) videoTab.classList.add('active');
      if (ssTab) ssTab.classList.remove('active');
      if (gazeTab) gazeTab.classList.remove('active');
      if (videoPane) { videoPane.classList.add('show', 'active'); }
      if (ssPane) { ssPane.classList.remove('show', 'active'); }
      if (gazePane) { gazePane.classList.remove('show', 'active'); }

      if (submission.enable_video_proctoring && !this.videoStore[submission.name]) {
        try {
          var data = await this.apiCall({
            method: "exampro.exam_pro.doctype.exam_submission.exam_submission.proctor_video_list",
            args: { exam_submission: submission.name }
          });
          if (data.message && data.message.videos) {
            this.processVideoData(submission.name, data.message.videos);
          }
        } catch (e) { console.error('Failed to load videos for modal:', e); }
      }

      this.initModalVideoPlayer(submission.name);
      this.loadModalScreenshots(submission.name);
      this.loadChatMessages(submission.name);
      this.loadGazeData(submission.name);

      var modalElement = document.getElementById('archiveModal');
      if (modalElement) {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
          var modalInstance = new bootstrap.Modal(modalElement);
          modalInstance.show();
        } else if (typeof $ !== 'undefined') {
          $('#archiveModal').modal('show');
        }
      }

      if (typeof feather !== 'undefined') feather.replace();
    },

    closeModal() {
      var modalElement = document.getElementById('archiveModal');
      if (modalElement) {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
          var modalInstance = bootstrap.Modal.getInstance(modalElement);
          if (modalInstance) modalInstance.hide();
        } else if (typeof $ !== 'undefined') {
          $('#archiveModal').modal('hide');
        }
      }

      this.currentSubmission = '';
      this.currentCandidate = '';
      this._gazeData = null;
      this._gazeRendered = false;

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
        videoEl: '#archive-player-video',
        prevBtn: '#archive-player-prev',
        nextBtn: '#archive-player-next',
        playPauseBtn: '#archive-player-play',
        skipBackBtn: '#archive-player-skip-back',
        skipForwardBtn: '#archive-player-skip-fwd',
        goLiveBtn: null,
        indexField: '#archive-player-index',
      });

      var chunks = this.videoStore[examSubmission] || [];
      if (chunks.length > 0) {
        this._modalVideoPlayer.loadChunks(chunks);
        this._modalVideoPlayer.playAt(0);
      }
    },

    async loadModalScreenshots(examSubmission) {
      var gallery = document.getElementById('archive-screenshot-gallery');
      var viewer = document.getElementById('archive-screenshot-viewer');
      var emptyMsg = document.getElementById('archive-screenshot-empty');
      if (!gallery) return;

      gallery.innerHTML = '';
      if (viewer) viewer.classList.add('hidden');
      if (emptyMsg) emptyMsg.classList.remove('hidden');

      try {
        var data = await this.apiCall({
          method: 'exampro.exam_pro.doctype.exam_submission.exam_submission.get_screenshot_list',
          args: { exam_submission: examSubmission },
        });
        var screenshots = (data.message && data.message.screenshots) || [];
        if (screenshots.length === 0) return;

        if (emptyMsg) emptyMsg.classList.add('hidden');

        var self = this;
        screenshots.forEach(function (ss, idx) {
          var thumb = document.createElement('img');
          thumb.src = ss.url;
          thumb.style.cssText = 'height:80px;border-radius:4px;cursor:pointer;border:2px solid transparent;flex-shrink:0;';
          thumb.dataset.index = idx;
          thumb.onclick = function () { self._showModalScreenshot(screenshots, idx); };
          gallery.appendChild(thumb);
        });

        this._showModalScreenshot(screenshots, 0);
      } catch (error) {
        console.error('Failed to load screenshots:', error);
      }
    },

    _showModalScreenshot(list, idx) {
      var img = document.getElementById('archive-screenshot-full');
      var viewer = document.getElementById('archive-screenshot-viewer');
      var indexEl = document.getElementById('archive-ss-index');
      var captionEl = document.getElementById('archive-ss-caption');
      var gallery = document.getElementById('archive-screenshot-gallery');

      if (!img || !viewer) return;
      viewer.classList.remove('hidden');
      img.src = list[idx].url;
      if (indexEl) indexEl.textContent = (idx + 1) + '/' + list.length;

      if (captionEl) {
        var m = String(list[idx].filename).match(/^(\d+)/);
        if (m) {
          var d = new Date(Number(m[1]));
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

      var self = this;
      var prevBtn = document.getElementById('archive-ss-prev');
      var nextBtn = document.getElementById('archive-ss-next');
      if (prevBtn) prevBtn.onclick = function () { if (idx > 0) self._showModalScreenshot(list, idx - 1); };
      if (nextBtn) nextBtn.onclick = function () { if (idx < list.length - 1) self._showModalScreenshot(list, idx + 1); };
    },

    async loadChatMessages(examSubmission) {
      try {
        var data = await this.apiCall({
          method: "exampro.exam_pro.doctype.exam_submission.exam_submission.exam_messages",
          args: { exam_submission: examSubmission }
        });

        if (data.message && data.message.messages) {
          var messages = data.message.messages;
          var self = this;
          messages.forEach(function (chatmsg) {
            if (!self.existingMessages[examSubmission]) {
              self.existingMessages[examSubmission] = [];
            }
            if (!self.existingMessages[examSubmission].includes(chatmsg.creation)) {
              var convertedTime = self.timeAgo(chatmsg.creation);
              self.appendMessage(convertedTime, chatmsg.message, chatmsg.from);
              self.existingMessages[examSubmission].push(chatmsg.creation);
            }
          });
        }
      } catch (error) {
        console.error('Failed to load chat messages:', error);
      }
    },

    async loadGazeData(examSubmission) {
      try {
        var data = await this.apiCall({
          method: "exampro.exam_pro.doctype.exam_submission.exam_submission.get_submission_gaze_data",
          args: { exam_submission: examSubmission }
        });
        this._gazeData = data.message || null;
      } catch (error) {
        console.error('Failed to load gaze data:', error);
        this._gazeData = null;
      }
    },

    renderGazeCharts() {
      if (this._gazeRendered) return;

      var self = this;
      setTimeout(function () {
        if (!self._gazeData || !self._gazeData.retina_location_log) {
          var emptyEl = document.getElementById('archive-gaze-empty');
          var wrapEl = document.getElementById('archive-gaze-wrap');
          if (emptyEl) emptyEl.classList.remove('hidden');
          var canvas = document.getElementById('archive-gaze-timeline');
          if (canvas) canvas.style.display = 'none';
          return;
        }

        var canvas = document.getElementById('archive-gaze-timeline');
        if (canvas) {
          var wrap = canvas.closest('.tab-pane');
          var w = wrap ? wrap.clientWidth : 600;
          canvas.width = Math.max(400, w - 30);
          canvas.height = 420;
          canvas.style.display = 'block';
        }

        var emptyEl = document.getElementById('archive-gaze-empty');
        if (emptyEl) emptyEl.classList.add('hidden');

        if (typeof GazeCharts !== 'undefined') {
          GazeCharts.renderAll({
            retinaLog: self._gazeData.retina_location_log,
            timelineCanvas: 'archive-gaze-timeline',
            captionEl: 'archive-gaze-caption',
            pieCanvas: 'archive-gaze-pie',
            breakdownEl: 'archive-gaze-breakdown',
            scoreEl: 'archive-gaze-score',
            faceCountChanges: self._gazeData.face_count_changes || 0,
            examStartedTime: self._gazeData.exam_started_time,
            examSubmittedTime: self._gazeData.exam_submitted_time,
          });
        }

        self._gazeRendered = true;
      }, 150);
    },

    appendMessage(convertedTime, text, sender) {
      var chatMessages = document.getElementById('archive-chat-messages');
      if (!chatMessages) return;

      var messageElement = document.createElement('div');
      messageElement.className = 'd-flex flex-column mb-2';

      var timestampElement = document.createElement('div');
      timestampElement.className = sender === 'Candidate' ? 'chat-timestamp' : 'chat-timestamp-right';
      timestampElement.textContent = convertedTime;

      var contentElement = document.createElement('div');
      contentElement.className = 'chat-bubble ' + (sender === 'Candidate' ? 'chat-left' : 'chat-right');
      contentElement.textContent = text;

      messageElement.appendChild(timestampElement);
      messageElement.appendChild(contentElement);
      chatMessages.appendChild(messageElement);

      setTimeout(function () {
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }, 100);
    },

    timeAgo(timestamp) {
      if (typeof window.timeAgo === 'function' && window.timeAgo !== this.timeAgo) {
        return window.timeAgo(timestamp);
      }

      var currentTime = new Date();
      var providedTime = new Date(timestamp);
      var timeDifference = currentTime - providedTime;
      var minutesDifference = Math.floor(timeDifference / (1000 * 60));

      if (minutesDifference < 1) return 'Just now';
      if (minutesDifference === 1) return '1 minute ago';
      if (minutesDifference < 60) return minutesDifference + ' minutes ago';
      if (minutesDifference < 120) return '1 hour ago';
      if (minutesDifference < 1440) return Math.floor(minutesDifference / 60) + ' hours ago';
      if (minutesDifference < 2880) return '1 day ago';
      return Math.floor(minutesDifference / 1440) + ' days ago';
    },
  };
}

window.proctorArchiveApp = proctorArchiveApp;
