frappe.ready(function() {
    // Initialize evaluation interface
    class ExamEvaluation {
        constructor() {
            this.currentExam = null;
            this.currentSubmissionId = null;
            this.answers = [];
            this.currentQuestionIndex = 0;
            this.bindEvents();
        }

        bindEvents() {
            // Handle exam selection from sidebar
            $(document).on('click', '.exam-item', (e) => {
                e.preventDefault();
                const examId = $(e.currentTarget).data('exam-id');
                const submissionId = $(e.currentTarget).data('submission-id');
                this.loadExamSubmission(examId, submissionId);
            });

            // Handle mark input changes
            $(document).on('change', '.mark-input, .feedback-input', (e) => {
                const questionId = $(e.target).data('question-id');
                const mark = $(`.mark-input[data-question-id="${questionId}"]`).val();
                const feedback = $(`.feedback-input[data-question-id="${questionId}"]`).val();
                this.saveMark(questionId, mark, feedback);
            });

            // Handle question navigation
            $(document).on('click', '.question-nav-btn', (e) => {
                const index = parseInt($(e.currentTarget).data('index'), 10);
                if (!isNaN(index)) {
                    this.showQuestion(index);
                } else {
                    console.error('Invalid question index in button data attribute');
                }
            });
        }

        loadExamSubmission(examId, submissionId) {
            this.currentExam = examId;
            this.currentSubmissionId = submissionId;
            
            // Show loading state
            $('#evaluation-area').html('<div class="text-center p-5"><i class="fa fa-spinner fa-spin fa-2x"></i><br>Loading exam...</div>');
            
            frappe.call({
                method: 'exampro.www.live.evaluate.get_submission_details',
                args: {
                    exam_id: examId,
                    submission_id: submissionId
                },
                callback: (r) => {
                    if (r.message && r.message.success) {
                        // Sort answers by sequence number
                        this.answers = r.message.answers.sort((a, b) => a.seq_no - b.seq_no);
                        
                        // Show question navigation
                        this.setupQuestionNavigation();
                        
                        // Show first question if answers exist
                        if (this.answers.length > 0) {
                            this.showQuestion(0);
                        }
                        
                        // Show question navigation panel
                        $('#question-nav-panel').show();
                    }
                }
            });
        }

        setupQuestionNavigation() {
            const navGrid = $('#question-nav-buttons');
            navGrid.empty();
            
            this.answers.forEach((answer, index) => {
            const status = answer.evaluation_status;
            const btnClass = status === 'Auto' ? 'evaluated' : 
                       status === 'Pending' ? 'pending' : '';
                       
            navGrid.append(`
                <button class="question-nav-btn ${btnClass}" data-index="${answer.seq_no}">
                ${answer.seq_no}
                </button>
            `);
            });
        }

        showQuestion(index) {
            // Validate index is a number and within bounds
            const questionIndex = parseInt(index, 10);
            if (isNaN(questionIndex)) {
                console.error('Invalid question index:', index);
                return;
            }

            if (questionIndex < 0 || questionIndex >= this.answers.length) {
                console.error('Question index out of bounds:', questionIndex);
                return;
            }

            this.currentQuestionIndex = questionIndex;
            const answer = this.answers[questionIndex];
            
            if (!answer || !answer.question) {
                console.error('Invalid answer data for index:', questionIndex);
                return;
            }

            // Update navigation buttons
            $('.question-nav-btn').removeClass('active');
            $(`.question-nav-btn[data-index="${questionIndex}"]`).addClass('active');

            // Update question display
            $('#evaluation-area').html(`
                <div class="card">
                    <div class="card-body">
                        <h5>Question ${questionIndex + 1}</h5>
                        <div class="question-text mb-4">${answer.question}</div>
                        
                        <div class="answer-section mb-4">
                            <h6>Candidate's Answer:</h6>
                            <div class="p-3 bg-light rounded">${answer.answer || 'No answer provided'}</div>
                        </div>
                        
                        <div class="evaluation-section">
                            <h6>Evaluation</h6>
                            <div class="form-group mb-3">
                                <label>Mark (max: ${answer.max_marks})</label>
                                <input type="number" 
                                       class="form-control mark-input" 
                                       data-question-id="${answer.exam_question}"
                                       value="${answer.mark || 0}"
                                       min="0" 
                                       max="${answer.max_marks}">
                            </div>
                            <div class="form-group">
                                <label>Feedback</label>
                                <textarea class="form-control feedback-input" 
                                          data-question-id="${answer.exam_question}"
                                          rows="3">${answer.evaluator_response || ''}</textarea>
                            </div>
                        </div>
                    </div>
                </div>
            `);
        }

        saveMark(questionId, mark, feedback) {
            frappe.call({
                method: 'exampro.www.live.evaluate.save_marks',
                args: {
                    question_id: questionId,
                    marks: mark,  // Backend expects 'marks'
                    feedback: feedback,
                    submission_id: this.currentSubmissionId
                },
                callback: (r) => {
                    if (r.message && r.message.success) {
                        // Update navigation button status
                        $(`.question-nav-btn[data-index="${this.currentQuestionIndex}"]`).addClass('evaluated');
                        
                        frappe.show_alert({
                            message: 'Mark saved successfully',
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    }

    // Initialize evaluation interface when document is ready
    new ExamEvaluation();
});
