function examStudioApp() {
  return {
    aiConfigured: window.examStudioData?.aiConfigured || false,
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
    generatedQuestions: [],
    selectedIndex: null,
    editSource: "generated",
    modalTab: "question",

    approvedQuestions: [],
    saving: false,
    loadingExisting: false,

    _cacheTimer: null,
    _modal: null,

    init() {
      this.restoreState();
      this.$nextTick(() => {
        if (typeof feather !== "undefined") feather.replace();
        this._modal = new bootstrap.Modal(document.getElementById("questionEditorModal"));
      });
    },

    replaceIcons() {
      this.$nextTick(() => {
        if (typeof feather !== "undefined") feather.replace();
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
      if (q.help_text === undefined) q.help_text = "";
      if (q.help_quiz === undefined) q.help_quiz = [];
    },

    openModal(index, source) {
      this.selectedIndex = index;
      this.editSource = source;
      this.modalTab = "question";
      this.ensureHelpFields(this.currentQ());
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
          method: "frappe.client.insert",
          args: {
            doc: {
              doctype: "Exam Question Category",
              title: name,
            },
          },
        });

        if (r.message) {
          this.categories.push({
            name: r.message.name,
            title: r.message.title,
          });
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
  };
}

window.examStudioApp = examStudioApp;
