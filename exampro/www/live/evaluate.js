frappe.ready(function() {
    // Initialize evaluation interface
    class ExamEvaluation {
        constructor() {
            this.currentExam = null;
            this.bindEvents();
            this.setupMarkingInterface();
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
            $(document).on('change', '.mark-input', (e) => {
                const questionId = $(e.target).data('question-id');
                const marks = $(e.target).val();
                this.saveMarks(questionId, marks);
            });
        }

        setupMarkingInterface() {
            // Add marking input fields to subjective questions
            $('.question[data-type="subjective"]').each((i, el) => {
                const questionId = $(el).data('name');
                const maxMarks = $(el).data('max-marks');
                
                // Add marking interface after answer
                $(el).append(`
                    <div class="marking-interface mt-3">
                        <div class="d-flex align-items-center">
                            <label class="me-2">Marks:</label>
                            <input type="number" 
                                   class="form-control mark-input" 
                                   data-question-id="${questionId}"
                                   min="0" 
                                   max="${maxMarks}"
                                   style="width: 100px;">
                            <span class="ms-2">/ ${maxMarks}</span>
                        </div>
                        <div class="feedback mt-2">
                            <textarea class="form-control feedback-input" 
                                      data-question-id="${questionId}"
                                      placeholder="Add feedback (optional)"></textarea>
                        </div>
                    </div>
                `);
            });

            // Make objective questions read-only
            $('.question[data-type="objective"] input').prop('disabled', true);
        }

        loadExamSubmission(examId, submissionId) {
            frappe.call({
                method: 'exampro.www.live.evaluate.get_submission_details',
                args: {
                    exam_id: examId,
                    submission_id: submissionId
                },
                callback: (r) => {
                    if (r.message) {
                        $('#evaluation-area').html(r.message.html);
                        this.setupMarkingInterface();
                        this.loadExistingMarks(submissionId);
                    }
                }
            });
        }

        saveMarks(questionId, marks) {
            frappe.call({
                method: 'exampro.www.live.evaluate.save_marks',
                args: {
                    question_id: questionId,
                    marks: marks,
                    submission_id: this.currentSubmissionId
                },
                callback: (r) => {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: 'Marks saved successfully',
                            indicator: 'green'
                        });
                    }
                }
            });
        }

        loadExistingMarks(submissionId) {
            frappe.call({
                method: 'exampro.www.live.evaluate.get_existing_marks',
                args: {
                    submission_id: submissionId
                },
                callback: (r) => {
                    if (r.message && r.message.marks) {
                        r.message.marks.forEach(mark => {
                            $(`.mark-input[data-question-id="${mark.question_id}"]`).val(mark.marks);
                            $(`.feedback-input[data-question-id="${mark.question_id}"]`).val(mark.feedback);
                        });
                    }
                }
            });
        }
    }

    // Initialize evaluation interface when document is ready
    new ExamEvaluation();
});
