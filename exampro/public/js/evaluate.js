/**
 * ExamPro Evaluation Dashboard - Alpine.js App
 */

function evaluationApp() {
  return {
    assignedExams: window.evaluationData?.assignedExams || [],
    currentExam: null,
    currentSubmissionId: null,
    answers: [],
    currentQuestionIndex: 0,
    currentQuestionSeqNo: null,
    unsavedChanges: false,

    showQuestionNavPanel: false,
    showFinishButton: false,
    evaluationAreaContent: '',

    async init() {
      this.$nextTick(() => {
        this.setupFormChangeDetection();
      });
    },

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

    setupFormChangeDetection() {
      document.addEventListener('change', (e) => {
        if (e.target.matches('.mark-select, .feedback-input')) {
          this.unsavedChanges = true;
        }
      });
      document.addEventListener('input', (e) => {
        if (e.target.matches('.mark-select, .feedback-input')) {
          this.unsavedChanges = true;
        }
      });
    },

    async loadExamSubmission(examId, submissionId) {
      if (this.unsavedChanges) {
        if (!confirm('You have unsaved changes. Do you want to continue without saving?')) {
          return;
        }
      }

      this.unsavedChanges = false;
      this.currentExam = examId;
      this.currentSubmissionId = submissionId;

      this.evaluationAreaContent = `
        <div class="eval-select-placeholder">
          <i data-feather="loader" style="width:24px;height:24px;"></i>
          <p class="mb-0 mt-2" style="font-size:0.85rem">Loading...</p>
        </div>
      `;
      this.$nextTick(() => { if (typeof feather !== 'undefined') feather.replace(); });

      try {
        const data = await this.apiCall({
          method: 'exampro.www.evaluate.get_submission_details',
          args: { exam_id: examId, submission_id: submissionId }
        });

        if (data.message && data.message.success) {
          this.answers = data.message.answers.sort((a, b) => a.seq_no - b.seq_no);
          this.showQuestionNavPanel = true;

          if (this.answers.length > 0) {
            this.showQuestion(this.answers[0].seq_no);
          }
          this.checkAllEvaluated();
        }
      } catch (error) {
        console.error('Failed to load exam submission:', error);
      }
    },

    generateMarkOptions(maxMarks, selectedValue = 0) {
      let options = '';
      for (let i = 0; i <= maxMarks; i += 0.5) {
        const value = i.toFixed(1);
        const selected = parseFloat(selectedValue) === i ? 'selected' : '';
        options += `<option value="${value}" ${selected}>${value}</option>`;
      }
      return options;
    },

    showQuestion(seqNo) {
      if (this.unsavedChanges) {
        if (!confirm('You have unsaved changes. Do you want to continue without saving?')) {
          return;
        }
      }

      const questionSeqNo = parseInt(seqNo, 10);
      if (isNaN(questionSeqNo)) return;

      const answerIndex = this.answers.findIndex(a => a.seq_no === questionSeqNo);
      if (answerIndex === -1) return;

      this.currentQuestionIndex = answerIndex;
      this.currentQuestionSeqNo = questionSeqNo;
      const answer = this.answers[answerIndex];
      if (!answer || !answer.question) return;

      this.unsavedChanges = false;

      const isChoicesType = answer.question_type === 'Choices';
      const isDone = answer.evaluation_status === 'Done' || answer.evaluation_status === 'Auto';

      const questionHeader = `
        <div class="eval-card-header">
          <h6>Question ${questionSeqNo}</h6>
          <span class="eval-score-display">${answer.mark || 0} <span class="score-total">/ ${answer.max_marks}</span></span>
        </div>`;

      const questionBody = `
        <div class="eval-question-text">${answer.question}</div>
        <div class="eval-answer-label">Candidate's Answer</div>
        <div class="eval-answer-block">${answer.answer || '<span style="color:#adb5bd;font-style:italic">No answer provided</span>'}</div>`;

      if (isChoicesType) {
        this.evaluationAreaContent = `
          <div class="eval-card">
            ${questionHeader}
            <div class="eval-card-body">
              ${questionBody}
              <div class="eval-info-banner info-auto">
                <i data-feather="info" style="width:15px;height:15px;"></i>
                Auto-evaluated choices question
              </div>
            </div>
          </div>`;
      } else if (isDone) {
        const markOptions = this.generateMarkOptions(answer.max_marks, answer.mark || 0);
        this.evaluationAreaContent = `
          <div class="eval-card">
            ${questionHeader}
            <div class="eval-card-body">
              ${questionBody}
              <div class="eval-info-banner info-done">
                <i data-feather="check-circle" style="width:15px;height:15px;"></i>
                This answer has been evaluated
              </div>
              <div class="eval-form-group">
                <label class="eval-form-label">Mark (max: ${answer.max_marks})</label>
                <select class="form-select form-select-sm mark-select"
                        data-question-id="${answer.exam_question}"
                        style="max-width:120px">
                  ${markOptions}
                </select>
              </div>
              <div class="eval-form-group">
                <label class="eval-form-label">Feedback (optional)</label>
                <textarea class="form-control form-control-sm feedback-input"
                          data-question-id="${answer.exam_question}"
                          rows="3">${answer.evaluator_response || ''}</textarea>
              </div>
              <button class="btn btn-primary btn-sm eval-save-btn"
                      onclick="window.evaluationAppInstance.saveMark('${answer.exam_question}')">
                <i data-feather="save" style="width:13px;height:13px;"></i>
                Update Score
              </button>
            </div>
          </div>`;
      } else {
        const markOptions = this.generateMarkOptions(answer.max_marks, answer.mark || 0);
        this.evaluationAreaContent = `
          <div class="eval-card">
            ${questionHeader}
            <div class="eval-card-body">
              ${questionBody}
              <div class="eval-form-group">
                <label class="eval-form-label">Mark (max: ${answer.max_marks})</label>
                <select class="form-select form-select-sm mark-select"
                        data-question-id="${answer.exam_question}"
                        style="max-width:120px">
                  ${markOptions}
                </select>
              </div>
              <div class="eval-form-group">
                <label class="eval-form-label">Feedback (optional)</label>
                <textarea class="form-control form-control-sm feedback-input"
                          data-question-id="${answer.exam_question}"
                          rows="3">${answer.evaluator_response || ''}</textarea>
              </div>
              <button class="btn btn-primary btn-sm eval-save-btn"
                      onclick="window.evaluationAppInstance.saveMark('${answer.exam_question}')">
                <i data-feather="save" style="width:13px;height:13px;"></i>
                Save Score
              </button>
            </div>
          </div>`;
      }

      this.$nextTick(() => { if (typeof feather !== 'undefined') feather.replace(); });
    },

    async saveMark(questionId) {
      const markElement = document.querySelector(`.mark-select[data-question-id="${questionId}"]`);
      const feedbackElement = document.querySelector(`.feedback-input[data-question-id="${questionId}"]`);

      if (!markElement) return;

      const mark = markElement.value;
      const feedback = feedbackElement ? feedbackElement.value : '';

      try {
        const data = await this.apiCall({
          method: 'exampro.www.evaluate.save_marks',
          args: {
            question_id: questionId,
            marks: mark,
            feedback: feedback,
            submission_id: this.currentSubmissionId
          }
        });

        if (data.message && data.message.success) {
          this.unsavedChanges = false;

          const currentAnswer = this.answers[this.currentQuestionIndex];
          if (currentAnswer && currentAnswer.exam_question === questionId) {
            currentAnswer.mark = mark;
            currentAnswer.evaluator_response = feedback;
            currentAnswer.evaluation_status = 'Done';
          }

          if (typeof frappe !== 'undefined' && frappe.show_alert) {
            frappe.show_alert({ message: 'Mark saved successfully', indicator: 'green' });
          }

          this.checkAllEvaluated();
          // Re-render to show the "evaluated" banner
          this.showQuestion(this.currentQuestionSeqNo);
        }
      } catch (error) {
        console.error('Failed to save mark:', error);
      }
    },

    checkAllEvaluated() {
      if (!this.answers || this.answers.length === 0) {
        this.showFinishButton = false;
        return;
      }
      this.showFinishButton = !this.answers.some(a => a.evaluation_status === 'Pending');
    },

    async finishEvaluation() {
      if (!this.currentSubmissionId) {
        if (typeof frappe !== 'undefined' && frappe.show_alert) {
          frappe.show_alert({ message: 'No active submission to finish evaluation', indicator: 'red' });
        }
        return;
      }

      if (!confirm('Are you sure you want to finish evaluation? This will mark the evaluation as complete.')) {
        return;
      }

      try {
        const data = await this.apiCall({
          method: 'exampro.www.evaluate.finish_evaluation',
          args: { submission_id: this.currentSubmissionId }
        });

        if (data.message && data.message.success) {
          if (typeof frappe !== 'undefined' && frappe.show_alert) {
            frappe.show_alert({ message: 'Evaluation marked as finished', indicator: 'green' });
          }
          this.showFinishButton = false;
          setTimeout(() => { window.location.reload(); }, 1000);
        }
      } catch (error) {
        console.error('Failed to finish evaluation:', error);
        if (typeof frappe !== 'undefined' && frappe.show_alert) {
          frappe.show_alert({ message: error.message || 'Error finishing evaluation', indicator: 'red' });
        }
      }
    }
  };
}

window.evaluationApp = evaluationApp;

document.addEventListener('alpine:init', () => {
  window.evaluationAppInstance = null;
});

document.addEventListener('alpine:initialized', () => {
  const appElement = document.querySelector('[x-data*="evaluationApp"]');
  if (appElement) {
    window.evaluationAppInstance = appElement._x_dataStack ? appElement._x_dataStack[0] : null;
  }
});
