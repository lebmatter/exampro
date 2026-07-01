function examStudioApp() {
  return {
    currentPartner: window.examStudioData?.currentPartner || "",
    partnerName: window.examStudioData?.partnerName || "",
    aiConfigured: window.examStudioData?.aiConfigured || false,
    allCategories: window.examStudioData?.categories || [],
    categories: window.examStudioData?.categories || [],

    category: "",
    count: 5,
    mark: 1,
    difficulty: "Medium",
    questionType: "Choices",
    prompt: "",

    showNewCategory: false,
    newCategoryName: "",

    uploadedFile: null,
    fileContent: "",
    fileError: "",
    fileDragOver: false,

    generating: false,
    regenerating: false,
    updating: false,
    generatingHelpText: false,
    helpTextSize: "medium",
    generatingImage: null,
    imageStyle: "realistic",
    imageStyles: [
      { key: "realistic", label: "Realistic" },
      { key: "cartoon", label: "Cartoon" },
      { key: "exampro_slider", label: "ExamPro Slider" },
    ],
    generatedQuestions: [],
    selectedIndex: null,
    editSource: "generated",
    modalTab: "question",

    approvedQuestions: [],
    saving: false,
    loadingExisting: false,

    categorySearchQuery: "",

    _cacheTimer: null,
    _modal: null,
    _generateModal: null,

    // --- Exams tab state ---
    examDropdownOpen: null,
    scheduleDropdownOpen: null,
    exams: window.examStudioData?.exams || [],
    selectedExam: null,
    schedules: [],
    selectedSchedule: null,
    candidates: [],
    batches: window.examStudioData?.batches || [],
    allCertificateTemplates: window.examStudioData?.certificateTemplates || [],
    allPartners: window.examStudioData?.partners || [],

    loadingSchedules: false,
    loadingCandidates: false,
    savingExam: false,
    savingSchedule: false,
    addingCandidates: false,

    examModalMode: "create",
    examModalTab: "details",
    examForm: {
      name: "",
      title: "",
      exam_mode: "Exam",
      duration: 60,
      pass_percentage: 50,
      question_type: "Choices",
      description: "",
      instructions: "",
      randomize_questions: false,
      select_questions: [],
      enable_certification: false,
      expiry: 0,
      certificate_template: "",
      partner: "",
      partner_manages_questions: false,
      is_public: false,
      enable_payment: false,
      price: 0,
      enable_video_proctoring: false,
      enable_screen_recording: false,
      enable_chat: false,
      enable_calculator: false,
      max_warning_count: 3,
    },

    scheduleForm: {
      schedule_name: "",
      start_date_time: "",
      schedule_type: "Fixed",
      schedule_expire_in_days: 7,
      badge: "",
    },

    candidateAddMode: "search",
    candidateEmails: "",
    candidateSearchQuery: "",
    candidateSearchResults: [],
    selectedUsers: [],
    candidateBatch: "",

    examSearchQuery: "",
    scheduleModalMode: "create",
    conflictingSchedules: [],
    loadingConflicts: false,
    conflictsChecked: false,

    ongoingSchedules: [],

    _examModal: null,
    _scheduleModal: null,
    _candidateModal: null,
    _newCategoryModal: null,

    init() {
      this.restoreState();
      this.loadOngoingSchedules();
      this.$nextTick(() => {
        if (typeof feather !== "undefined") feather.replace();
        this._modal = new bootstrap.Modal(document.getElementById("questionEditorModal"));
        var generateModalEl = document.getElementById("generateQuestionsModal");
        if (generateModalEl) this._generateModal = new bootstrap.Modal(generateModalEl);

        var examModalEl = document.getElementById("examEditorModal");
        if (examModalEl) this._examModal = new bootstrap.Modal(examModalEl);
        var scheduleModalEl = document.getElementById("scheduleEditorModal");
        if (scheduleModalEl) this._scheduleModal = new bootstrap.Modal(scheduleModalEl);
        var candidateModalEl = document.getElementById("candidateAddModal");
        if (candidateModalEl) this._candidateModal = new bootstrap.Modal(candidateModalEl);
        var newCategoryModalEl = document.getElementById("newCategoryModal");
        if (newCategoryModalEl) this._newCategoryModal = new bootstrap.Modal(newCategoryModalEl);
      });
    },

    replaceIcons() {
      this.$nextTick(() => {
        if (typeof feather !== "undefined") feather.replace();
      });
    },

    loadOngoingSchedules() {
      frappe.call({
        method: "exampro.exam_pro.api.exam_studio.get_ongoing_schedules",
        callback: (r) => {
          this.ongoingSchedules = r.message || [];
          this.replaceIcons();
        },
      });
    },

    execFormat(command) {
      document.execCommand(command, false, null);
    },

    persistState() {
      clearTimeout(this._cacheTimer);
      this._cacheTimer = setTimeout(() => {
        frappe.call({
          method: "exampro.exam_pro.api.exam_studio.set_cached_state",
          args: {
            state: JSON.stringify({
              generatedQuestions: this.generatedQuestions,
              approvedQuestions: this.approvedQuestions,
              category: this.category,
              count: this.count,
              mark: this.mark,
              difficulty: this.difficulty,
              questionType: this.questionType,
              prompt: this.prompt,
            }),
          },
          async: true,
        });
      }, 500);
    },

    async restoreState() {
      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.get_cached_state",
        });
        if (r.message && Object.keys(r.message).length > 0) {
          var s = r.message;
          if (s.generatedQuestions) this.generatedQuestions = s.generatedQuestions;
          if (s.approvedQuestions) this.approvedQuestions = s.approvedQuestions;
          if (s.category) this.category = s.category;
          if (s.count) this.count = s.count;
          if (s.mark) this.mark = s.mark;
          if (s.difficulty) this.difficulty = s.difficulty;
          if (s.questionType) this.questionType = s.questionType;
          if (s.prompt) this.prompt = s.prompt;
        }
      } catch (e) {
        // ignore cache restore errors
      }
      this.replaceIcons();
    },

    selectCategory(cat) {
      this.category = cat.name;
      this.onCategoryChange();
      this.replaceIcons();
    },

    async searchCategories() {
      var q = (this.categorySearchQuery || "").trim();
      if (!q) {
        this.categories = this.allCategories;
        this.replaceIcons();
        return;
      }
      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.search_categories",
          args: { query: q },
        });
        this.categories = r.message || [];
      } catch (e) {
        this.categories = [];
      }
      this.replaceIcons();
    },

    clearCategorySearch() {
      this.categorySearchQuery = "";
      this.categories = this.allCategories;
      this.replaceIcons();
    },

    openGenerateModal() {
      if (this._generateModal) this._generateModal.show();
      this.replaceIcons();
    },

    async generateFromModal() {
      await this.generateQuestions();
      if (this._generateModal) this._generateModal.hide();
    },

    async onCategoryChange() {
      if (!this.category) {
        this.approvedQuestions = [];
        this.persistState();
        return;
      }
      this.loadingExisting = true;
      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.get_category_questions",
          args: { category: this.category },
        });
        if (r.message && r.message.questions) {
          this.approvedQuestions = r.message.questions;
          this.persistState();
        }
      } catch (e) {
        // error shown by frappe
      }
      this.loadingExisting = false;
      this.replaceIcons();
    },

    stripHtml(html) {
      var tmp = document.createElement("div");
      tmp.innerHTML = html || "";
      return tmp.textContent || tmp.innerText || "";
    },

    currentQ() {
      if (this.selectedIndex === null) return null;
      if (this.editSource === "approved") return this.approvedQuestions[this.selectedIndex];
      return this.generatedQuestions[this.selectedIndex];
    },

    ensureHelpFields(q) {
      if (!q) return;
      if (q.help_show === undefined) q.help_show = "Do not show";
      if (q.help_type === undefined) q.help_type = "Text";
      if (q.help_text === undefined) q.help_text = "";
      if (q.help_link === undefined) q.help_link = "";
      if (q.help_quiz === undefined) q.help_quiz = [];
    },

    ensureImageFields(q) {
      if (!q) return;
      if (q.description_image === undefined) q.description_image = "";
      if (q.helper_text_image === undefined) q.helper_text_image = "";
      if (q.type === "Choices" && q.options) {
        q.options.forEach(function(opt) {
          if (opt.image === undefined) opt.image = "";
        });
      }
    },

    openModal(index, source) {
      this.selectedIndex = index;
      this.editSource = source;
      this.modalTab = "question";
      this.ensureHelpFields(this.currentQ());
      this.ensureImageFields(this.currentQ());
      this._modal.show();
      this.$nextTick(() => {
        this.syncEditorsToData();
        this.replaceIcons();
      });
    },

    syncEditorsToData() {
      var q = this.currentQ();
      if (!q) return;
      if (this.$refs.questionEditor) {
        this.$refs.questionEditor.innerHTML = q.question || "";
      }
      if (this.$refs.helpTextEditor) {
        this.$refs.helpTextEditor.innerHTML = q.help_text || "";
      }
      if (this.$refs.explanationEditor) {
        this.$refs.explanationEditor.innerHTML = q.explanation || "";
      }
    },

    closeModal() {
      if (this._modal) this._modal.hide();
    },

    addHelpQuiz() {
      var q = this.currentQ();
      if (!q) return;
      if (!q.help_quiz) q.help_quiz = [];
      if (q.help_quiz.length >= 3) return;
      q.help_quiz.push({
        quiz_question: "",
        choice_1: "",
        choice_2: "",
        choice_3: "",
        correct_choice: "1",
      });
    },

    removeHelpQuiz(index) {
      var q = this.currentQ();
      if (q && q.help_quiz) {
        q.help_quiz.splice(index, 1);
      }
    },

    async generateHelpText() {
      var q = this.currentQ();
      if (!q || !q.question) return;
      this.generatingHelpText = true;

      try {
        var args = {
          question: q.question,
          question_type: q.type || "Choices",
          category: q.category || this.category,
          text_size: this.helpTextSize,
        };
        if (q.type === "Choices" && q.options) {
          args.options = JSON.stringify(q.options);
        } else if (q.type === "User Input" && q.possible_answers) {
          args.possible_answers = JSON.stringify(q.possible_answers);
        }

        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.generate_help_text",
          args: args,
        });

        if (r.message && r.message.help_text) {
          q.help_text = r.message.help_text;
          if (q.help_show === "Do not show") {
            q.help_show = "Before question";
          }
          this.$nextTick(() => {
            if (this.$refs.helpTextEditor) {
              this.$refs.helpTextEditor.innerHTML = q.help_text;
            }
          });
          this.persistState();
          frappe.show_alert({ message: "Help text generated", indicator: "green" });
        }
      } catch (e) {
        // error shown by frappe
      }

      this.generatingHelpText = false;
      this.replaceIcons();
    },

    // --- Image generation & upload ---

    async generateAllImages() {
      var q = this.currentQ();
      if (!q || !q.question || this.generatingImage) return;

      var jobs = [];
      if (!q.description_image) {
        jobs.push({ fieldKey: "description_image", prompt: q.question });
      }
      if (q.type === "Choices" && q.options) {
        for (var i = 0; i < q.options.length; i++) {
          if (!q.options[i].image && q.options[i].text) {
            jobs.push({ fieldKey: "option_" + (i + 1) + "_image", prompt: q.options[i].text });
          }
        }
      }
      if (!q.helper_text_image) {
        jobs.push({ fieldKey: "helper_text_image", prompt: q.question });
      }

      if (jobs.length === 0) {
        frappe.show_alert({ message: "All images already set", indicator: "blue" });
        return;
      }

      for (var j = 0; j < jobs.length; j++) {
        await this.generateImage(jobs[j].fieldKey, jobs[j].prompt);
      }
      frappe.show_alert({ message: "All images generated", indicator: "green" });
    },

    async uploadImage(event, fieldKey) {
      var file = event.target.files[0];
      if (!file) return;

      var formData = new FormData();
      formData.append("file", file);
      formData.append("is_private", "0");
      formData.append("folder", "Home");

      try {
        const r = await fetch("/api/method/upload_file", {
          method: "POST",
          body: formData,
          headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
        });
        const data = await r.json();
        if (data.message && data.message.file_url) {
          this.currentQ()[fieldKey] = data.message.file_url;
          this.persistState();
          frappe.show_alert({ message: "Image uploaded", indicator: "green" });
        }
      } catch (e) {
        frappe.show_alert({ message: "Upload failed", indicator: "red" });
      }
      event.target.value = "";
      this.replaceIcons();
    },

    triggerOptionImageUpload(optionIndex) {
      var self = this;
      var input = document.createElement("input");
      input.type = "file";
      input.accept = "image/*";
      input.onchange = function(event) {
        var file = event.target.files[0];
        if (!file) return;

        var formData = new FormData();
        formData.append("file", file);
        formData.append("is_private", "0");
        formData.append("folder", "Home");

        fetch("/api/method/upload_file", {
          method: "POST",
          body: formData,
          headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
        })
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.message && data.message.file_url) {
              self.currentQ().options[optionIndex].image = data.message.file_url;
              self.persistState();
              self.replaceIcons();
              frappe.show_alert({ message: "Image uploaded", indicator: "green" });
            }
          })
          .catch(function() {
            frappe.show_alert({ message: "Upload failed", indicator: "red" });
          });
      };
      input.click();
    },

    async generateImage(fieldKey, textPrompt) {
      if (!textPrompt || this.generatingImage) return;
      this.generatingImage = fieldKey;

      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.generate_image",
          args: {
            prompt: this.stripHtml(textPrompt),
            style: this.imageStyle,
            field_context: fieldKey,
          },
        });

        if (r.message && r.message.file_url) {
          if (fieldKey.startsWith("option_") && fieldKey.endsWith("_image")) {
            var idx = parseInt(fieldKey.split("_")[1]) - 1;
            this.currentQ().options[idx].image = r.message.file_url;
          } else {
            this.currentQ()[fieldKey] = r.message.file_url;
          }
          this.persistState();
          frappe.show_alert({ message: "Image generated", indicator: "green" });
        }
      } catch (e) {
        // error shown by frappe
      }

      this.generatingImage = null;
      this.replaceIcons();
    },

    // --- File upload ---

    handleFileSelect(event) {
      var file = event.target.files[0];
      if (file) this.processFile(file);
    },

    handleFileDrop(event) {
      this.fileDragOver = false;
      var file = event.dataTransfer.files[0];
      if (file) this.processFile(file);
    },

    processFile(file) {
      this.fileError = "";
      var validTypes = ["text/plain", "text/csv", "application/vnd.ms-excel"];
      var validExts = [".txt", ".csv"];
      var ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();

      if (!validTypes.includes(file.type) && !validExts.includes(ext)) {
        this.fileError = "Only .txt and .csv files are supported.";
        return;
      }

      if (file.size > 2 * 1024 * 1024) {
        this.fileError = "File must be under 2 MB.";
        return;
      }

      var self = this;
      var reader = new FileReader();
      reader.onload = function(e) {
        self.fileContent = e.target.result;
        self.uploadedFile = { name: file.name, size: file.size };
        self.replaceIcons();
      };
      reader.onerror = function() {
        self.fileError = "Failed to read file.";
      };
      reader.readAsText(file);
    },

    removeFile() {
      this.uploadedFile = null;
      this.fileContent = "";
      this.fileError = "";
      if (this.$refs.fileInput) this.$refs.fileInput.value = "";
      this.replaceIcons();
    },

    formatFileSize(bytes) {
      if (bytes < 1024) return bytes + " B";
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
      return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    },

    // --- Generate ---

    async generateQuestions() {
      if (!this.category || (!this.prompt.trim() && !this.fileContent)) return;
      this.generating = true;
      this.generatedQuestions = [];
      this.selectedIndex = null;

      try {
        var args = {
          category: this.category,
          count: this.count,
          difficulty: this.difficulty,
          question_type: this.questionType,
          prompt: this.prompt,
          mark: this.mark,
        };
        if (this.fileContent) {
          args.file_content = this.fileContent;
        }

        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.generate_questions",
          args: args,
        });

        if (r.message && r.message.questions) {
          this.generatedQuestions = r.message.questions;
          this.persistState();
        }
      } catch (e) {
        // frappe.call already shows the error via msgprint
      }

      this.generating = false;
      this.replaceIcons();
    },

    // --- Modal actions for generated questions ---

    insertFromModal() {
      var idx = this.selectedIndex;
      var q = this.generatedQuestions.splice(idx, 1)[0];
      this.approvedQuestions.push(q);
      this.persistState();
      this.closeModal();
      this.replaceIcons();
    },

    async regenerateFromModal() {
      this.regenerating = true;
      var idx = this.selectedIndex;
      var original = this.generatedQuestions[idx];

      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.generate_questions",
          args: {
            category: original.category || this.category,
            count: 1,
            difficulty: original.difficulty || this.difficulty,
            question_type: original.type || this.questionType,
            prompt: this.prompt,
            mark: original.mark || this.mark,
          },
        });

        if (r.message && r.message.questions && r.message.questions.length > 0) {
          this.generatedQuestions.splice(idx, 1, r.message.questions[0]);
          this.ensureHelpFields(this.generatedQuestions[idx]);
          this.persistState();
        }
      } catch (e) {
        // error shown by frappe
      }

      this.regenerating = false;
      this.replaceIcons();
    },

    insertAll() {
      this.approvedQuestions.push(...this.generatedQuestions);
      this.generatedQuestions = [];
      this.persistState();
      this.replaceIcons();
    },

    // --- Modal actions for approved questions ---

    async updateQuestion() {
      var q = this.currentQ();
      if (!q) return;

      if (q._existing && q.name) {
        this.updating = true;
        try {
          await frappe.call({
            method: "exampro.exam_pro.api.exam_studio.update_question",
            args: { name: q.name, data: JSON.stringify(q) },
          });
          frappe.show_alert({ message: "Question updated", indicator: "green" });
        } catch (e) {
          // error shown by frappe
        }
        this.updating = false;
      } else {
        this.persistState();
        frappe.show_alert({ message: "Changes saved locally", indicator: "blue" });
      }
    },

    removeFromModal() {
      this.approvedQuestions.splice(this.selectedIndex, 1);
      this.persistState();
      this.closeModal();
      this.replaceIcons();
    },

    removeApproved(index) {
      this.approvedQuestions.splice(index, 1);
      this.persistState();
      this.replaceIcons();
    },

    // --- Category ---

    async createCategory() {
      var name = this.newCategoryName.trim();
      if (!name) return;

      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.create_category",
          args: { title: name },
        });

        if (r.message) {
          var newCat = {
            name: r.message.name,
            title: r.message.title,
            question_count: 0,
          };
          this.allCategories.unshift(newCat);
          this.categories.unshift(newCat);
          this.category = r.message.name;
          this.newCategoryName = "";
          this.showNewCategory = false;
          this.approvedQuestions = [];
          this.persistState();
          frappe.show_alert({ message: "Category created", indicator: "green" });
        }
      } catch (e) {
        // error shown by frappe
      }
    },

    openNewQuestionModal() {
      if (!this.category) return;
      var blank = {
        question: "",
        type: "Choices",
        category: this.category,
        mark: 1,
        difficulty: "Medium",
        options: [
          { text: "", is_correct: false, explanation: "", image: "" },
          { text: "", is_correct: false, explanation: "", image: "" },
          { text: "", is_correct: false, explanation: "", image: "" },
          { text: "", is_correct: false, explanation: "", image: "" },
        ],
        possible_answers: [""],
        help_show: "Do not show",
        help_type: "Text",
        help_text: "",
        help_link: "",
        help_quiz: [],
        description_image: "",
        helper_text_image: "",
        _existing: false,
      };
      this.approvedQuestions.unshift(blank);
      this.openModal(0, "approved");
    },

    openNewCategoryModal() {
      this.newCategoryName = "";
      if (this._newCategoryModal) this._newCategoryModal.show();
      this.replaceIcons();
    },

    async createCategoryFromModal() {
      await this.createCategory();
      if (this._newCategoryModal) this._newCategoryModal.hide();
    },

    // --- Save all ---

    async saveAll() {
      var newQuestions = this.approvedQuestions.filter(function(q) { return !q._existing; });
      if (newQuestions.length === 0) {
        frappe.show_alert({ message: "No new questions to save", indicator: "orange" });
        return;
      }
      this.saving = true;

      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.save_questions",
          args: {
            questions: JSON.stringify(newQuestions),
          },
        });

        if (r.message) {
          var msg = r.message;
          frappe.show_alert({
            message: msg.created + " question(s) saved successfully" +
              (msg.failed.length > 0
                ? ". " + msg.failed.length + " failed."
                : ""),
            indicator: msg.failed.length > 0 ? "orange" : "green",
          });

          if (msg.created > 0) {
            this.onCategoryChange();
          }
        }
      } catch (e) {
        // error shown by frappe
      }

      this.saving = false;
    },

    // =============================================
    // Exams Tab Methods
    // =============================================

    formatDateTime(dt) {
      if (!dt) return "";
      var d = new Date(dt);
      return d.toLocaleDateString("en-IN", {
        day: "numeric", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    },

    async selectExam(exam) {
      this.selectedExam = exam;
      this.selectedSchedule = null;
      this.candidates = [];
      this.schedules = [];
      await this.loadSchedules(exam.name);
      this.replaceIcons();
    },

    async loadSchedules(examName) {
      this.loadingSchedules = true;
      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.get_exam_schedules",
          args: { exam: examName },
        });
        this.schedules = r.message || [];
      } catch (e) {
        this.schedules = [];
      }
      this.loadingSchedules = false;
      this.replaceIcons();
    },

    async selectSchedule(sch) {
      this.selectedSchedule = sch;
      this.candidates = [];
      await this.loadCandidates(sch.name);
      this.replaceIcons();
    },

    async loadCandidates(scheduleName) {
      this.loadingCandidates = true;
      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.get_schedule_candidates",
          args: { schedule: scheduleName },
        });
        this.candidates = r.message || [];
      } catch (e) {
        this.candidates = [];
      }
      this.loadingCandidates = false;
      this.replaceIcons();
    },

    // --- Exam search ---

    async searchExams() {
      var q = (this.examSearchQuery || "").trim();
      if (!q) {
        this.exams = window.examStudioData?.exams || [];
        this.replaceIcons();
        return;
      }
      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.search_exams",
          args: { query: q },
        });
        this.exams = r.message || [];
      } catch (e) {
        this.exams = [];
      }
      this.replaceIcons();
    },

    clearExamSearch() {
      this.examSearchQuery = "";
      this.exams = window.examStudioData?.exams || [];
      this.replaceIcons();
    },

    // --- Edit shortcuts ---

    toggleExamDropdown(examName) {
      if (this.examDropdownOpen === examName) {
        this.examDropdownOpen = null;
        return;
      }
      this.examDropdownOpen = examName;
      var btn = this.$event.currentTarget;
      this.$nextTick(() => {
        var menu = btn.closest('.quiz-dropdown-wrap').querySelector('.quiz-dropdown-menu');
        if (!menu) return;
        var rect = btn.getBoundingClientRect();
        menu.style.top = (rect.bottom + 2) + 'px';
        menu.style.right = (window.innerWidth - rect.right) + 'px';
        menu.style.left = 'auto';
        this.replaceIcons();
      });
    },

    toggleScheduleDropdown(scheduleName) {
      if (this.scheduleDropdownOpen === scheduleName) {
        this.scheduleDropdownOpen = null;
        return;
      }
      this.scheduleDropdownOpen = scheduleName;
      var btn = this.$event.currentTarget;
      this.$nextTick(() => {
        var menu = btn.closest('.quiz-dropdown-wrap').querySelector('.quiz-dropdown-menu');
        if (!menu) return;
        var rect = btn.getBoundingClientRect();
        menu.style.top = (rect.bottom + 2) + 'px';
        menu.style.right = (window.innerWidth - rect.right) + 'px';
        menu.style.left = 'auto';
        this.replaceIcons();
      });
    },

    copyScheduleInviteLink(sch) {
      if (!sch.short_uuid) {
        frappe.show_alert({ message: "Invite link not available for this schedule.", indicator: "red" });
        return;
      }
      const link = window.location.origin + "/exam/invite/" + sch.short_uuid;
      navigator.clipboard.writeText(link).then(() => {
        frappe.show_alert({ message: "Invite link copied to clipboard.", indicator: "green" });
      }).catch(() => {
        frappe.show_alert({ message: "Could not copy link. Please copy manually: " + link, indicator: "orange" });
      });
    },

    async openCertificatePdf(certificateName) {
      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.doctype.exam_certificate.exam_certificate.download_certificate_pdf",
          args: { certificate_name: certificateName },
        });
        if (r.message) {
          const binary = atob(r.message);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
          const blob = new Blob([bytes], { type: "application/pdf" });
          const url = URL.createObjectURL(blob);
          window.open(url, "_blank");
        }
      } catch (e) {
        // error shown by frappe
      }
    },

    sendScheduleCertificates(sch) {
      frappe.confirm(
        `Send certificates to all passing candidates for schedule <strong>${sch.name}</strong>? This will create certificate records for eligible submissions.`,
        async () => {
          try {
            const r = await frappe.call({
              method: "exampro.exam_pro.doctype.exam_schedule.exam_schedule.send_certificates",
              args: { docname: sch.name },
            });
            frappe.show_alert({ message: "Certificates sent successfully.", indicator: "green" });
          } catch (e) {
            // error shown by frappe
          }
        }
      );
    },

    async duplicateExam(exam) {
      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.duplicate_exam",
          args: { name: exam.name },
        });
        if (r.message) {
          this.exams.unshift(r.message);
          frappe.show_alert({ message: "Exam duplicated", indicator: "green" });
          this.replaceIcons();
        }
      } catch (e) {
        // error shown by frappe
      }
    },

    async editExam(exam) {
      this.examModalMode = "edit";
      this.examModalTab = "details";
      this.examForm = {
        name: exam.name,
        title: exam.title || "",
        exam_mode: exam.exam_mode || "Exam",
        duration: exam.duration || 60,
        pass_percentage: exam.pass_percentage || 50,
        question_type: exam.question_type || "Choices",
        description: "",
        instructions: "",
        randomize_questions: false,
        select_questions: [],
        enable_certification: false,
        expiry: 0,
        certificate_template: "",
        partner: "",
        partner_manages_questions: false,
        is_public: false,
        enable_payment: false,
        price: 0,
        enable_video_proctoring: false,
        enable_screen_recording: false,
        enable_chat: false,
        enable_calculator: false,
        max_warning_count: 3,
      };
      if (this._examModal) this._examModal.show();
      this.syncExamEditors();

      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.get_exam_detail",
          args: { name: exam.name },
        });
        if (r.message) {
          var detail = r.message;
          this.examForm.description = detail.description || "";
          this.examForm.instructions = detail.instructions || "";
          this.examForm.randomize_questions = detail.randomize_questions || false;
          this.examForm.pass_percentage = detail.pass_percentage || 50;
          this.examForm.select_questions = (detail.select_questions || []).map(function(sq) {
            return {
              question_category: sq.question_category,
              no_of_questions: sq.no_of_questions,
              mark_per_question: sq.mark_per_question,
            };
          });
          this.examForm.enable_certification = detail.enable_certification || false;
          this.examForm.expiry = detail.expiry || 1;
          this.examForm.certificate_template = detail.certificate_template || "";
          this.examForm.partner = detail.partner || "";
          this.examForm.partner_manages_questions = detail.partner_manages_questions || false;
          this.examForm.is_public = detail.is_public || false;
          this.examForm.enable_payment = detail.enable_payment || false;
          this.examForm.price = detail.price || 0;
          this.examForm.enable_video_proctoring = detail.enable_video_proctoring || false;
          this.examForm.enable_screen_recording = detail.enable_screen_recording || false;
          this.examForm.enable_chat = detail.enable_chat || false;
          this.examForm.enable_calculator = detail.enable_calculator || false;
          this.examForm.max_warning_count = detail.max_warning_count !== undefined ? detail.max_warning_count : 3;
        }
      } catch (e) {
        // keep modal open with basic data
      }
      this.syncExamEditors();
    },

    editSchedule(sch) {
      this.openScheduleModal("edit", sch);
    },

    // --- Exam modal ---

    syncExamEditors() {
      this.$nextTick(() => {
        if (this.$refs.examDescriptionEditor) {
          this.$refs.examDescriptionEditor.innerHTML = this.examForm.description || "";
        }
        if (this.$refs.examInstructionsEditor) {
          this.$refs.examInstructionsEditor.innerHTML = this.examForm.instructions || "";
        }
        this.replaceIcons();
      });
    },

    openExamModal(mode, exam) {
      this.examModalMode = mode;
      this.examModalTab = "details";
      if (mode === "edit" && exam) {
        this.examForm = {
          name: exam.name,
          title: exam.title || "",
          exam_mode: exam.exam_mode || "Exam",
          duration: exam.duration || 60,
          pass_percentage: exam.pass_percentage || 50,
          question_type: exam.question_type || "Choices",
          description: exam.description || "",
          instructions: exam.instructions || "",
          randomize_questions: exam.randomize_questions || false,
          select_questions: (exam.select_questions || []).map(function(sq) {
            return {
              question_category: sq.question_category,
              no_of_questions: sq.no_of_questions,
              mark_per_question: sq.mark_per_question,
            };
          }),
          enable_certification: exam.enable_certification || false,
          expiry: (exam.expiry != null ? exam.expiry : 0),
          certificate_template: exam.certificate_template || "",
          partner: exam.partner || "",
          partner_manages_questions: exam.partner_manages_questions || false,
          is_public: exam.is_public || false,
          enable_payment: exam.enable_payment || false,
          price: exam.price || 0,
          enable_video_proctoring: exam.enable_video_proctoring || false,
          enable_screen_recording: exam.enable_screen_recording || false,
          enable_chat: exam.enable_chat || false,
          enable_calculator: exam.enable_calculator || false,
          max_warning_count: exam.max_warning_count !== undefined ? exam.max_warning_count : 3,
        };
      } else {
        this.examForm = {
          name: "",
          title: "",
          exam_mode: "Exam",
          duration: 60,
          pass_percentage: 50,
          question_type: "Choices",
          description: "",
          instructions: "",
          randomize_questions: false,
          select_questions: [],
          enable_certification: false,
          expiry: 0,
          certificate_template: "",
          partner: "",
          partner_manages_questions: false,
          is_public: false,
          enable_payment: false,
          price: 0,
          enable_video_proctoring: false,
          enable_screen_recording: false,
          enable_chat: false,
          enable_calculator: false,
          max_warning_count: 3,
        };
      }
      if (this._examModal) this._examModal.show();
      this.syncExamEditors();
    },

    addExamCategory() {
      this.examForm.select_questions.push({
        question_category: "",
        no_of_questions: 1,
        mark_per_question: 1,
      });
      this.replaceIcons();
    },

    async saveExam() {
      if (!this.examForm.title || !this.examForm.duration || !this.examForm.description) return;
      this.savingExam = true;

      try {
        var payload = {
          title: this.examForm.title,
          exam_mode: this.examForm.exam_mode,
          duration: this.examForm.duration,
          pass_percentage: this.examForm.pass_percentage,
          question_type: this.examForm.question_type,
          description: this.examForm.description,
          instructions: this.examForm.instructions,
          randomize_questions: this.examForm.randomize_questions,
          select_questions: this.examForm.select_questions.filter(function(sq) {
            return sq.question_category;
          }),
          enable_certification: this.examForm.enable_certification,
          expiry: this.examForm.expiry,
          certificate_template: this.examForm.certificate_template,
          partner: this.examForm.partner,
          partner_manages_questions: this.examForm.partner_manages_questions,
          is_public: this.examForm.is_public,
          enable_payment: this.examForm.enable_payment,
          price: this.examForm.price,
          enable_video_proctoring: this.examForm.enable_video_proctoring,
          enable_screen_recording: this.examForm.enable_screen_recording,
          enable_chat: this.examForm.enable_chat,
          enable_calculator: this.examForm.enable_calculator,
          max_warning_count: this.examForm.max_warning_count,
        };
        if (this.examModalMode === "edit" && this.examForm.name) {
          payload.name = this.examForm.name;
        }

        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.save_exam",
          args: { data: JSON.stringify(payload) },
        });

        if (r.message) {
          var result = r.message;
          if (this.examModalMode === "create") {
            this.exams.unshift(result);
            frappe.show_alert({ message: "Exam created", indicator: "green" });
          } else {
            var idx = this.exams.findIndex(function(e) { return e.name === result.name; });
            if (idx >= 0) {
              this.exams[idx] = result;
            }
            frappe.show_alert({ message: "Exam updated", indicator: "green" });
          }
        }

        if (this._examModal) this._examModal.hide();
      } catch (e) {
        // error shown by frappe
      }

      this.savingExam = false;
      this.replaceIcons();
    },

    // --- Schedule modal ---

    openScheduleModal(mode, sch) {
      this.scheduleModalMode = mode || "create";
      this.conflictingSchedules = [];
      this.conflictsChecked = false;
      this.loadingConflicts = false;
      if (mode === "edit" && sch) {
        var dt = (sch.start_date_time || "").replace(" ", "T");
        if (dt.length > 16) dt = dt.substring(0, 16);
        this.scheduleForm = {
          name: sch.name,
          schedule_name: sch.name,
          start_date_time: dt,
          schedule_type: sch.schedule_type || "Fixed",
          schedule_expire_in_days: sch.schedule_expire_in_days || 7,
          badge: sch.badge || "",
        };
      } else {
        this.scheduleForm = {
          name: "",
          schedule_name: "",
          start_date_time: "",
          schedule_type: "Fixed",
          schedule_expire_in_days: 7,
          badge: "",
        };
      }
      if (this._scheduleModal) this._scheduleModal.show();
      this._initScheduleDatetime();
      if (this.scheduleForm.start_date_time) {
        this.checkConflicts(this.scheduleForm.start_date_time);
      }
      this.replaceIcons();
    },

    _initScheduleDatetime() {
      var el = document.getElementById("schedule-datetime-picker");
      if (!el) return;
      if (this._scheduleDatetimePicker) this._scheduleDatetimePicker.destroy();
      var self = this;
      var defaultDate = this.scheduleForm.start_date_time
        ? this.scheduleForm.start_date_time.replace("T", " ")
        : null;
      this._scheduleDatetimePicker = flatpickr(el, {
        enableTime: true,
        dateFormat: "Y-m-d H:i",
        time_24hr: true,
        defaultDate: defaultDate,
        onChange: function (selectedDates, dateStr) {
          self.scheduleForm.start_date_time = dateStr ? dateStr + ":00" : "";
          self.checkConflicts(self.scheduleForm.start_date_time);
        },
      });
    },

    async checkConflicts(dateStr) {
      if (!dateStr || !this.selectedExam) {
        this.conflictingSchedules = [];
        this.conflictsChecked = false;
        return;
      }
      this.loadingConflicts = true;
      try {
        var startDt = dateStr.replace("T", " ");
        if (startDt.length === 16) startDt += ":00";
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.get_conflicting_schedules",
          args: {
            start_date_time: startDt,
            duration_minutes: this.selectedExam.duration || 0,
            exclude_schedule: this.scheduleForm.name || null,
          },
        });
        this.conflictingSchedules = r.message || [];
        this.conflictsChecked = true;
      } catch (e) {
        this.conflictingSchedules = [];
        this.conflictsChecked = false;
      }
      this.loadingConflicts = false;
      this.replaceIcons();
    },

    async saveSchedule() {
      if (!this.scheduleForm.start_date_time || !this.selectedExam) return;

      if (this.conflictingSchedules.length > 0) {
        const count = this.conflictingSchedules.length;
        const confirmed = await new Promise(resolve => {
          frappe.confirm(
            `This schedule overlaps with ${count} other exam${count > 1 ? "s" : ""}. Do you want to continue?`,
            () => resolve(true),
            () => resolve(false)
          );
        });
        if (!confirmed) return;
      }

      this.savingSchedule = true;

      try {
        var startDt = this.scheduleForm.start_date_time.replace("T", " ");
        if (startDt.length === 16) startDt += ":00";

        var payload = {
          exam: this.selectedExam.name,
          schedule_name: this.scheduleForm.schedule_name,
          start_date_time: startDt,
          schedule_type: this.scheduleForm.schedule_type,
          badge: this.scheduleForm.badge || "",
        };
        if (this.scheduleForm.schedule_type === "Flexible") {
          payload.schedule_expire_in_days = this.scheduleForm.schedule_expire_in_days;
        }
        if (this.scheduleModalMode === "edit" && this.scheduleForm.name) {
          payload.name = this.scheduleForm.name;
        }

        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.save_schedule",
          args: { data: JSON.stringify(payload) },
        });

        if (r.message) {
          var label = this.scheduleModalMode === "create" ? "Schedule created" : "Schedule updated";
          frappe.show_alert({ message: label, indicator: "green" });
          await this.loadSchedules(this.selectedExam.name);
        }

        if (this._scheduleModal) this._scheduleModal.hide();
      } catch (e) {
        // error shown by frappe
      }

      this.savingSchedule = false;
      this.replaceIcons();
    },

    // --- Candidate modal ---

    openCandidateModal() {
      this.candidateAddMode = "search";
      this.candidateEmails = "";
      this.candidateSearchQuery = "";
      this.candidateSearchResults = [];
      this.selectedUsers = [];
      this.candidateBatch = "";
      if (this._candidateModal) this._candidateModal.show();
      this.replaceIcons();
    },

    async searchUsers() {
      var q = (this.candidateSearchQuery || "").trim();
      if (q.length < 2) {
        this.candidateSearchResults = [];
        return;
      }

      try {
        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.search_users",
          args: { query: q },
        });
        this.candidateSearchResults = r.message || [];
      } catch (e) {
        this.candidateSearchResults = [];
      }
    },

    toggleUserSelection(user) {
      var idx = this.selectedUsers.indexOf(user.name);
      if (idx >= 0) {
        this.selectedUsers.splice(idx, 1);
      } else {
        this.selectedUsers.push(user.name);
      }
    },

    async addCandidates() {
      if (!this.selectedSchedule) return;
      this.addingCandidates = true;

      try {
        var args = { schedule_name: this.selectedSchedule.name };

        if (this.candidateAddMode === "search") {
          args.emails = this.selectedUsers.join(",");
        } else if (this.candidateAddMode === "email") {
          args.emails = this.candidateEmails;
        } else if (this.candidateAddMode === "batch") {
          args.batch_name = this.candidateBatch;
        }

        const r = await frappe.call({
          method: "exampro.exam_pro.api.exam_studio.add_candidates_to_schedule",
          args: args,
        });

        if (r.message) {
          var msg = r.message;
          var text = msg.added + " candidate(s) added";
          if (msg.duplicates > 0) text += ", " + msg.duplicates + " already registered";
          if (msg.invalid_users && msg.invalid_users.length > 0) {
            text += ", " + msg.invalid_users.length + " invalid";
          }
          frappe.show_alert({
            message: text,
            indicator: msg.added > 0 ? "green" : "orange",
          });

          await this.loadCandidates(this.selectedSchedule.name);

          if (this.selectedExam) {
            await this.loadSchedules(this.selectedExam.name);
          }
        }

        if (this._candidateModal) this._candidateModal.hide();
      } catch (e) {
        // error shown by frappe
      }

      this.addingCandidates = false;
      this.replaceIcons();
    },
  };
}

window.examStudioApp = examStudioApp;
