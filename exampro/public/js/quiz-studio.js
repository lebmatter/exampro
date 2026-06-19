function quizStudioApp() {
  return {
    // State
    quizzes: [],
    selectedQuiz: null,
    editData: null,
    searchQuery: "",
    editingQuestionIdx: -1,
    saving: false,
    aiConfigured: false,

    // Modal
    modalData: null,

    // Add questions modal
    _quizGenerateModal: null,
    addQuestionTab: "generate",
    aiTopic: "",
    aiCount: 5,
    aiTone: "fun",
    aiGenerating: false,

    // Import
    importCategories: [],
    importCategory: "",
    importCount: 5,

    // Manual
    manualQuestion: "",
    manualOptions: ["", "", "", ""],
    manualCorrect: 1,
    manualExplanation: "",

    // Dropdowns
    quizDropdownOpen: null,
    questionDropdownOpen: null,

    // Submissions
    submissions: [],
    submissionTab: "responses",
    analytics: null,
    analyticsLoading: false,

    get filteredQuizzes() {
      if (!this.searchQuery) {
        return this.quizzes.filter(function (quiz) {
          return quiz.status !== "Archived";
        }).slice(0, 10);
      }
      var q = this.searchQuery.toLowerCase();
      return this.quizzes.filter(function (quiz) {
        return quiz.title.toLowerCase().includes(q);
      });
    },

    init() {
      this.aiConfigured = (window.examStudioData && window.examStudioData.aiConfigured) || this.$el.dataset.aiConfigured === "true";
      this.loadQuizzes();
      this.loadCategories();
      this.$nextTick(() => {
        var el = document.getElementById("quizGenerateModal");
        if (el) this._quizGenerateModal = new bootstrap.Modal(el);
      });
    },

    randomPin() {
      var chars = "0123456789";
      var pin = "";
      for (var i = 0; i < 4; i++) {
        pin += chars.charAt(Math.floor(Math.random() * chars.length));
      }
      return pin;
    },

    replaceIcons() {
      this.$nextTick(function () {
        if (typeof feather !== "undefined") feather.replace();
      });
    },

    // --- Modal ---

    _showModal() {
      this.replaceIcons();
      var el = document.getElementById("quizSettingsModal");
      if (el) {
        var modal = bootstrap.Modal.getOrCreateInstance(el);
        modal.show();
      }
    },

    _hideModal() {
      var el = document.getElementById("quizSettingsModal");
      if (el) {
        var modal = bootstrap.Modal.getInstance(el);
        if (modal) modal.hide();
      }
    },

    openNewQuizModal() {
      this.modalData = {
        name: null,
        title: "",
        quiz_mode: "Simple",
        status: "Draft",
        access_type: "PIN",
        pin_code: this.randomPin(),
        timer_enabled: 0,
        timer_seconds: 30,
        theme: "Default",
        randomize_questions: 0,
        show_correct_after_answer: 0,
        description: "",
        questions: [],
      };
      this._showModal();
    },

    _positionDropdown(btnEl) {
      this.$nextTick(() => {
        var menu = btnEl.closest('.quiz-dropdown-wrap').querySelector('.quiz-dropdown-menu');
        if (!menu) return;
        var rect = btnEl.getBoundingClientRect();
        menu.style.top = (rect.bottom + 2) + 'px';
        menu.style.right = (window.innerWidth - rect.right) + 'px';
        menu.style.left = 'auto';
        this.replaceIcons();
      });
    },

    toggleQuizDropdown(quizName) {
      this.questionDropdownOpen = null;
      if (this.quizDropdownOpen === quizName) {
        this.quizDropdownOpen = null;
        return;
      }
      this.quizDropdownOpen = quizName;
      this._positionDropdown(this.$event.currentTarget);
    },

    toggleQuestionDropdown(idx) {
      this.quizDropdownOpen = null;
      if (this.questionDropdownOpen === idx) {
        this.questionDropdownOpen = null;
        return;
      }
      this.questionDropdownOpen = idx;
      this._positionDropdown(this.$event.currentTarget);
    },

    openSettingsModal() {
      if (!this.editData) return;
      this.modalData = JSON.parse(JSON.stringify(this.editData));
      this._showModal();
    },

    confirmModal() {
      var self = this;
      if (!this.modalData.title.trim()) return;

      if (this.modalData.name) {
        // Editing existing — copy settings back
        var keep = ["title", "quiz_mode", "status", "access_type", "pin_code",
          "timer_enabled", "timer_seconds", "theme", "randomize_questions",
          "description"];
        for (var i = 0; i < keep.length; i++) {
          self.editData[keep[i]] = self.modalData[keep[i]];
        }
        self._hideModal();
        self.saveQuiz();
      } else {
        // Creating new — set as active quiz and save
        self.selectedQuiz = { name: null };
        self.editData = self.modalData;
        self.editingQuestionIdx = -1;
        self.submissions = [];
        self._hideModal();
        self.saveQuiz();
      }
      self.replaceIcons();
    },

    // --- Quiz CRUD ---

    loadQuizzes() {
      var self = this;
      frappe.call({
        method: "exampro.exam_pro.api.quick_quiz_studio.get_quiz_list",
        callback: function (r) {
          self.quizzes = (r.message && r.message.quizzes) || [];
          self.replaceIcons();
        },
      });
    },

    selectQuiz(quiz) {
      var self = this;
      frappe.call({
        method: "exampro.exam_pro.api.quick_quiz_studio.get_quiz_detail",
        args: { name: quiz.name },
        callback: function (r) {
          self.selectedQuiz = quiz;
          self.editData = r.message;
          self.editData.questions = self.editData.questions || [];
          self.editingQuestionIdx = -1;
          self.submissions = [];
          self.analytics = null;
          self.submissionTab = "responses";
          self.loadSubmissions();
          self.replaceIcons();
        },
      });
    },

    saveQuiz() {
      var self = this;
      self.saving = true;
      frappe.call({
        method: "exampro.exam_pro.api.quick_quiz_studio.save_quiz",
        args: { data: JSON.stringify(self.editData) },
        callback: function (r) {
          self.saving = false;
          self.editData.name = r.message.name;
          self.editData.short_uuid = r.message.short_uuid;
          if (self.selectedQuiz) self.selectedQuiz.name = r.message.name;
          self.loadQuizzes();
          frappe.show_alert({ message: "Quiz saved", indicator: "green" });
          self.replaceIcons();
        },
        error: function () {
          self.saving = false;
        },
      });
    },

    archiveQuiz() {
      if (!confirm("Archive this quiz?")) return;
      var self = this;
      frappe.call({
        method: "exampro.exam_pro.api.quick_quiz_studio.delete_quiz",
        args: { name: self.editData.name },
        callback: function () {
          self.selectedQuiz = null;
          self.editData = null;
          self.submissions = [];
          self.loadQuizzes();
          frappe.show_alert({ message: "Quiz archived", indicator: "orange" });
          self.replaceIcons();
        },
      });
    },

    duplicateQuiz() {
      var self = this;
      frappe.call({
        method: "exampro.exam_pro.api.quick_quiz_studio.duplicate_quiz",
        args: { name: self.editData.name },
        callback: function () {
          self.loadQuizzes();
          frappe.show_alert({ message: "Quiz duplicated", indicator: "green" });
        },
      });
    },

    shareUrl() {
      return window.location.origin + "/quiz/" + (this.editData.short_uuid || "");
    },

    copyShareLink() {
      navigator.clipboard.writeText(this.shareUrl());
      frappe.show_alert({ message: "Link copied!", indicator: "green" });
    },

    togglePublish() {
      var newStatus =
        this.editData.status === "Published" ? "Draft" : "Published";
      if (newStatus === "Published" && (!this.editData.questions || this.editData.questions.length === 0)) {
        frappe.show_alert({ message: "Cannot publish a quiz with no questions", indicator: "orange" }, 5);
        return;
      }
      this.editData.status = newStatus;
      this.saveQuiz();
    },

    takeDemo() {
      var uuid = this.editData.short_uuid || "preview";
      window.open("/quiz/" + uuid + "?preview=1", "_blank");
    },

    hostQuiz() {
      window.open(
        "/quiz/" + this.editData.short_uuid + "/host",
        "_blank"
      );
    },

    // --- Question management ---

    addQuestion() {
      this.editData.questions.push({
        question: "",
        question_image: "",
        option_1: "",
        option_2: "",
        option_3: "",
        option_4: "",
        is_correct_1: 1,
        is_correct_2: 0,
        is_correct_3: 0,
        is_correct_4: 0,
        explanation: "",
        points: 100,
      });
      this.editingQuestionIdx = this.editData.questions.length - 1;
      this.replaceIcons();
    },

    editQuestion(idx) {
      this.editingQuestionIdx =
        this.editingQuestionIdx === idx ? -1 : idx;
      this.replaceIcons();
    },

    removeQuestion(idx) {
      this.editData.questions.splice(idx, 1);
      if (this.editingQuestionIdx === idx) this.editingQuestionIdx = -1;
    },

    setCorrectOption(qIdx, optNum) {
      for (var i = 1; i <= 4; i++) {
        this.editData.questions[qIdx]["is_correct_" + i] =
          i === optNum ? 1 : 0;
      }
    },

    // --- AI generation ---

    openQuizGenerateModal() {
      if (this._quizGenerateModal) this._quizGenerateModal.show();
      this.replaceIcons();
    },

    generateFromModal() {
      var self = this;
      self.generateQuestions();
      var checkDone = setInterval(function () {
        if (!self.aiGenerating) {
          clearInterval(checkDone);
          if (self._quizGenerateModal) self._quizGenerateModal.hide();
        }
      }, 200);
    },

    importFromModal() {
      var self = this;
      this.importQuestions();
      if (this._quizGenerateModal) this._quizGenerateModal.hide();
    },

    addManualFromModal() {
      if (!this.manualQuestion.trim()) return;
      this.editData.questions.push({
        question: this.manualQuestion,
        question_image: "",
        option_1: this.manualOptions[0],
        option_2: this.manualOptions[1],
        option_3: this.manualOptions[2],
        option_4: this.manualOptions[3],
        is_correct_1: this.manualCorrect === 1 ? 1 : 0,
        is_correct_2: this.manualCorrect === 2 ? 1 : 0,
        is_correct_3: this.manualCorrect === 3 ? 1 : 0,
        is_correct_4: this.manualCorrect === 4 ? 1 : 0,
        explanation: this.manualExplanation,
        points: 100,
      });
      this.manualQuestion = "";
      this.manualOptions = ["", "", "", ""];
      this.manualCorrect = 1;
      this.manualExplanation = "";
      if (this._quizGenerateModal) this._quizGenerateModal.hide();
      this.replaceIcons();
    },

    generateQuestions() {
      var self = this;
      self.aiGenerating = true;
      frappe.call({
        method:
          "exampro.exam_pro.api.quick_quiz_studio.generate_quiz_questions",
        args: {
          topic: self.aiTopic,
          count: self.aiCount,
          tone: self.aiTone,
        },
        callback: function (r) {
          self.aiGenerating = false;
          var newQs = (r.message && r.message.questions) || [];
          self.editData.questions.push.apply(
            self.editData.questions,
            newQs
          );
          frappe.show_alert({
            message: newQs.length + " questions generated",
            indicator: "green",
          });
          self.replaceIcons();
        },
        error: function () {
          self.aiGenerating = false;
        },
      });
    },

    // --- Import from question bank ---

    loadCategories() {
      var self = this;
      frappe.call({
        method:
          "exampro.exam_pro.api.quick_quiz_studio.get_question_categories",
        callback: function (r) {
          self.importCategories =
            (r.message && r.message.categories) || [];
        },
      });
    },

    importQuestions() {
      var self = this;
      frappe.call({
        method:
          "exampro.exam_pro.api.quick_quiz_studio.import_from_question_bank",
        args: {
          category: self.importCategory,
          count: self.importCount,
        },
        callback: function (r) {
          var newQs = (r.message && r.message.questions) || [];
          self.editData.questions.push.apply(
            self.editData.questions,
            newQs
          );
          frappe.show_alert({
            message: newQs.length + " questions imported",
            indicator: "green",
          });
          self.replaceIcons();
        },
      });
    },

    // --- Submissions ---

    loadSubmissions() {
      if (!this.editData || !this.editData.name) return;
      var self = this;
      frappe.call({
        method:
          "exampro.exam_pro.api.quick_quiz_studio.get_quiz_submissions",
        args: { quiz_name: self.editData.name },
        callback: function (r) {
          self.submissions =
            (r.message && r.message.submissions) || [];
        },
      });
    },

    loadAnalytics() {
      if (!this.editData || !this.editData.name) return;
      var self = this;
      self.analyticsLoading = true;
      frappe.call({
        method: "exampro.exam_pro.api.quick_quiz_studio.get_quiz_analytics",
        args: { quiz_name: self.editData.name },
        callback: function (r) {
          self.analyticsLoading = false;
          self.analytics = r.message || null;
        },
        error: function () {
          self.analyticsLoading = false;
        },
      });
    },

    switchSubmissionTab(tab) {
      this.submissionTab = tab;
      if (tab === "analytics" && !this.analytics) {
        this.loadAnalytics();
      }
    },
  };
}

window.quizStudioApp = quizStudioApp;
