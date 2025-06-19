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

            // Handle Save Score button
            $(document).on('click', '.save-score-btn:not(.disabled)', (e) => {
                e.preventDefault();
                const questionId = $(e.target).data('question-id');
                const mark = $(`.mark-input[data-question-id="${questionId}"]`).val();
                const feedback = $(`.feedback-input[data-question-id="${questionId}"]`).val();
                this.saveMark(questionId, mark, feedback);
            });
        }

        loadExamSubmission(examId, submissionId) {
            this.currentExam = examId;
            this.currentSubmissionId = submissionId;
            
            // Show loading state
            $('#evaluation-area').html('<div class="text-center p-5"><i class="fa fa-spinner fa-spin fa-2x"></i><br>Select a question...</div>');
            
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
            <button class="question-nav-btn btn-sm ${btnClass}" data-index="${answer.seq_no}">
            ${answer.seq_no}
            </button>
            `);
            });
        }

        showQuestion(index) {
            // Validate index is a number
            const questionSeqNo = parseInt(index, 10);
            if (isNaN(questionSeqNo)) {
                console.error('Invalid question index:', index);
                return;
            }

            // Find the answer with the matching sequence number
            const answerIndex = this.answers.findIndex(answer => answer.seq_no === questionSeqNo);
            if (index <= 0) {
                return;
            }
            if (answerIndex === -1) {
                console.error('Question with sequence number not found:', questionSeqNo);
                return;
            }

            this.currentQuestionIndex = answerIndex;
            const answer = this.answers[answerIndex];
            
            if (!answer || !answer.question) {
                console.error('Invalid answer data for index:', answerIndex);
                return;
            }

            // Update navigation buttons
            $('.question-nav-btn').removeClass('active');
            $(`.question-nav-btn[data-index="${questionSeqNo}"]`).addClass('active');

            // Check if evaluation is allowed (status is Pending)
            const isPending = answer.evaluation_status === 'Pending';
            
            // Update question display
            if (!isPending) {
                // Show simplified view for auto-evaluated questions
                $('#evaluation-area').html(`
                    <div class="card">
                        <div class="card-body">
                            <h5>Question ${questionSeqNo}</h5>
                            <div class="alert alert-info mt-3">
                                <i class="fa fa-info-circle mr-2"></i>
                                This answer has been automatically evaluated.
                            </div>
                        </div>
                    </div>
                `);
            } else {
                // Show full evaluation interface for pending questions
                const readOnlyAttr = '';
                const buttonDisabledClass = '';
                const buttonDisabledAttr = '';
                
                $('#evaluation-area').html(`
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
                                    <input type="number" 
                                           class="form-control mark-input" 
                                           data-question-id="${answer.exam_question}"
                                           value="${answer.mark || 0}"
                                           min="0" 
                                           max="${answer.max_marks}"
                                           ${readOnlyAttr}>
                                </div>
                                <div class="form-group">
                                    <label>Feedback</label>
                                    <textarea class="form-control feedback-input" 
                                              data-question-id="${answer.exam_question}"
                                              rows="3"
                                              ${readOnlyAttr}>${answer.evaluator_response || ''}</textarea>
                                </div>
                                <div class="mt-3">
                                    <button class="btn btn-primary save-score-btn ${buttonDisabledClass}" 
                                            data-question-id="${answer.exam_question}"
                                            ${buttonDisabledAttr}>
                                        Save Score
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                `);
            }
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
