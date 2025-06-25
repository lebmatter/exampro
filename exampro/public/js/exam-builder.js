
frappe.ready(function() {
    // Global variables
    let currentStep = 1;
    let examData = {};
    let scheduleData = {};
    let questionsData = [];
    let registrationsData = [];
    let categoriesData = {};
    let selectedCategoriesData = [];
    
    // Store all users data
    let allUsersData = [];
    
    // Initialize the page
    init();
    
    function init() {
        resetFormToInitialState();
        bindEvents();
        populateDropdowns();
        fetchQuestionCategories();
        
        // Reset all step styles and ensure we're at step 1
        $('.step-navigation .nav-link').removeClass('active completed');
        $('#step1-tab').addClass('active');
        
        // Make sure tab panes are correctly set
        $('.tab-pane').removeClass('show active');
        $('#step1').addClass('show active');
        
        // Reset current step to 1
        currentStep = 1;
        
        // Fix any Bootstrap nav-pills styling conflicts
        setTimeout(() => {
            $('.step-navigation.nav-pills .nav-link.active').css('background-color', 'transparent');
        }, 100);
    }
    
    function resetFormToInitialState() {
        // Clear global variables
        examData = {}; // This will clear pendingQuestionConfig as well
        scheduleData = {};
        questionsData = [];
        registrationsData = [];
        selectedCategoriesData = [];
        
        // Reset to step 1
        currentStep = 1;
        
        // Reset exam choice to create new exam
        $('input[name="exam-choice"][value="new"]').prop('checked', true).trigger('change');
        
        // Clear existing exam dropdown
        $('#existing-exam').val('').trigger('change');
        
        // Clear new exam form fields
        $('#exam-title').val('');
        $('#exam-duration').val('');
        $('#exam-pass-percentage').val('');
        $('#exam-description').val('');
        $('#exam-instructions').val('');
        $('#exam-image').val('');
        
        // Clear examiners table
        $('#examiners-table tbody').empty();
        
        // Reset question selection to Fixed
        $('#question-selection-type').val('Fixed').trigger('change');
        $('#total-questions').val('');
        
        // Clear selected categories
        $('#selected-categories').empty();
        
        // Update selection summary to show 0
        updateSelectionSummary();
        
        // Reset schedule choice to create new
        $('input[name="schedule-choice"][value="new"]').prop('checked', true).trigger('change');
        
        // Clear schedule form fields
        $('#schedule-name').val('');
        $('#schedule-start-datetime').val('');
        $('#schedule-expire-days').val('');
        $('#existing-schedule').val('');
        
        // Clear registration fields
        $('#registration-email').val('');
        $('#registration-search').val('');
        $('#registrations-table tbody').empty();
        
        // Show appropriate form sections
        $('#new-exam-form').show();
        $('#existing-exam-form').hide();
        $('#new-schedule-form').show();
        $('#existing-schedule-form').hide();
        $('#fixed-questions-section').show();
        $('#random-questions-count').hide();
        $('#schedule-expire-days-container').hide();
        
        console.log('Form reset to initial state');
    }
    
    function populateDropdowns() {
        // Populate question type filter
        const questionTypes = ['Mixed', 'Choices', 'User Input'];
        const questionTypeSelect = $('#question-type-filter');
        questionTypeSelect.empty();
        
        questionTypes.forEach(type => {
            questionTypeSelect.append(`<option value="${type}">${type}</option>`);
        });
        
        // Set default to Mixed
        questionTypeSelect.val('Mixed');
        
        // Populate schedule type
        const scheduleTypes = ['Fixed', 'Flexible'];
        const scheduleTypeSelect = $('#schedule-type');
        scheduleTypeSelect.empty();
        
        scheduleTypes.forEach(type => {
            scheduleTypeSelect.append(`<option value="${type}">${type}</option>`);
        });
        
        // Set default to Fixed
        scheduleTypeSelect.val('Fixed');
        
        // Populate visibility
        const visibilityOptions = ['Public', 'Private', 'Archived'];
        const visibilitySelect = $('#schedule-visibility');
        visibilitySelect.empty();
        
        visibilityOptions.forEach(option => {
            visibilitySelect.append(`<option value="${option}">${option}</option>`);
        });
        
        // Set default to Public
        visibilitySelect.val('Public');
    }
    
    function bindEvents() {
        // Exam choice toggle
        $('input[name="exam-choice"]').on('change', function() {
            const choice = $('input[name="exam-choice"]:checked').val();
            if (choice === 'existing') {
                $('#existing-exam-form').show();
                $('#new-exam-form').hide();
            } else {
                $('#existing-exam-form').hide();
                $('#new-exam-form').show();
            }
        });
        
        // Schedule choice toggle
        $('input[name="schedule-choice"]').on('change', function() {
            const choice = $('input[name="schedule-choice"]:checked').val();
            if (choice === 'existing') {
                $('#existing-schedule-form').show();
                $('#new-schedule-form').hide();
            } else {
                $('#existing-schedule-form').hide();
                $('#new-schedule-form').show();
            }
        });
        
        // Question selection type change
        $('#question-selection-type').on('change', function() {
            if ($(this).val() === 'Random') {
                $('#random-questions-count').show();
                $('#fixed-questions-section').hide();
            } else {
                $('#random-questions-count').hide();
                $('#fixed-questions-section').show();
            }
        });

        // Question type filter change
        $('#question-type-filter').on('change', function() {
            renderAvailableCategories();
        });
        
        // Schedule type change
        $('#schedule-type').on('change', function() {
            if ($(this).val() === 'Recurring') {
                $('#schedule-expire-days-container').show();
            } else {
                $('#schedule-expire-days-container').hide();
            }
        });
        
        // Existing exam change
        $('#existing-exam').on('change', function() {
            const examId = $(this).val();
            if (examId) {
                loadExamDetails(examId);
                loadExamSchedules(examId);
            }
        });
        
        // Existing schedule change
        $('#existing-schedule').on('change', function() {
            const scheduleId = $(this).val();
            if (scheduleId) {
                loadScheduleDetails(scheduleId);
                loadRegistrations(scheduleId);
            }
        });
        
        // Add examiner button
        $('#add-examiner').on('click', function() {
            addExaminerRow();
        });
        
        // Handle add user buttons - delegated event handler
        $(document).on('click', '.add-user', function() {
            const email = $(this).data('email');
            addRegistration(email);
        });
        
        // No need for search functionality as we have two clean columns now
        
        // Navigation buttons
        $('#next-step').on('click', function() {
            if (validateCurrentStep()) {
                if (currentStep === 2) {
                    // Special handling for step 2 - save exam before proceeding
                    saveExamWithConfirmation();
                } else if (currentStep < 4) {
                    navigateToStep(currentStep + 1);
                } else {
                    // refresh page
                    window.location.reload();
                }
            }
        });
        
        // Refresh button functionality
        $('#refresh-step').on('click', function(e) {
            e.preventDefault();
            // Reset the form state instead of reloading the page
            resetFormToInitialState();
            // Re-initialize the page elements
            init();
        });
        
        // Tab navigation - completely disabled, only Next button allowed
        $('.step-navigation .nav-link').on('click', function(e) {
            e.preventDefault();
            return false;
        });
    }
    
    function navigateToStep(step) {
        // Update current step
        const previousStep = currentStep;
        currentStep = step;
        
        // Mark completed steps
        if (previousStep < step && validateStep(previousStep)) {
            $(`#step${previousStep}-tab`).addClass('completed');
        }
        
        // Update UI
        $(`.step-navigation .nav-link`).removeClass('active');
        $(`#step${step}-tab`).addClass('active');
        
        $('.tab-pane').removeClass('show active');
        $(`#step${step}`).addClass('show active');
        
        // If navigating to step 2 and we have pending question config, populate it
        if (step === 2) {
            // Check if we have a selected exam and question config
            if (examData.pendingQuestionConfig) {
                populateStep2FromExam(examData.pendingQuestionConfig);
                // Keep the pending config in case we need to repopulate on refresh
                // Don't delete examData.pendingQuestionConfig so it's available if needed again
            } else if ($('input[name="exam-choice"]:checked').val() === 'existing' && $('#existing-exam').val()) {
                // If we're using an existing exam but don't have question data yet, try to load it
                loadExamDetails($('#existing-exam').val());
            }
        }
        

        if (step === 4) {
            $('#next-step').text('Finish');
        } else {
            $('#next-step').text('Next');
        }
    }
    
    function validateCurrentStep() {
        return validateStep(currentStep);
    }
    
    function validateStep(step) {
        switch (step) {
            case 1:
                // Check if existing exam selected or new exam form filled
                if ($('input[name="exam-choice"]:checked').val() === 'existing') {
                    if (!$('#existing-exam').val()) {
                        frappe.throw(__('Please select an exam'));
                        return false;
                    }
                } else {
                    // Check required fields for new exam
                    if (!$('#exam-title').val()) {
                        frappe.throw(__('Exam title is required'));
                        return false;
                    }
                    if (!$('#exam-duration').val() || $('#exam-duration').val() <= 0) {
                        frappe.throw(__('Valid duration is required'));
                        return false;
                    }
                    if (!$('#exam-pass-percentage').val()) {
                        frappe.throw(__('Pass percentage is required'));
                        return false;
                    }
                    if (!$('#exam-description').val()) {
                        frappe.throw(__('Description is required'));
                        return false;
                    }
                }
                break;
                
            case 2:
                // For fixed questions, check if at least one category selected
                if ($('#question-selection-type').val() === 'Fixed' && selectedCategoriesData.length === 0) {
                    frappe.throw(__('Please select at least one question category'));
                    return false;
                }
                // For random questions, check if count is set
                if ($('#question-selection-type').val() === 'Random' && (!$('#total-questions').val() || $('#total-questions').val() <= 0)) {
                    frappe.throw(__('Please specify the number of questions'));
                    return false;
                }
                break;
                
            case 3:
                // Check schedule data
                if ($('input[name="schedule-choice"]:checked').val() === 'existing') {
                    if (!$('#existing-schedule').val()) {
                        frappe.throw(__('Please select a schedule'));
                        return false;
                    }
                } else {
                    // Check required fields for new schedule
                    if (!$('#schedule-name').val()) {
                        frappe.throw(__('Schedule name is required'));
                        return false;
                    }
                    if (!$('#schedule-start-datetime').val()) {
                        frappe.throw(__('Start date and time is required'));
                        return false;
                    }
                }
                break;
        }
        
        return true;
    }
    
    function loadExamDetails(examId) {
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_exam_details',
            args: {
                exam: examId
            },
            callback: function(response) {
                if (response.message) {
                    examData = response.message;
                    
                    console.log('Loaded exam data:', examData);
                    
                    // Populate step 2 with existing exam's question configuration
                    if (examData.question_config) {
                        // Store the question config for later use
                        examData.pendingQuestionConfig = examData.question_config;
                        
                        // Always prepare question config data regardless of current step
                        // This ensures consistent behavior after refresh or when selecting a new exam
                        if (currentStep >= 2) {
                            populateStep2FromExam(examData.question_config);
                        }
                    }
                    
                    loadExamQuestions(examId);
                }
            }
        });
    }
    
    function populateStep2FromExam(questionConfig) {
        console.log('Populating step 2 from exam:', questionConfig);
        
        // Set question selection type based on randomize_questions
        if (questionConfig.randomize_questions) {
            $('#question-selection-type').val('Random').trigger('change');
            $('#total-questions').val(questionConfig.total_questions || '');
        } else {
            $('#question-selection-type').val('Fixed').trigger('change');
            
            // Convert select_questions to selectedCategoriesData format
            selectedCategoriesData = [];
            
            if (questionConfig.select_questions && questionConfig.select_questions.length > 0) {
                // Set question type filter first
                $('#question-type-filter').val(questionConfig.question_type || 'Mixed');
                
                questionConfig.select_questions.forEach(setting => {
                    // For existing exams, we'll use the exam's question_type
                    // If it's Mixed, we'll try to determine the most appropriate type later
                    const questionType = questionConfig.question_type || 'Mixed';
                    
                    selectedCategoriesData.push({
                        category: setting.question_category,
                        type: questionType,
                        mark: setting.mark_per_question,
                        selectedCount: setting.no_of_questions,
                        totalCount: setting.no_of_questions, // Will be updated from available categories
                        fromExistingExam: true // Flag to indicate this came from an existing exam
                    });
                });
                
                console.log('Selected categories data:', selectedCategoriesData);
                
                // Render the selected categories immediately
                renderSelectedCategories();
                updateSelectionSummary();
                
                // If categories data is already loaded, update total counts now
                if (Object.keys(categoriesData).length > 0) {
                    updateTotalCountsFromAvailableCategories();
                }
                // Otherwise, it will be called after fetchQuestionCategories completes
            }
        }
    }
    
    function updateTotalCountsFromAvailableCategories() {
        console.log('Updating total counts from available categories');
        console.log('Selected categories data:', selectedCategoriesData);
        console.log('Available categories data:', categoriesData);
        
        // This function will update the totalCount for selected categories
        // based on the actual available questions in the system
        selectedCategoriesData.forEach(selectedItem => {
            if (categoriesData[selectedItem.category]) {
                const availableItems = categoriesData[selectedItem.category];
                
                // If this is from an existing exam and type is Mixed, find the best match
                if (selectedItem.fromExistingExam && selectedItem.type === 'Mixed') {
                    // Find the item with the matching mark that has the most questions
                    const matchingItems = availableItems.filter(item => item.mark === selectedItem.mark);
                    if (matchingItems.length > 0) {
                        // Sort by question count descending and take the first one
                        matchingItems.sort((a, b) => b.question_count - a.question_count);
                        const bestMatch = matchingItems[0];
                        selectedItem.type = bestMatch.type;
                        selectedItem.totalCount = bestMatch.question_count;
                        console.log(`Updated ${selectedItem.category} from Mixed to ${bestMatch.type}`);
                    }
                } else {
                    // Normal case - exact match
                    const matchingItem = availableItems.find(item => 
                        item.type === selectedItem.type && item.mark === selectedItem.mark
                    );
                    if (matchingItem) {
                        selectedItem.totalCount = matchingItem.question_count;
                        console.log(`Updated ${selectedItem.category} total count to ${matchingItem.question_count}`);
                    } else {
                        console.log(`No matching item found for ${selectedItem.category} with type ${selectedItem.type} and mark ${selectedItem.mark}`);
                    }
                }
            } else {
                console.log(`Category ${selectedItem.category} not found in available categories`);
            }
        });
        
        console.log('Updated selected categories data:', selectedCategoriesData);
        
        // Re-render to show updated information
        renderSelectedCategories();
        updateSelectionSummary();
    }
    
    function loadExamQuestions(examId) {
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_exam_questions',
            args: {
                exam: examId
            },
            callback: function(response) {
                if (response.message) {
                    questionsData = response.message;
                    
                    // Populate selected questions
                    $('#selected-questions').empty();
                    questionsData.forEach(q => {
                        const listItem = `<li class="list-group-item d-flex justify-content-between align-items-center" data-id="${q.exam_question}">
                            ${q.question_text} 
                            <span class="badge badge-primary badge-pill">Mark: ${q.mark}</span>
                            <button class="btn btn-sm btn-danger remove-question"><i class="bi bi-x"></i></button>
                        </li>`;
                        $('#selected-questions').append(listItem);
                    });
                    
                    // Bind remove events
                    $('.remove-question').on('click', function() {
                        $(this).closest('li').remove();
                    });
                }
            }
        });
    }
    
    function loadExamSchedules(examId) {
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_exam_schedules',
            args: {
                exam: examId
            },
            callback: function(response) {
                if (response.message) {
                    // Populate schedules dropdown
                    const schedules = response.message;
                    $('#existing-schedule').empty();
                    $('#existing-schedule').append('<option value="">Select a schedule...</option>');
                    
                    schedules.forEach(s => {
                        $('#existing-schedule').append(`<option value="${s.name}">${s.schedule_name} (${s.start_date_time})</option>`);
                    });
                }
            }
        });
    }
    
    function loadScheduleDetails(scheduleId) {
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_schedule_details',
            args: {
                schedule: scheduleId
            },
            callback: function(response) {
                if (response.message) {
                    scheduleData = response.message;
                }
            }
        });
    }
    
    function loadRegistrations(scheduleId) {
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_registrations',
            args: {
                schedule: scheduleId
            },
            callback: function(response) {
                if (response.message) {
                    registrationsData = response.message;
                    renderRegistrationsTable();
                    
                    // Also load all users
                    loadAllUsers();
                }
            }
        });
    }
    
    function loadAllUsers() {
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_users',
            callback: function(response) {
                if (response.message) {
                    allUsersData = response.message;
                    renderAvailableUsersTable();
                }
            }
        });
    }
    
    function renderAvailableUsersTable() {
        $('#available-users-table tbody').empty();
        
        if (allUsersData.length === 0) {
            $('#available-users-table tbody').append(`
                <tr>
                    <td colspan="3" class="text-center">No users found</td>
                </tr>
            `);
            return;
        }
        
        // Filter out users who are already registered
        const registeredUserIds = registrationsData.map(r => r.user);
        const availableUsers = allUsersData.filter(user => !registeredUserIds.includes(user.name));
        
        if (availableUsers.length === 0) {
            $('#available-users-table tbody').append(`
                <tr>
                    <td colspan="3" class="text-center">All users are registered</td>
                </tr>
            `);
            return;
        }
        
        availableUsers.forEach(user => {
            const row = `<tr>
                <td>${user.full_name}</td>
                <td>${user.email}</td>
                <td>
                    <button class="btn btn-sm btn-success add-user" 
                            data-email="${user.email}" 
                            data-name="${user.name}">
                        <i class="bi bi-plus-circle"></i>
                    </button>
                </td>
            </tr>`;
            
            $('#available-users-table tbody').append(row);
        });
        
        // Bind add buttons
        $('.add-user').off('click').on('click', function() {
            const email = $(this).data('email');
            addRegistration(email);
        });
    }
    
    function fetchQuestionCategories() {
        console.log('Fetching question categories...');
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_question_categories_with_counts',
            callback: function(response) {
                if (response.message) {
                    categoriesData = response.message;
                    console.log('Fetched categories data:', categoriesData);
                    renderAvailableCategories();
                    
                    // If we have selected categories from an existing exam, update their total counts
                    if (selectedCategoriesData.length > 0) {
                        console.log('Updating total counts for existing selected categories');
                        updateTotalCountsFromAvailableCategories();
                    }
                }
            }
        });
    }

    function renderAvailableCategories() {
        const container = $('#available-categories');
        container.empty();
        
        const typeFilter = $('#question-type-filter').val();
        
        Object.keys(categoriesData).forEach(categoryName => {
            const categoryItems = categoriesData[categoryName];
            
            // Filter by question type if not "Mixed"
            const filteredItems = typeFilter === 'Mixed' 
                ? categoryItems 
                : categoryItems.filter(item => item.type === typeFilter);
            
            if (filteredItems.length === 0) return;
            
            // Create category section
            const categoryDiv = $(`
                <div class="category-section mb-3">
                    <h6 class="category-title text-primary">${categoryName}</h6>
                    <div class="category-items"></div>
                </div>
            `);
            
            const itemsContainer = categoryDiv.find('.category-items');
            
            filteredItems.forEach(item => {
                const itemDiv = $(`
                    <div class="category-item card mb-2" style="cursor: pointer;">
                        <div class="card-body p-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <small class="text-muted">${item.type}</small>
                                    <div><strong>${item.question_count} questions</strong> × ${item.mark} mark(s)</div>
                                </div>
                                <button class="btn btn-sm btn-outline-primary add-category-btn" 
                                        data-category="${categoryName}"
                                        data-type="${item.type}"
                                        data-mark="${item.mark}"
                                        data-count="${item.question_count}">
                                    <i class="bi bi-plus"></i> Add
                                </button>
                            </div>
                        </div>
                    </div>
                `);
                
                itemsContainer.append(itemDiv);
            });
            
            container.append(categoryDiv);
        });
        
        // Bind add category events
        $('.add-category-btn').on('click', function(e) {
            e.stopPropagation();
            const category = $(this).data('category');
            const type = $(this).data('type');
            const mark = $(this).data('mark');
            const count = $(this).data('count');
            
            showQuestionSelectionModal(category, type, mark, count);
        });
    }

    function showQuestionSelectionModal(category, type, mark, totalCount) {
        const modalHtml = `
            <div class="modal fade" id="questionSelectionModal" tabindex="-1" role="dialog">
                <div class="modal-dialog modal-lg" role="document">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Select Questions</h5>
                            <button type="button" class="close" data-dismiss="modal">
                                <span>&times;</span>
                            </button>
                        </div>
                        <div class="modal-body">
                            <p><strong>Category:</strong> ${category}</p>
                            <p><strong>Type:</strong> ${type}</p>
                            <p><strong>Mark per question:</strong> ${mark}</p>
                            <p><strong>Available questions:</strong> ${totalCount}</p>
                            
                            <!-- View Questions Section -->
                            <div class="mb-4">
                                <h6>View Questions</h6>
                                <div class="border rounded" style="height: 300px; overflow-y: auto;">
                                    <table class="table table-sm table-striped mb-0" id="questions-preview-table">
                                        <thead class="thead-light sticky-top">
                                            <tr>
                                                <th style="width: 60px;">#</th>
                                                <th>Question</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr>
                                                <td colspan="2" class="text-center">
                                                    <div class="spinner-border spinner-border-sm" role="status">
                                                        <span class="sr-only">Loading...</span>
                                                    </div>
                                                    Loading questions...
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            
                            <div class="form-group">
                                <label for="question-count-input">Number of questions to select:</label>
                                <input type="number" id="question-count-input" class="form-control" 
                                        min="1" max="${totalCount}" value="${totalCount}">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="confirm-selection">Add Selected</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        $('#questionSelectionModal').remove();
        
        // Add modal to body
        $('body').append(modalHtml);
        
        // Show modal
        $('#questionSelectionModal').modal('show');
        
        // Load questions preview
        loadQuestionsPreview(category, type, mark);
        
        // Bind confirm button
        $('#confirm-selection').on('click', function() {
            const selectedCount = parseInt($('#question-count-input').val());
            if (selectedCount > 0 && selectedCount <= totalCount) {
                addSelectedCategory(category, type, mark, selectedCount, totalCount);
                $('#questionSelectionModal').modal('hide');
            } else {
                frappe.throw(__('Please enter a valid number of questions'));
            }
        });
    }

    function loadQuestionsPreview(category, type, mark) {
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_questions_preview',
            args: {
                category: category,
                question_type: type,
                mark: mark
            },
            callback: function(response) {
                const tbody = $('#questions-preview-table tbody');
                tbody.empty();
                
                if (response.message && response.message.length > 0) {
                    response.message.forEach((question, index) => {
                        const row = `
                            <tr>
                                <td>${index + 1}</td>
                                <td class="text-truncate" style="max-width: 400px;" title="${question.question}">
                                    ${question.question}
                                </td>
                            </tr>
                        `;
                        tbody.append(row);
                    });
                } else {
                    tbody.append(`
                        <tr>
                            <td colspan="2" class="text-center text-muted">
                                No questions found
                            </td>
                        </tr>
                    `);
                }
            },
            error: function() {
                $('#questions-preview-table tbody').html(`
                    <tr>
                        <td colspan="2" class="text-center text-danger">
                            Error loading questions
                        </td>
                    </tr>
                `);
            }
        });
    }

    function addSelectedCategory(category, type, mark, selectedCount, totalCount) {
        // Check if this exact combination already exists
        const existingIndex = selectedCategoriesData.findIndex(item => 
            item.category === category && item.type === type && item.mark === mark
        );
        
        if (existingIndex >= 0) {
            frappe.throw(__('This category/type/mark combination is already selected'));
            return;
        }
        
        // Add to selected data
        selectedCategoriesData.push({
            category: category,
            type: type,
            mark: mark,
            selectedCount: selectedCount,
            totalCount: totalCount
        });
        
        renderSelectedCategories();
        updateSelectionSummary();
    }

    function renderSelectedCategories() {
        const container = $('#selected-categories');
        container.empty();
        
        if (selectedCategoriesData.length === 0) {
            container.html(`
                <div class="text-center text-muted" id="no-selection-message">
                    <p>No categories selected yet</p>
                    <small>Select categories from the left panel to add questions</small>
                </div>
            `);
            return;
        }
        
        selectedCategoriesData.forEach((item, index) => {
            const itemDiv = $(`
                <div class="selected-category-item card mb-2">
                    <div class="card-body p-2">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong>${item.category}</strong>
                                <br>
                                <small class="text-muted">${item.type} • ${item.mark} mark(s) each</small>
                                <br>
                                <span class="badge badge-primary">${item.selectedCount} of ${item.totalCount} questions</span>
                                <span class="badge badge-success">${item.selectedCount * item.mark} marks</span>
                            </div>
                            <div>
                                <button class="btn btn-sm btn-outline-secondary edit-selection-btn mr-1" 
                                        data-index="${index}">
                                    <i class="bi bi-pencil"></i>
                                </button>
                                <button class="btn btn-sm btn-danger remove-selection-btn" 
                                        data-index="${index}">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `);
            
            container.append(itemDiv);
        });
        
        // Bind edit and remove events
        $('.edit-selection-btn').on('click', function() {
            const index = $(this).data('index');
            const item = selectedCategoriesData[index];
            editSelectedCategory(index, item);
        });
        
        $('.remove-selection-btn').on('click', function() {
            const index = $(this).data('index');
            removeSelectedCategory(index);
        });
    }

    function editSelectedCategory(index, item) {
        const modalHtml = `
            <div class="modal fade" id="editSelectionModal" tabindex="-1" role="dialog">
                <div class="modal-dialog" role="document">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Edit Selection</h5>
                            <button type="button" class="close" data-dismiss="modal">
                                <span>&times;</span>
                            </button>
                        </div>
                        <div class="modal-body">
                            <p><strong>Category:</strong> ${item.category}</p>
                            <p><strong>Type:</strong> ${item.type}</p>
                            <p><strong>Mark per question:</strong> ${item.mark}</p>
                            <p><strong>Available questions:</strong> ${item.totalCount}</p>
                            
                            <div class="form-group">
                                <label for="edit-question-count">Number of questions:</label>
                                <input type="number" id="edit-question-count" class="form-control" 
                                        min="1" max="${item.totalCount}" value="${item.selectedCount}">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="confirm-edit">Update</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        $('#editSelectionModal').remove();
        
        // Add modal to body
        $('body').append(modalHtml);
        
        // Show modal
        $('#editSelectionModal').modal('show');
        
        // Bind confirm button
        $('#confirm-edit').on('click', function() {
            const newCount = parseInt($('#edit-question-count').val());
            if (newCount > 0 && newCount <= item.totalCount) {
                selectedCategoriesData[index].selectedCount = newCount;
                renderSelectedCategories();
                updateSelectionSummary();
                $('#editSelectionModal').modal('hide');
            } else {
                frappe.throw(__('Please enter a valid number of questions'));
            }
        });
    }

    function removeSelectedCategory(index) {
        selectedCategoriesData.splice(index, 1);
        renderSelectedCategories();
        updateSelectionSummary();
    }

    function updateSelectionSummary() {
        let totalQuestions = 0;
        let totalMarks = 0;
        
        selectedCategoriesData.forEach(item => {
            totalQuestions += item.selectedCount;
            totalMarks += item.selectedCount * item.mark;
        });
        
        $('#total-selected-questions').text(totalQuestions);
        $('#total-selected-marks').text(totalMarks);
    }
    
    function addExaminerRow() {
        const rowIndex = $('#examiners-table tbody tr').length;
        const newRow = `<tr>
            <td>
                <select class="form-control form-control-sm examiner-user" name="examiners[${rowIndex}][examiner]" required>
                    <option value="">Select User...</option>
                </select>
            </td>
            <td>
                <div class="custom-control custom-checkbox">
                    <input type="checkbox" class="custom-control-input" id="can-proctor-${rowIndex}" name="examiners[${rowIndex}][can_proctor]" checked>
                    <label class="custom-control-label" for="can-proctor-${rowIndex}"></label>
                </div>
            </td>
            <td>
                <div class="custom-control custom-checkbox">
                    <input type="checkbox" class="custom-control-input" id="can-evaluate-${rowIndex}" name="examiners[${rowIndex}][can_evaluate]" checked>
                    <label class="custom-control-label" for="can-evaluate-${rowIndex}"></label>
                </div>
            </td>
            <td>
                <button type="button" class="btn btn-sm btn-danger remove-examiner">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>`;
        
        $('#examiners-table tbody').append(newRow);
        
        // Load users for the dropdown
        loadUserOptions(rowIndex);
        
        // Bind remove button
        $('.remove-examiner').off('click').on('click', function() {
            $(this).closest('tr').remove();
        });
    }
    
    function loadUserOptions(rowIndex) {
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_users',
            callback: function(response) {
                if (response.message) {
                    const userSelect = $(`select[name="examiners[${rowIndex}][examiner]"]`);
                    response.message.forEach(user => {
                        userSelect.append(`<option value="${user.name}">${user.full_name} (${user.name})</option>`);
                    });
                }
            }
        });
    }
    
    function addRegistration(email) {
        frappe.call({
            method: 'exampro.www.manage.exam_builder.add_registration',
            args: {
                schedule: scheduleData.name,
                email: email
            },
            callback: function(response) {
                if (response.message && response.message.success) {
                    registrationsData.push(response.message.user);
                    renderRegistrationsTable();
                    frappe.show_alert({
                        message: __('User added successfully'),
                        indicator: 'green'
                    });
                } else {
                    frappe.throw(response.message.error || __('Failed to add user'));
                }
            }
        });
    }
    
    function renderRegistrationsTable() {
        $('#registrations-table tbody').empty();
        
        if (registrationsData.length === 0) {
            $('#registrations-table tbody').append(`
                <tr>
                    <td colspan="3" class="text-center">No registrations found</td>
                </tr>
            `);
            return;
        }
        
        registrationsData.forEach(r => {
            const row = `<tr>
                <td>${r.user_name || r.user}</td>
                <td><span class="badge badge-${r.status === 'Registered' ? 'success' : 'secondary'}">${r.status}</span></td>
                <td>
                    <button class="btn btn-sm btn-danger remove-registration" data-user="${r.user}">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>`;
            
            $('#registrations-table tbody').append(row);
        });
        
        // Bind remove buttons
        $('.remove-registration').off('click').on('click', function() {
            const user = $(this).data('user');
            removeRegistration(user);
        });
    }
    
    function removeRegistration(user) {
        frappe.confirm(
            __('Are you sure you want to remove this user from the exam?'),
            function() {
                frappe.call({
                    method: 'exampro.www.manage.exam_builder.remove_registration',
                    args: {
                        schedule: scheduleData.name,
                        user: user
                    },
                    callback: function(response) {
                        if (response.message && response.message.success) {
                            registrationsData = registrationsData.filter(r => r.user !== user);
                            renderRegistrationsTable();
                            // Also refresh the available users table
                            renderAvailableUsersTable();
                            frappe.show_alert({
                                message: __('User removed successfully'),
                                indicator: 'green'
                            });
                        } else {
                            frappe.throw(response.message.error || __('Failed to remove user'));
                        }
                    }
                });
            }
        );
    }
    
    function collectExamData() {
        if ($('input[name="exam-choice"]:checked').val() === 'existing') {
            return {
                type: 'existing',
                name: $('#existing-exam').val()
            };
        } else {
            const examiners = [];
            $('#examiners-table tbody tr').each(function() {
                const rowIndex = $(this).index();
                const examiner = {
                    examiner: $(`select[name="examiners[${rowIndex}][examiner]"]`).val(),
                    can_proctor: $(`#can-proctor-${rowIndex}`).is(':checked'),
                    can_evaluate: $(`#can-evaluate-${rowIndex}`).is(':checked')
                };
                
                if (examiner.examiner) {
                    examiners.push(examiner);
                }
            });
            
            return {
                type: 'new',
                title: $('#exam-title').val(),
                duration: $('#exam-duration').val(),
                pass_percentage: $('#exam-pass-percentage').val(),
                image: $('#exam-image').val(), // Note: File handling will be different
                description: $('#exam-description').val(),
                instructions: $('#exam-instructions').val(),
                examiners: examiners
            };
        }
    }
    
    function collectQuestionsData() {
        const questionSelectionType = $('#question-selection-type').val();
        
        if (questionSelectionType === 'Random') {
            return {
                type: 'Random',
                total_questions: $('#total-questions').val()
            };
        } else {
            // For Fixed questions, return category-based selection
            return {
                type: 'Fixed',
                question_type_filter: $('#question-type-filter').val(),
                categories: selectedCategoriesData
            };
        }
    }
    
    function collectScheduleData() {
        if ($('input[name="schedule-choice"]:checked').val() === 'existing') {
            return {
                type: 'existing',
                name: $('#existing-schedule').val()
            };
        } else {
            return {
                type: 'new',
                name: $('#schedule-name').val(),
                start_date_time: $('#schedule-start-datetime').val(),
                schedule_type: $('#schedule-type').val(),
                schedule_expire_in_days: $('#schedule-expire-days').val(),
                visibility: $('#schedule-visibility').val()
            };
        }
    }
    
    function validateEmail(email) {
        const re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        return re.test(String(email).toLowerCase());
    }
    
    function saveExamWithConfirmation() {
        const isExistingExam = $('input[name="exam-choice"]:checked').val() === 'existing';
        const examTitle = isExistingExam ? 
            $('#existing-exam option:selected').text() : 
            $('#exam-title').val();
        
        const action = isExistingExam ? 'update' : 'create';
        const message = isExistingExam ? 
            `Are you sure you want to update the exam "${examTitle}" with the current question configuration?` :
            `Are you sure you want to create the exam "${examTitle}" with the current configuration?`;
        
        frappe.confirm(
            __(message),
            function() {
                // User confirmed, proceed with saving
                saveExamData().then(() => {
                    navigateToStep(3);
                }).catch((error) => {
                    frappe.throw(error.message || 'Failed to save exam');
                });
            },
            function() {
                // User cancelled, do nothing
            }
        );
    }
    
    function saveExamData() {
        return new Promise((resolve, reject) => {
            // Collect exam and questions data
            const formExamData = collectExamData();
            const questionsData = collectQuestionsData();
            
            console.log('Form exam data:', formExamData);
            console.log('Questions data:', questionsData);
            
            const formData = {
                ...formExamData,
                questions: questionsData
            };
            
            console.log('Combined form data:', formData);
            
            frappe.call({
                method: 'exampro.www.manage.exam_builder.save_exam_from_builder',
                args: {
                    exam_data: JSON.stringify(formData)
                },
                callback: function(response) {
                    if (response.message && response.message.success) {
                        frappe.show_alert({
                            message: __(response.message.message),
                            indicator: 'green'
                        });
                        
                        // Update global examData with the saved exam name for future operations
                        if (formExamData.type === 'new') {
                            // Update global examData to reflect that this is now an existing exam
                            examData.name = response.message.exam_name;
                            
                            // Update the existing exam dropdown and select the new exam
                            updateExistingExamDropdown(response.message.exam_name);
                        }
                        
                        resolve(response.message);
                    } else {
                        reject(new Error(response.message?.error || 'Failed to save exam'));
                    }
                },
                error: function(error) {
                    console.error('Error saving exam:', error);
                    reject(error);
                }
            });
        });
    }
    
    function updateExistingExamDropdown(examName) {
        // Refresh the existing exam dropdown to include the newly created exam
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_exams',
            callback: function(response) {
                if (response.message) {
                    const existingExamSelect = $('#existing-exam');
                    existingExamSelect.empty();
                    existingExamSelect.append('<option value="">Select an exam...</option>');
                    
                    response.message.forEach(exam => {
                        const selected = exam.name === examName ? 'selected' : '';
                        existingExamSelect.append(`<option value="${exam.name}" ${selected}>${exam.title}</option>`);
                    });
                    
                    // Switch to existing exam mode
                    $('input[name="exam-choice"][value="existing"]').prop('checked', true).trigger('change');
                }
            }
        });
    }
});