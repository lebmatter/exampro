function quizApp() {
  return {
    // Config from page
    shortUuid: '',
    isHost: false,
    isPreview: false,

    // State
    screen: 'join', // join|waiting|question|feedback|leaderboard|complete|host-lobby|host-question|host-leaderboard
    quizInfo: {},
    questions: [],
    currentQuestionIdx: 0,
    participantName: '',
    pinInput: '',
    submissionId: null,
    joining: false,
    joinError: '',

    // Answer state
    answered: false,
    selectedOption: null,
    lastAnswerCorrect: false,
    lastPointsEarned: 0,
    totalScore: 0,

    // Timer
    timerPercent: 100,
    timerDisplay: '',
    timerInterval: null,
    questionStartTime: null,

    // Host state
    hostAnswerCount: 0,
    participants: [],
    participantPollInterval: null,
    quizEnded: false,

    // Results
    results: {},
    leaderboard: [],

    // Theme
    theme: 'default',
    joinUrl: '',

    init() {
      const pageData = window.quizPageData || {};
      this.shortUuid = pageData.shortUuid || '';
      this.isHost = pageData.isHost || false;
      this.isPreview = pageData.isPreview || false;

      if (this.isHost) {
        this.screen = 'host-lobby';
      }

      this.loadQuizInfo();
      this.setupRealtime();
    },

    loadQuizInfo() {
      frappe.call({
        method: 'exampro.exam_pro.api.quick_quiz.get_quiz_info',
        args: { short_uuid: this.shortUuid },
        callback: (r) => {
          this.quizInfo = r.message;
          this.theme = (this.quizInfo.theme || 'default').toLowerCase().replace(/ /g, '-');
          this.joinUrl = window.location.origin + '/quiz/' + this.shortUuid;

          // If logged in user, pre-fill name
          if (frappe.session.user && frappe.session.user !== 'Guest') {
            this.participantName = frappe.session.user_fullname || frappe.session.user;
          }

          // Host mode goes to lobby
          if (this.isHost) {
            this.screen = 'host-lobby';
            this.startParticipantPolling();
          }

          this.$nextTick(() => {
            setTimeout(() => {
              if (typeof feather !== 'undefined') feather.replace();
            }, 50);
          });
        },
        error: () => {
          this.joinError = 'Quiz not found or not available.';
        }
      });
    },

    setupRealtime() {
      if (!frappe.realtime) return;

      // Subscribe to quiz room
      frappe.realtime.on('quiz_question', (data) => {
        if (!this.isHost) {
          this.currentQuestionIdx = data.question_idx;
          this.showQuestion(data);
        }
      });

      frappe.realtime.on('quiz_answer_count', (data) => {
        if (this.isHost) {
          this.hostAnswerCount = data.answer_count;
        }
      });

      frappe.realtime.on('quiz_leaderboard', (data) => {
        this.leaderboard = data.rankings;
        if (!this.isHost) {
          this.screen = 'leaderboard';
        }
        this.$nextTick(() => {
          if (typeof feather !== 'undefined') feather.replace();
        });
      });

      frappe.realtime.on('quiz_ended', () => {
        this.finishQuiz();
      });

      frappe.realtime.on('quiz_participant_joined', (data) => {
        if (this.isHost) {
          this.participants = data.participants || this.participants;
        }
      });
    },

    joinQuiz() {
      this.joining = true;
      this.joinError = '';

      const args = {
        short_uuid: this.shortUuid,
        participant_name: this.participantName.trim(),
      };
      if (this.quizInfo.access_type === 'PIN') {
        args.pin = this.pinInput;
      }

      frappe.call({
        method: 'exampro.exam_pro.api.quick_quiz.join_quiz',
        args: args,
        callback: (r) => {
          this.joining = false;
          const data = r.message;
          this.submissionId = data.submission_id;
          this.questions = data.questions;

          if (this.quizInfo.quiz_mode === 'Kahoot') {
            this.screen = 'waiting';
          } else {
            // Simple mode: start immediately
            this.currentQuestionIdx = 0;
            this.startQuestion();
          }
          this.$nextTick(() => {
            if (typeof feather !== 'undefined') feather.replace();
          });
        },
        error: (err) => {
          this.joining = false;
          this.joinError = (err && err.message) || 'Failed to join quiz.';
        }
      });
    },

    _normalizeOptions(q) {
      if (q.options) return q;
      q.options = [q.option_1, q.option_2, q.option_3, q.option_4].filter(Boolean);
      return q;
    },

    get currentQuestion() {
      if (!this.questions.length) return { question: '', options: [] };
      var q = this.questions[this.currentQuestionIdx] || { question: '', options: [] };
      return this._normalizeOptions(q);
    },

    startQuestion() {
      this.screen = 'question';
      this.answered = false;
      this.selectedOption = null;
      this.questionStartTime = Date.now();
      this.timerPercent = 100;

      if (this.quizInfo.timer_enabled) {
        this.startTimer();
      }

      this.$nextTick(() => {
        if (typeof feather !== 'undefined') feather.replace();
      });
    },

    showQuestion(data) {
      this.currentQuestionIdx = data.question_idx;
      if (data.question) {
        var q = {
          question: data.question,
          question_image: data.question_image || '',
          option_1: data.option_1,
          option_2: data.option_2,
          option_3: data.option_3,
          option_4: data.option_4,
          points: data.points || 100,
        };
        this.questions[data.question_idx] = q;
      }
      this.startQuestion();
    },

    startTimer() {
      this.clearTimer();
      const totalMs = this.quizInfo.timer_seconds * 1000;
      const startTime = Date.now();

      this.timerInterval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const remaining = Math.max(0, totalMs - elapsed);
        this.timerPercent = (remaining / totalMs) * 100;
        this.timerDisplay = Math.ceil(remaining / 1000) + 's';

        if (remaining <= 0) {
          this.clearTimer();
          if (!this.answered) {
            this.selectOption(0); // timeout - no selection
          }
        }
      }, 50);
    },

    clearTimer() {
      if (this.timerInterval) {
        clearInterval(this.timerInterval);
        this.timerInterval = null;
      }
    },

    selectOption(optionNum) {
      if (this.answered) return;
      this.answered = true;
      this.selectedOption = optionNum;
      this.clearTimer();

      const timeTaken = Date.now() - (this.questionStartTime || Date.now());

      frappe.call({
        method: 'exampro.exam_pro.api.quick_quiz.submit_answer',
        args: {
          submission_id: this.submissionId,
          question_idx: this.currentQuestionIdx,
          selected_option: optionNum,
          time_taken_ms: timeTaken,
        },
        callback: (r) => {
          const data = r.message;
          this.lastAnswerCorrect = data.is_correct || false;
          this.lastPointsEarned = data.points_earned || 0;
          this.totalScore += this.lastPointsEarned;

          // Show feedback briefly
          if (this.quizInfo.show_correct_after_answer) {
            setTimeout(() => {
              this.screen = 'feedback';
              this.$nextTick(() => {
                if (typeof feather !== 'undefined') feather.replace();
              });

              // For simple mode, auto-advance after feedback
              if (this.quizInfo.quiz_mode === 'Simple') {
                setTimeout(() => this.advanceQuestion(), 2000);
              }
              // Kahoot: host controls advancement
            }, 500);
          } else {
            // No feedback, just advance (Simple mode)
            setTimeout(() => this.advanceQuestion(), 500);
          }
        }
      });
    },

    optionClass(idx) {
      const num = idx + 1;
      let cls = 'quiz-option-color-' + num;
      if (this.answered) {
        if (num === this.selectedOption) {
          cls += this.lastAnswerCorrect ? ' quiz-option-correct' : ' quiz-option-wrong';
        }
      }
      return cls;
    },

    advanceQuestion() {
      if (this.currentQuestionIdx < this.questions.length - 1) {
        this.currentQuestionIdx++;
        this.startQuestion();
      } else {
        this.finishQuiz();
      }
    },

    finishQuiz() {
      this.clearTimer();

      frappe.call({
        method: 'exampro.exam_pro.api.quick_quiz.finish_quiz',
        args: { submission_id: this.submissionId },
        callback: () => {
          frappe.call({
            method: 'exampro.exam_pro.api.quick_quiz.get_quiz_results',
            args: { submission_id: this.submissionId },
            callback: (r) => {
              this.results = r.message;
              this.screen = 'complete';
              this.$nextTick(() => {
                if (typeof feather !== 'undefined') feather.replace();
              });
            }
          });
        }
      });
    },

    copyToClipboard(text) {
      navigator.clipboard.writeText(text).then(() => {
        frappe.show_alert({ message: 'Copied!', indicator: 'green' }, 2);
      });
    },

    // ---- Host functions ----

    startParticipantPolling() {
      this.pollParticipants();
      this.participantPollInterval = setInterval(() => this.pollParticipants(), 3000);
    },

    pollParticipants() {
      frappe.call({
        method: 'exampro.exam_pro.api.quick_quiz.get_live_participants',
        args: { short_uuid: this.shortUuid },
        callback: (r) => {
          this.participants = (r.message && r.message.participants) || [];
        }
      });
    },

    hostStartQuiz() {
      frappe.call({
        method: 'exampro.exam_pro.api.quick_quiz.host_start_quiz',
        args: { short_uuid: this.shortUuid },
        callback: (r) => {
          const data = r.message;
          this.questions = data.questions || [];
          this.currentQuestionIdx = 0;
          this.hostAnswerCount = 0;
          this.screen = 'host-question';
          if (this.quizInfo.timer_enabled) this.startTimer();
          this.$nextTick(() => {
            if (typeof feather !== 'undefined') feather.replace();
          });
        }
      });
    },

    hostNextQuestion() {
      if (this.currentQuestionIdx >= this.questions.length - 1) {
        this.hostEndQuiz();
        return;
      }
      this.currentQuestionIdx++;
      this.hostAnswerCount = 0;

      frappe.call({
        method: 'exampro.exam_pro.api.quick_quiz.host_next_question',
        args: { short_uuid: this.shortUuid, question_idx: this.currentQuestionIdx },
        callback: () => {
          this.screen = 'host-question';
          if (this.quizInfo.timer_enabled) this.startTimer();
          this.$nextTick(() => {
            if (typeof feather !== 'undefined') feather.replace();
          });
        }
      });
    },

    hostShowLeaderboard() {
      frappe.call({
        method: 'exampro.exam_pro.api.quick_quiz.host_show_leaderboard',
        args: { short_uuid: this.shortUuid },
        callback: (r) => {
          this.leaderboard = (r.message && r.message.rankings) || [];
          this.screen = 'host-leaderboard';
          this.$nextTick(() => {
            if (typeof feather !== 'undefined') feather.replace();
          });
        }
      });
    },

    hostEndQuiz() {
      this.clearTimer();
      if (this.participantPollInterval) {
        clearInterval(this.participantPollInterval);
      }

      frappe.call({
        method: 'exampro.exam_pro.api.quick_quiz.host_end_quiz',
        args: { short_uuid: this.shortUuid },
        callback: (r) => {
          this.leaderboard = (r.message && r.message.leaderboard) || [];
          this.quizEnded = true;
          this.screen = 'host-leaderboard';
          this.$nextTick(() => {
            if (typeof feather !== 'undefined') feather.replace();
          });
        }
      });
    },

    hostRestartQuiz() {
      frappe.call({
        method: 'exampro.exam_pro.api.quick_quiz.host_restart_quiz',
        args: { short_uuid: this.shortUuid },
        callback: () => {
          this.quizEnded = false;
          this.participants = [];
          this.leaderboard = [];
          this.questions = [];
          this.currentQuestionIdx = 0;
          this.hostAnswerCount = 0;
          this.screen = 'host-lobby';
          this.startParticipantPolling();
          this.$nextTick(() => {
            if (typeof feather !== 'undefined') feather.replace();
          });
        }
      });
    },
  };
}
