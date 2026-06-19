function usersStudioApp() {
  return {
    batches: [],
    selectedBatch: null,
    batchUsers: [],
    batchSearchQuery: "",
    userFilterQuery: "",

    loadingUsers: false,
    addingUsers: false,
    creatingUser: false,
    removingUser: null,
    creatingBatch: false,
    importingCsv: false,

    addMode: "new",

    existingAddMode: "search",
    searchQuery: "",
    searchResults: [],
    selectedEmails: [],
    bulkEmailsText: "",
    _addExistingModal: null,

    newUserForm: { email: "", first_name: "", last_name: "" },

    csvFile: null,
    csvParsed: [],
    csvError: "",
    csvDragOver: false,

    batchForm: { batch_name: "", description: "" },
    _batchModal: null,

    get filteredBatches() {
      if (!this.batchSearchQuery) return this.batches;
      var q = this.batchSearchQuery.toLowerCase();
      return this.batches.filter(function(b) {
        return (b.batch_name || "").toLowerCase().includes(q) ||
               (b.description || "").toLowerCase().includes(q);
      });
    },

    get filteredUsers() {
      if (!this.userFilterQuery) return this.batchUsers;
      var q = this.userFilterQuery.toLowerCase();
      return this.batchUsers.filter(function(u) {
        return (u.full_name || "").toLowerCase().includes(q) ||
               (u.candidate || "").toLowerCase().includes(q);
      });
    },

    init() {
      this.loadBatches();
      this.$nextTick(function() {
        var el = document.getElementById("batchCreateModal");
        if (el) this._batchModal = new bootstrap.Modal(el);
        var el2 = document.getElementById("addExistingUsersModal");
        if (el2) this._addExistingModal = new bootstrap.Modal(el2);
        if (typeof feather !== "undefined") feather.replace();
      }.bind(this));
    },

    replaceIcons() {
      this.$nextTick(function() {
        if (typeof feather !== "undefined") feather.replace();
      });
    },

    loadBatches() {
      var self = this;
      frappe.call({
        method: "exampro.exam_pro.api.exam_studio.get_batches_with_counts",
        callback: function(r) {
          self.batches = r.message || [];
          self.replaceIcons();
        },
      });
    },

    selectBatch(batch) {
      this.selectedBatch = batch;
      this.userFilterQuery = "";
      this.searchQuery = "";
      this.searchResults = [];
      this.selectedEmails = [];
      this.loadBatchUsers(batch.name);
    },

    loadBatchUsers(batchName) {
      var self = this;
      self.loadingUsers = true;
      frappe.call({
        method: "exampro.exam_pro.api.exam_studio.get_batch_users",
        args: { batch_name: batchName },
        callback: function(r) {
          self.batchUsers = r.message || [];
          self.loadingUsers = false;
          self.refreshBatchCount(batchName);
          self.replaceIcons();
        },
        error: function() {
          self.loadingUsers = false;
        },
      });
    },

    openBatchModal() {
      this.batchForm = { batch_name: "", description: "" };
      if (this._batchModal) this._batchModal.show();
      this.replaceIcons();
    },

    createBatch() {
      var self = this;
      if (!self.batchForm.batch_name.trim()) return;
      self.creatingBatch = true;
      frappe.call({
        method: "exampro.exam_pro.api.exam_studio.create_batch",
        args: {
          batch_name: self.batchForm.batch_name.trim(),
          description: self.batchForm.description.trim(),
        },
        callback: function(r) {
          self.creatingBatch = false;
          if (r.message) {
            self.batches.push(r.message);
            if (self._batchModal) self._batchModal.hide();
            frappe.show_alert({ message: "Batch created", indicator: "green" });
            self.selectBatch(r.message);
          }
        },
        error: function() {
          self.creatingBatch = false;
        },
      });
    },

    searchExistingUsers() {
      var self = this;
      if (!self.searchQuery || self.searchQuery.length < 2) {
        self.searchResults = [];
        return;
      }
      frappe.call({
        method: "exampro.exam_pro.api.exam_studio.search_users",
        args: { query: self.searchQuery },
        callback: function(r) {
          self.searchResults = r.message || [];
          self.replaceIcons();
        },
      });
    },

    toggleUserSelection(email) {
      var idx = this.selectedEmails.indexOf(email);
      if (idx === -1) {
        this.selectedEmails.push(email);
      } else {
        this.selectedEmails.splice(idx, 1);
      }
    },

    addSelectedUsers() {
      var self = this;
      if (self.selectedEmails.length === 0 || !self.selectedBatch) return;
      self.addingUsers = true;
      frappe.call({
        method: "exampro.exam_pro.api.exam_studio.add_users_to_batch",
        args: {
          batch_name: self.selectedBatch.name,
          emails: self.selectedEmails.join(","),
        },
        callback: function(r) {
          self.addingUsers = false;
          var d = r.message || {};
          var parts = [];
          if (d.added) parts.push(d.added + " added");
          if (d.skipped) parts.push(d.skipped + " already in batch");
          if (d.not_found && d.not_found.length) parts.push(d.not_found.length + " not found");
          frappe.show_alert({ message: parts.join(", ") || "Done", indicator: d.added ? "green" : "orange" });
          self.selectedEmails = [];
          self.searchQuery = "";
          self.searchResults = [];
          self.loadBatchUsers(self.selectedBatch.name);
          self.refreshBatchCount(self.selectedBatch.name);
        },
        error: function() {
          self.addingUsers = false;
        },
      });
    },

    openAddExistingModal() {
      this.existingAddMode = "search";
      this.searchQuery = "";
      this.searchResults = [];
      this.selectedEmails = [];
      this.bulkEmailsText = "";
      if (this._addExistingModal) this._addExistingModal.show();
      this.replaceIcons();
    },

    addExistingUsersFromModal() {
      var self = this;
      if (!self.selectedBatch) return;

      var emails;
      if (self.existingAddMode === "search") {
        if (self.selectedEmails.length === 0) return;
        emails = self.selectedEmails.join(",");
      } else {
        if (!self.bulkEmailsText.trim()) return;
        emails = self.bulkEmailsText.trim();
      }

      self.addingUsers = true;
      frappe.call({
        method: "exampro.exam_pro.api.exam_studio.add_users_to_batch",
        args: {
          batch_name: self.selectedBatch.name,
          emails: emails,
        },
        callback: function(r) {
          self.addingUsers = false;
          var d = r.message || {};
          var parts = [];
          if (d.added) parts.push(d.added + " added");
          if (d.skipped) parts.push(d.skipped + " already in batch");
          if (d.not_found && d.not_found.length) parts.push(d.not_found.length + " not found");
          frappe.show_alert({ message: parts.join(", ") || "Done", indicator: d.added ? "green" : "orange" });
          if (self._addExistingModal) self._addExistingModal.hide();
          self.selectedEmails = [];
          self.searchQuery = "";
          self.searchResults = [];
          self.bulkEmailsText = "";
          self.loadBatchUsers(self.selectedBatch.name);
          self.refreshBatchCount(self.selectedBatch.name);
        },
        error: function() {
          self.addingUsers = false;
        },
      });
    },

    createAndAddUser() {
      var self = this;
      if (!self.newUserForm.email || !self.newUserForm.first_name || !self.selectedBatch) return;
      self.creatingUser = true;
      frappe.call({
        method: "exampro.exam_pro.api.exam_studio.create_users_and_add_to_batch",
        args: {
          batch_name: self.selectedBatch.name,
          users_data: JSON.stringify([{
            email: self.newUserForm.email.trim(),
            first_name: self.newUserForm.first_name.trim(),
            last_name: self.newUserForm.last_name.trim(),
          }]),
        },
        callback: function(r) {
          self.creatingUser = false;
          var d = r.message || {};
          if (d.errors && d.errors.length) {
            frappe.show_alert({ message: d.errors[0].error, indicator: "red" });
            return;
          }
          if (d.skipped) {
            frappe.show_alert({ message: "User already exists", indicator: "orange" });
          } else if (d.created) {
            frappe.show_alert({ message: "User created and added to batch", indicator: "green" });
          }
          self.newUserForm = { email: "", first_name: "", last_name: "" };
          self.loadBatchUsers(self.selectedBatch.name);
          self.refreshBatchCount(self.selectedBatch.name);
        },
        error: function() {
          self.creatingUser = false;
        },
      });
    },

    removeUser(user) {
      var self = this;
      self.removingUser = user.candidate;
      frappe.call({
        method: "exampro.exam_pro.api.exam_studio.remove_user_from_batch",
        args: {
          batch_name: self.selectedBatch.name,
          email: user.candidate,
        },
        callback: function() {
          self.removingUser = null;
          self.batchUsers = self.batchUsers.filter(function(u) { return u.candidate !== user.candidate; });
          self.refreshBatchCount(self.selectedBatch.name);
          frappe.show_alert({ message: "User removed", indicator: "green" });
        },
        error: function() {
          self.removingUser = null;
        },
      });
    },

    refreshBatchCount(batchName) {
      var batch = this.batches.find(function(b) { return b.name === batchName; });
      if (batch) {
        batch.user_count = this.batchUsers.length;
      }
    },

    handleCsvSelect(event) {
      var file = event.target.files[0];
      if (file) this.processCsvFile(file);
    },

    handleCsvDrop(event) {
      var file = event.dataTransfer.files[0];
      if (file) this.processCsvFile(file);
    },

    processCsvFile(file) {
      if (!file.name.toLowerCase().endsWith(".csv")) {
        this.csvError = "Please upload a .csv file";
        return;
      }
      var self = this;
      self.csvFile = file;
      self.csvError = "";
      self.csvParsed = [];

      var reader = new FileReader();
      reader.onload = function(e) {
        self.parseCsv(e.target.result);
        self.replaceIcons();
      };
      reader.readAsText(file);
    },

    parseCsv(content) {
      var lines = content.split(/\r?\n/).filter(function(l) { return l.trim(); });
      if (lines.length < 2) {
        this.csvError = "CSV must have a header row and at least one data row";
        return;
      }

      var headerLine = lines[0].toLowerCase();
      var headers = headerLine.split(",").map(function(h) { return h.trim().replace(/^["']|["']$/g, ""); });
      var emailIdx = headers.indexOf("email");
      var fnIdx = headers.indexOf("first_name");
      var lnIdx = headers.indexOf("last_name");

      if (emailIdx === -1) {
        this.csvError = "CSV must have an 'email' column";
        return;
      }
      if (fnIdx === -1) {
        this.csvError = "CSV must have a 'first_name' column";
        return;
      }

      var parsed = [];
      for (var i = 1; i < lines.length; i++) {
        var cols = lines[i].split(",").map(function(c) { return c.trim().replace(/^["']|["']$/g, ""); });
        parsed.push({
          email: cols[emailIdx] || "",
          first_name: cols[fnIdx] || "",
          last_name: lnIdx !== -1 ? (cols[lnIdx] || "") : "",
        });
      }
      this.csvParsed = parsed;
    },

    downloadCsvTemplate() {
      var csv = "email,first_name,last_name\n";
      var blob = new Blob([csv], { type: "text/csv" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "users_template.csv";
      a.click();
      URL.revokeObjectURL(a.href);
    },

    removeCsvFile() {
      this.csvFile = null;
      this.csvParsed = [];
      this.csvError = "";
      if (this.$refs.csvFileInput) this.$refs.csvFileInput.value = "";
    },

    importCsvUsers() {
      var self = this;
      if (self.csvParsed.length === 0 || !self.selectedBatch) return;
      self.importingCsv = true;
      frappe.call({
        method: "exampro.exam_pro.api.exam_studio.create_users_and_add_to_batch",
        args: {
          batch_name: self.selectedBatch.name,
          users_data: JSON.stringify(self.csvParsed),
        },
        callback: function(r) {
          self.importingCsv = false;
          var d = r.message || {};
          var parts = [];
          if (d.created) parts.push(d.created + " created");
          if (d.skipped) parts.push(d.skipped + " existing skipped");
          if (d.errors && d.errors.length) parts.push(d.errors.length + " errors");
          frappe.show_alert({ message: parts.join(", ") || "Done", indicator: d.created ? "green" : "orange" });
          self.removeCsvFile();
          self.loadBatchUsers(self.selectedBatch.name);
          self.refreshBatchCount(self.selectedBatch.name);
        },
        error: function() {
          self.importingCsv = false;
        },
      });
    },
  };
}
window.usersStudioApp = usersStudioApp;
