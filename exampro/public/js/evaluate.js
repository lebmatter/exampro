/**
 * ExamPro Evaluation Dashboard - Alpine.js App
 * Modern reactive evaluation interface with Alpine.js and enhanced API calls
 */

// Alpine.js Evaluation App
function evaluationApp() {
  return {
    // Data properties
    assignedExams: window.evaluationData?.assignedExams || [],
    currentExam: null,
    currentSubmissionId: null,
    answers: [],
    currentQuestionIndex: 0,
    currentQuestionSeqNo: null,
    unsavedChanges: false,
    
    // UI state
    showQuestionNavPanel: false,
    showFinishButton: false,
    evaluationAreaContent: '',
    
    // Initialize the app
    async init() {
      console.log('Initializing Evaluation Dashboard');
      console.log('Initial assigned exams:', this.assignedExams);
      
      // Set up change detection for form inputs
      this.$nextTick(() => {
        this.setupFormChangeDetection();
      });
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
    
    // Setup form change detection for unsaved changes
    setupFormChangeDetection() {
      // Track changes in mark inputs and feedback to detect unsaved changes
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
    
    // Load exam submission
    async loadExamSubmission(examId, submissionId) {
      // Check for unsaved changes before loading a new exam
      if (this.unsavedChanges) {
        if (!confirm('You have unsaved changes. Do you want to continue without saving?')) {
          return;
        }
      }
      
      this.unsavedChanges = false;
      this.currentExam = examId;
      this.currentSubmissionId = submissionId;
      
      // Show loading state
      this.evaluationAreaContent = '<div class="text-center p-5"><i class="bi bi-arrow-repeat"></i><br></div>';
      
      try {
        const data = await this.apiCall({
          method: 'exampro.www.evaluate.get_submission_details',
          args: {
            exam_id: examId,
            submission_id: submissionId
          }
        });
        
        if (data.message && data.message.success) {
          // Sort answers by sequence number
          this.answers = data.message.answers.sort((a, b) => a.seq_no - b.seq_no);
          
          // Show question navigation
          this.showQuestionNavPanel = true;
          
          // Show first question if answers exist
          if (this.answers.length > 0) {
            this.showQuestion(this.answers[0].seq_no);
          }
          
          // Check if all questions are evaluated to show/hide finish button
          this.checkAllEvaluated();
        }
      } catch (error) {
        console.error('Failed to load exam submission:', error);
      }
    },
    
    // Generate dropdown options for marks from 0 to max_marks with 0.5 increments
    generateMarkOptions(maxMarks, selectedValue = 0) {
      let options = '';
      for (let i = 0; i <= maxMarks; i += 0.5) {
        const value = i.toFixed(1);
        const selected = parseFloat(selectedValue) === i ? 'selected' : '';
        options += `<option value="${value}" ${selected}>${value}</option>`;
      }
      return options;
    },
    
    // Show specific question
    showQuestion(seqNo) {
      // Check for unsaved changes before navigating
      if (this.unsavedChanges) {
        if (!confirm('You have unsaved changes. Do you want to continue without saving?')) {
          return;
        }
      }
      
      // Validate seqNo is a number
      const questionSeqNo = parseInt(seqNo, 10);
      if (isNaN(questionSeqNo)) {
        console.error('Invalid question sequence number:', seqNo);
        return;
      }
      
      // Find the answer with the matching sequence number
      const answerIndex = this.answers.findIndex(answer => answer.seq_no === questionSeqNo);
      if (questionSeqNo <= 0 || answerIndex === -1) {
        console.error('Question with sequence number not found:', questionSeqNo);
        return;
      }
      
      this.currentQuestionIndex = answerIndex;
      this.currentQuestionSeqNo = questionSeqNo;
      const answer = this.answers[answerIndex];
      
      if (!answer || !answer.question) {
        console.error('Invalid answer data for index:', answerIndex);
        return;
      }
      
      // Reset unsaved changes flag when loading a new question
      this.unsavedChanges = false;
      
      // Check if question is of type Choices (read-only) or if evaluation is not allowed
      const isChoicesType = answer.question_type === 'Choices';
      const isDone = answer.evaluation_status === 'Done' || answer.evaluation_status === 'Auto';
      
      // Display appropriate view based on question type and status
      if (isChoicesType) {
        // Show simplified view for auto-evaluated questions
        this.evaluationAreaContent = `
          <div class="card">
            <div class="card-body">
              <h5>Question ${questionSeqNo}</h5>
              <div class="question-text mb-4">${answer.question}</div>
              
              <div class="answer-section mb-4">
                <h6>Candidate's Answer:</h6>
                <div class="p-3 bg-light rounded">${answer.answer || 'No answer provided'}</div>
              </div>
              
              <div class="alert alert-secondary mt-3">
                <i class="bi bi-info-circle me-2"></i>
                This is a Choices type question that has been automatically evaluated.
              </div>
              
              <div class="evaluation-result mt-3">
                <strong>Score:</strong> ${answer.mark || 0} / ${answer.max_marks}
              </div>
            </div>
          </div>
        `;
      } else if (isDone) {
        // Show evaluation interface for already evaluated questions with existing data
        const markOptions = this.generateMarkOptions(answer.max_marks, answer.mark || 0);
        this.evaluationAreaContent = `
          <div class="card">
            <div class="card-body">
              <h5>Question ${questionSeqNo}</h5>
              <div class="question-text mb-4">${answer.question}</div>
              
              <div class="answer-section mb-4">
                <h6>Candidate's Answer:</h6>
                <div class="p-3 bg-light rounded">${answer.answer || 'No answer provided'}</div>
              </div>
              
              <div class="evaluation-section">
                <h6>Evaluation</h6>
                <div class="alert alert-success">
                  <i class="bi bi-check-circle me-2"></i>
                  This answer has been evaluated.
                </div>
                <div class="form-group mb-3">
                  <label>Mark (max: ${answer.max_marks})</label>
                  <select class="form-control mark-select" 
                          data-question-id="${answer.exam_question}">
                    ${markOptions}
                  </select>
                </div>
                <div class="form-group">
                  <label>Feedback (optional)</label>
                  <textarea class="form-control feedback-input" 
                            data-question-id="${answer.exam_question}"
                            rows="3">${answer.evaluator_response || ''}</textarea>
                </div>
                <div class="mt-3">
                  <button class="btn btn-primary save-score-btn" 
                          data-question-id="${answer.exam_question}"
                          onclick="window.evaluationAppInstance.saveMark('${answer.exam_question}')">
                    Update Score
                  </button>
                </div>
              </div>
            </div>
          </div>
        `;
      } else {
        // Show full evaluation interface for User Input pending questions
        const markOptions = this.generateMarkOptions(answer.max_marks, answer.mark || 0);
        this.evaluationAreaContent = `
          <div class="card">
            <div class="card-body">
              <h5>Question ${questionSeqNo}</h5>
              <div class="question-text mb-4">${answer.question}</div>
              
              <div class="answer-section mb-4">
                <h6>Candidate's Answer:</h6>
                <div class="p-3 bg-light rounded">${answer.answer || 'No answer provided'}</div>
              </div>
              
              <div class="evaluation-section">
                <h6>Evaluation</h6>
                <div class="form-group mb-3">
                  <label>Mark (max: ${answer.max_marks})</label>
                  <select class="form-control mark-select" 
                          data-question-id="${answer.exam_question}">
                    ${markOptions}
                  </select>
                </div>
                <div class="form-group">
                  <label>Feedback (Optional)</label>
                  <textarea class="form-control feedback-input" 
                            data-question-id="${answer.exam_question}"
                            rows="3">${answer.evaluator_response || ''}</textarea>
                </div>
                <div class="mt-3">
                  <button class="btn btn-primary save-score-btn" 
                          data-question-id="${answer.exam_question}"
                          onclick="window.evaluationAppInstance.saveMark('${answer.exam_question}')">
                    Save Score
                  </button>
                </div>
              </div>
            </div>
          </div>
        `;
      }
    },
    
    // Save mark for a question
    async saveMark(questionId) {
      const markElement = document.querySelector(`.mark-select[data-question-id="${questionId}"]`);
      const feedbackElement = document.querySelector(`.feedback-input[data-question-id="${questionId}"]`);
      
      if (!markElement) {
        console.error('Mark element not found for question:', questionId);
        return;
      }
      
      const mark = markElement.value;
      const feedback = feedbackElement ? feedbackElement.value : '';
      
      try {
        const data = await this.apiCall({
          method: 'exampro.www.evaluate.save_marks',
          args: {
            question_id: questionId,
            marks: mark,  // Backend expects 'marks'
            feedback: feedback,
            submission_id: this.currentSubmissionId
          }
        });
        
        if (data.message && data.message.success) {
          // Reset unsaved changes flag after successful save
          this.unsavedChanges = false;
          
          // Update the answer in our local cache
          const currentAnswer = this.answers[this.currentQuestionIndex];
          if (currentAnswer && currentAnswer.exam_question === questionId) {
            currentAnswer.mark = mark;
            currentAnswer.evaluator_response = feedback;
            currentAnswer.evaluation_status = 'Done';
          }
          
          if (typeof frappe !== 'undefined' && frappe.show_alert) {
            frappe.show_alert({
              message: 'Mark saved successfully',
              indicator: 'green'
            });
          }
          
          // Check if all questions are now evaluated
          this.checkAllEvaluated();
        }
      } catch (error) {
        console.error('Failed to save mark:', error);
      }
    },
    
    // Check if all questions have been evaluated and show/hide Finish Evaluation button
    checkAllEvaluated() {
      if (!this.answers || this.answers.length === 0) {
        this.showFinishButton = false;
        return;
      }
      
      // Check if any question is still pending evaluation
      const pendingEvaluation = this.answers.some(answer => answer.evaluation_status === 'Pending');
      
      this.showFinishButton = !pendingEvaluation;
    },
    
    // Finish the evaluation process
    async finishEvaluation() {
      if (!this.currentSubmissionId) {
        if (typeof frappe !== 'undefined' && frappe.show_alert) {
          frappe.show_alert({
            message: 'No active submission to finish evaluation',
            indicator: 'red'
          });
        }
        return;
      }
      
      if (!confirm('Are you sure you want to finish evaluation? This will mark the evaluation as complete.')) {
        return;
      }
      
      try {
        const data = await this.apiCall({
          method: 'exampro.www.evaluate.finish_evaluation',
          args: {
            submission_id: this.currentSubmissionId
          }
        });
        
        if (data.message && data.message.success) {
          if (typeof frappe !== 'undefined' && frappe.show_alert) {
            frappe.show_alert({
              message: 'Evaluation marked as finished successfully',
              indicator: 'green'
            });
          }
          
          // Hide the finish button
          this.showFinishButton = false;
          
          // Reload to refresh the exam list
          setTimeout(() => {
            window.location.reload();
          }, 1000);
        }
      } catch (error) {
        console.error('Failed to finish evaluation:', error);
        if (typeof frappe !== 'undefined' && frappe.show_alert) {
          frappe.show_alert({
            message: error.message || 'Error finishing evaluation',
            indicator: 'red'
          });
        }
      }
    }
  };
}

// Make the evaluationApp function globally available
window.evaluationApp = evaluationApp;

// Store the app instance globally for access from onclick handlers
document.addEventListener('alpine:init', () => {
  window.evaluationAppInstance = null;
});

document.addEventListener('alpine:initialized', () => {
  // Find the Alpine component instance
  const appElement = document.querySelector('[x-data*="evaluationApp"]');
  if (appElement) {
    // In Alpine.js v3, use _x_dataStack to access component data
    window.evaluationAppInstance = appElement._x_dataStack ? appElement._x_dataStack[0] : null;
  }
});