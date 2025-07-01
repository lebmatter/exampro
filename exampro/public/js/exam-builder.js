frappe.ready(function() {
    // Global variables
    let currentStep = 1;
    let examData = {};
    let scheduleData = {};
    let questionsData = [];
    let registrationsData = [];
    let categoriesData = {};
    let selectedCategoriesData = [];
    
    // Store batches data and selected batch
    let examBatches = [];
    let selectedBatch = 'all';
    
    // Store pending changes
    let pendingChanges = {
        add: [],
        remove: []
    };
    
    // Initialize the page
    init();
    
    function init() {
        resetFormToInitialState();
        bindEvents();
        populateDropdowns();
        fetchQuestionCategories();
        loadExamBatches();
        
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
            $('.nav-pills .nav-link.active').css('background-color', 'transparent');
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
        
        // Clear total questions
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
            pendingChanges.add.push(email);
            if (pendingChanges.remove.includes(email)) {
                pendingChanges.remove = pendingChanges.remove.filter(e => e !== email);
            }
            renderUsersTable();
        });
        
        // Handle remove user
        $(document).on('click', '.remove-user', function() {
            const email = $(this).data('email');
            pendingChanges.remove.push(email);
            if (pendingChanges.add.includes(email)) {
                pendingChanges.add = pendingChanges.add.filter(e => e !== email);
            }
            renderUsersTable();
        });
        
        // Handle cancel add
        $(document).on('click', '.cancel-add', function() {
            const email = $(this).data('email');
            pendingChanges.add = pendingChanges.add.filter(e => e !== email);
            renderUsersTable();
        });
        
        // Handle cancel remove
        $(document).on('click', '.cancel-remove', function() {
            const email = $(this).data('email');
            pendingChanges.remove = pendingChanges.remove.filter(e => e !== email);
            renderUsersTable();
        });
        
        // Navigation buttons
        $('#next-step').on('click', function() {
            if (validateCurrentStep()) {
                if (currentStep === 2) {
                    // Special handling for step 2 - save exam before proceeding
                    saveExamWithConfirmation();
                } else if (currentStep === 1) {
                    // First check if this is an existing exam
                    if ($('input[name="exam-choice"]:checked').val() === 'existing') {
                        // Make sure we always navigate to step 2 for question selection
                        navigateToStep(currentStep + 1);
                    } else {
                        // For new exams, proceed as normal
                        navigateToStep(currentStep + 1);
                    }
                } else if (currentStep === 3) {
                    // Special handling for step 3 - save schedule before proceeding
                    if ($('input[name="schedule-choice"]:checked').val() === 'new') {
                        saveScheduleWithConfirmation();
                    } else {
                        navigateToStep(currentStep + 1);
                    }
                } else if (currentStep < 4) {
                    navigateToStep(currentStep + 1);
                } else {
                    window.location.href = '/manage/exams';
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
        
        // Batch filter change
        $('#batch-filter').on('change', function() {
            selectedBatch = $(this).val();
            console.log('Batch filter changed to:', selectedBatch);
            renderUsersTable();
        });
        
        // Add event handler for bulk registration
        $('#finish-registration').on('click', applyRegistrationChanges);
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
                
                // Give the system some time to load exam details before populating step 2
                setTimeout(() => {
                    if (examData.pendingQuestionConfig) {
                        populateStep2FromExam(examData.pendingQuestionConfig);
                    }
                }, 1000);
            }
        }
        

        if (step === 4) {
            $('#next-step').text('Finish');
            // Load registrations which now contains all users with status
            loadRegistrations(scheduleData.name);
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
                // Check if at least one category has questions selected
                const hasSelectedQuestions = selectedCategoriesData.some(item => item.selectedCount > 0);
                if (!hasSelectedQuestions) {
                    frappe.throw(__('Please select at least one question category and specify the number of questions'));
                    return false;
                }
                
                // Check that no selected category has more questions than available
                const invalidSelection = selectedCategoriesData.find(item => 
                    item.selectedCount > item.totalCount
                );
                if (invalidSelection) {
                    frappe.throw(__(`Cannot select more questions than available for ${invalidSelection.category}`));
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
                        // Note: We'll populate step 2 data even if not on step 2, to ensure it's ready when the user navigates there
                        populateStep2FromExam(examData.question_config);
                    }
                    
                    loadExamQuestions(examId);
                }
            }
        });
    }
    
    function populateStep2FromExam(questionConfig) {
        console.log('Populating step 2 from exam:', questionConfig);
        
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
                
                // We will render categories in the table after fetching available categories
                // Just update the summary for now
                updateSelectionSummary();
                
                // If categories data is already loaded, update total counts now
                if (Object.keys(categoriesData).length > 0) {
                    updateTotalCountsFromAvailableCategories();
                }
                // Otherwise, it will be called after fetchQuestionCategories completes
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
        
        // Re-render the table with the updated data
        renderAvailableCategories();
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
                if (response.message && !response.message.error) {
                    // The response now includes all users with their registration status
                    registrationsData = response.message;
                    console.log('Loaded registrations data:', registrationsData);
                    renderUsersTable();
                } else if (response.message && response.message.error) {
                    frappe.msgprint(__('Error loading registrations: ' + response.message.error));
                } else {
                    console.error('Invalid response format:', response);
                }
            },
            error: function(error) {
                console.error('Failed to load registrations:', error);
                frappe.msgprint(__('Failed to load registrations'));
            }
        });
    }
    
    // We don't need loadAllUsers anymore as get_registrations will handle this
    
    function loadExamBatches() {
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_exam_batches',
            callback: function(response) {
                if (response.message && !response.message.error) {
                    examBatches = response.message;
                    populateBatchFilter();
                }
            }
        });
    }

    function populateBatchFilter() {
        const batchFilter = $('#batch-filter');
        batchFilter.empty();
        batchFilter.append('<option value="all">All Batches</option>');
        
        examBatches.forEach(batch => {
            batchFilter.append(`<option value="${batch.name}">${batch.batch_name}</option>`);
        });
    }

    function renderUsersTable() {
        const tbody = $('#users-table tbody');
        tbody.empty();

        // Get pending changes
        const pendingChanges = getPendingChanges();
        
        console.log('Rendering users table with data:', registrationsData);
        console.log('Selected batch:', selectedBatch);
        console.log('Pending changes:', pendingChanges);

        // Filter users based on selected batch
        const filteredUsers = selectedBatch === 'all' 
            ? registrationsData 
            : registrationsData.filter(user => {
                // Handle case where batches might not exist or be empty
                if (!user.batches || !Array.isArray(user.batches)) {
                    console.log('User has no batches:', user.email);
                    return false;
                }
                return user.batches.some(batch => {
                    // Handle different possible batch structure
                    const batchId = batch.id || batch.name || batch;
                    return batchId === selectedBatch;
                });
            });

        console.log('Filtered users:', filteredUsers);

        filteredUsers.forEach(user => {
            const isPendingAdd = pendingChanges.add.includes(user.email);
            const isPendingRemove = pendingChanges.remove.includes(user.email);
            
            // Format batch names for display - handle missing batches
            let batchNames = '';
            if (user.batches && Array.isArray(user.batches) && user.batches.length > 0) {
                batchNames = user.batches.map(batch => {
                    // Handle different possible batch structure
                    return batch.name || batch.batch_name || batch.id || batch;
                }).join(', ');
            }

            let status, actionButton;
            
            if (user.registered && !isPendingRemove) {
                status = `<span class="badge badge-success">${user.status || 'Registered'}</span>`;
                actionButton = `
                    <button class="btn btn-sm btn-danger remove-user" 
                            data-user="${user.name}" 
                            data-email="${user.email}">
                        Remove
                    </button>`;
            } else if (isPendingAdd) {
                status = '<span class="badge badge-warning">Pending Registration</span>';
                actionButton = `
                    <button class="btn btn-sm btn-secondary cancel-add" 
                            data-user="${user.name}" 
                            data-email="${user.email}">
                        Cancel
                    </button>`;
            } else if (isPendingRemove) {
                status = '<span class="badge badge-warning">Pending Removal</span>';
                actionButton = `
                    <button class="btn btn-sm btn-secondary cancel-remove" 
                            data-user="${user.name}" 
                            data-email="${user.email}">
                        Cancel
                    </button>`;
            } else {
                status = 'Not Registered';
                actionButton = `
                    <button class="btn btn-sm btn-primary add-user" 
                            data-user="${user.name}" 
                            data-email="${user.email}">
                        Add
                    </button>`;
            }

            const row = `
                <tr>
                    <td>${(frappe.utils && frappe.utils.escape_html) ? frappe.utils.escape_html(user.full_name) : (user.full_name || '')}</td>
                    <td>${(frappe.utils && frappe.utils.escape_html) ? frappe.utils.escape_html(user.email) : (user.email || '')}</td>
                    <td>${(frappe.utils && frappe.utils.escape_html) ? frappe.utils.escape_html(batchNames) : batchNames}</td>
                    <td>${status}</td>
                    <td>${actionButton}</td>
                </tr>`;
            tbody.append(row);
        });
        
        // If no users found after filtering
        if (filteredUsers.length === 0) {
            tbody.append(`
                <tr>
                    <td colspan="5" class="text-center">No users found for the selected batch</td>
                </tr>
            `);
        }
    }

    // IMPORTANT: renderRegistrationsTable is obsolete since we've consolidated into a single table
    // All functionality should use renderUsersTable instead
    
    function fetchQuestionCategories() {
        console.log('Fetching question categories...');
        frappe.call({
            method: 'exampro.www.manage.exam_builder.get_question_categories_with_counts',
            callback: function(response) {
                console.log('Question categories API response:', response);
                
                if (response.message) {
                    categoriesData = response.message;
                    console.log('Fetched categories data:', categoriesData);
                    
                    // Check if categoriesData is empty
                    if (Object.keys(categoriesData).length === 0) {
                        console.warn('Warning: No category data received from API!');
                        
                        // Add a default empty message to the table
                        const tbody = $('#categories-table tbody');
                        tbody.empty();
                        tbody.append(`
                            <tr>
                                <td colspan="6" class="text-center text-muted py-4">
                                    <i class="bi bi-info-circle me-2"></i>
                                    No question categories found. Please add question categories first.
                                </td>
                            </tr>
                        `);
                    } else {
                        // We have data, render the table
                        renderAvailableCategories();
                        
                        // If we have selected categories from an existing exam, update their total counts
                        if (selectedCategoriesData.length > 0) {
                            console.log('Updating total counts for existing selected categories');
                            updateTotalCountsFromAvailableCategories();
                        }
                    }
                } else {
                    console.error('Error: No message in API response');
                    // Show error message in the table
                    const tbody = $('#categories-table tbody');
                    tbody.empty();
                    tbody.append(`
                        <tr>
                            <td colspan="6" class="text-center text-danger py-4">
                                <i class="bi bi-exclamation-triangle me-2"></i>
                                Error loading question categories. Please try refreshing the page.
                            </td>
                        </tr>
                    `);
                }
            },
            error: function(err) {
                console.error('Failed to fetch question categories:', err);
                // Show error message in the table
                const tbody = $('#categories-table tbody');
                tbody.empty();
                tbody.append(`
                    <tr>
                        <td colspan="6" class="text-center text-danger py-4">
                            <i class="bi bi-exclamation-triangle me-2"></i>
                            Error loading question categories. Please try refreshing the page.
                        </td>
                    </tr>
                `);
            }
        });
    }

    function renderAvailableCategories() {
        console.log('Rendering available categories...');
        console.log('Current categoriesData:', categoriesData);
        
        const tbody = $('#categories-table tbody');
        tbody.empty();
        
        // If no categories data available or empty object
        if (!categoriesData || Object.keys(categoriesData).length === 0) {
            console.warn('No categories data available to render');
            tbody.append(`
                <tr>
                    <td colspan="6" class="text-center text-muted py-4">
                        <i class="bi bi-info-circle me-2"></i>
                        No question categories found. Please add question categories first.
                    </td>
                </tr>
            `);
            return;
        }
        
        const typeFilter = $('#question-type-filter').val();
        console.log('Current type filter:', typeFilter);
        
        // First, create a map of already selected items for quick lookup
        const selectedMap = {};
        selectedCategoriesData.forEach(item => {
            const key = `${item.category}_${item.type}_${item.mark}`;
            selectedMap[key] = item;
        });
        console.log('Selected items map:', selectedMap);
        
        // Track if we've added any rows
        let rowsAdded = 0;
        
        // Then render all categories in the unified table
        Object.keys(categoriesData).forEach(categoryName => {
            const categoryItems = categoriesData[categoryName];
            
            if (!Array.isArray(categoryItems)) {
                console.warn(`Invalid category items for ${categoryName}:`, categoryItems);
                return;
            }
            
            // Filter by question type if not "Mixed"
            const filteredItems = typeFilter === 'Mixed' 
                ? categoryItems 
                : categoryItems.filter(item => item.type === typeFilter);
            
            console.log(`Category ${categoryName} filtered items:`, filteredItems);
            
            if (filteredItems.length === 0) return;
            
            // Add each category item as a row
            filteredItems.forEach(item => {
                // Check if this item is already selected
                const key = `${categoryName}_${item.type}_${item.mark}`;
                const isSelected = key in selectedMap;
                const selectedItem = selectedMap[key];
                const selectedCount = isSelected ? selectedItem.selectedCount : 0;
                
                // Create row
                const row = $(`
                    <tr data-category="${categoryName}" data-type="${item.type}" data-mark="${item.mark}">
                        <td>${categoryName}</td>
                        <td>${item.type}</td>
                        <td>${item.mark}</td>
                        <td>${item.question_count}</td>
                        <td>
                            <div class="input-group">
                                <input type="number" class="form-control question-count-input" 
                                    min="0" max="${item.question_count}" 
                                    value="${selectedCount}" 
                                    ${!isSelected ? 'disabled' : ''}
                                    data-category="${categoryName}"
                                    data-type="${item.type}"
                                    data-mark="${item.mark}"
                                    data-max="${item.question_count}">
                            </div>
                        </td>
                        <td>
                            <div class="btn-group">
                                <button class="btn btn-sm btn-info view-questions-btn" 
                                    data-category="${categoryName}"
                                    data-type="${item.type}"
                                    data-mark="${item.mark}">
                                    <i class="bi bi-eye"></i> View
                                </button>
                                <button class="btn btn-sm ${isSelected ? 'btn-danger deselect-btn' : 'btn-success select-btn'}" 
                                    data-category="${categoryName}"
                                    data-type="${item.type}"
                                    data-mark="${item.mark}"
                                    data-count="${item.question_count}">
                                    ${isSelected ? '<i class="bi bi-x"></i> Remove' : '<i class="bi bi-check"></i> Select'}
                                </button>
                            </div>
                        </td>
                    </tr>
                `);
                
                tbody.append(row);
                rowsAdded++;
            });
        });
        
        // If no rows were added after filtering, show a message
        if (rowsAdded === 0) {
            let message = '';
            if (typeFilter !== 'Mixed') {
                message = `No question categories found with type "${typeFilter}". Try selecting a different filter.`;
            } else {
                message = 'No question categories found. Please add question categories first.';
            }
            
            tbody.append(`
                <tr>
                    <td colspan="6" class="text-center text-muted py-4">
                        <i class="bi bi-info-circle me-2"></i>
                        ${message}
                    </td>
                </tr>
            `);
        }
        
        // Bind events for the table
        
        // View questions button
        $('.view-questions-btn').on('click', function(e) {
            e.preventDefault();
            const category = $(this).data('category');
            const type = $(this).data('type');
            const mark = $(this).data('mark');
            
            showQuestionsPreviewModal(category, type, mark);
        });
        
        // Select button
        $('.select-btn').on('click', function(e) {
            e.preventDefault();
            const category = $(this).data('category');
            const type = $(this).data('type');
            const mark = $(this).data('mark');
            const count = $(this).data('count');
            
            // Add to selected categories
            addSelectedCategory(category, type, mark, count, count);
            
            // Refresh the table to show updated state
            renderAvailableCategories();
        });
        
        // Deselect button
        $('.deselect-btn').on('click', function(e) {
            e.preventDefault();
            const category = $(this).data('category');
            const type = $(this).data('type');
            const mark = $(this).data('mark');
            
            // Find and remove from selected categories
            const index = selectedCategoriesData.findIndex(item => 
                item.category === category && item.type === type && item.mark === mark
            );
            
            if (index >= 0) {
                selectedCategoriesData.splice(index, 1);
                updateSelectionSummary();
                renderAvailableCategories();
            }
        });
        
        // Question count input change
        $('.question-count-input').on('change', function() {
            const category = $(this).data('category');
            const type = $(this).data('type');
            const mark = $(this).data('mark');
            const maxCount = parseInt($(this).data('max'));
            let newCount = parseInt($(this).val());
            
            // Validate input
            if (isNaN(newCount) || newCount < 0) {
                newCount = 0;
                $(this).val(0);
            } else if (newCount > maxCount) {
                newCount = maxCount;
                $(this).val(maxCount);
            }
            
            // Update selected categories data
            const index = selectedCategoriesData.findIndex(item => 
                item.category === category && item.type === type && item.mark === mark
            );
            
            if (index >= 0) {
                selectedCategoriesData[index].selectedCount = newCount;
                updateSelectionSummary();
            }
        });
        
        console.log('Finished rendering available categories. Rows added:', rowsAdded);
    }
    
    // This function has been replaced by direct table interaction and showQuestionsPreviewModal

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
            // We no longer need to throw an error since our UI now handles existing selections
            // Just enable the input field and set its value
            const inputField = $(`#categories-table tbody tr[data-category="${category}"][data-type="${type}"][data-mark="${mark}"] .question-count-input`);
            inputField.val(selectedCount).prop('disabled', false);
            return;
        }
        
        // Parse numeric values to ensure they're integers, not strings
        const parsedMark = parseInt(mark, 10);
        const parsedSelectedCount = parseInt(selectedCount, 10);
        const parsedTotalCount = parseInt(totalCount, 10);
        
        // Add to selected data
        selectedCategoriesData.push({
            category: category,
            type: type,
            mark: parsedMark,
            selectedCount: parsedSelectedCount,
            totalCount: parsedTotalCount
        });
        
        // Update summary directly instead of rendering selected categories separately
        updateSelectionSummary();
    }

    // This function has been replaced by the unified table rendering in renderAvailableCategories

    // This function has been replaced by direct editing in the table inputs

    // This function has been replaced by the deselect button functionality in renderAvailableCategories

    function updateSelectionSummary() {
        let totalQuestions = 0;
        let totalMarks = 0;
        
        selectedCategoriesData.forEach(item => {
            totalQuestions += item.selectedCount;
            totalMarks += item.selectedCount * item.mark;
        });
        
        // Update the summary card with counts and total marks
        $('#total-selected-questions').text(totalQuestions);
        $('#total-selected-marks').text(totalMarks);
        
        // Highlight summary card to indicate change
        $('.card-header').addClass('bg-success');
        setTimeout(() => {
            $('.card-header').removeClass('bg-success').addClass('bg-primary');
        }, 500);
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
                    // Find user in registrationsData and update status
                    const userIndex = registrationsData.findIndex(r => r.email === email);
                    if (userIndex !== -1) {
                        registrationsData[userIndex].registered = true;
                        registrationsData[userIndex].status = "Registered";
                    }
                    renderUsersTable();
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
    
    // We don't need renderRegistrationsTable anymore as get_registrations will directly update registrationsData
    
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
                            // Update users in registrationsData to mark as not registered
                            const userIndex = registrationsData.findIndex(r => r.name === user);
                            if (userIndex !== -1) {
                                registrationsData[userIndex].registered = false;
                                registrationsData[userIndex].status = "Not Registered";
                            }
                            // Render the combined user table
                            renderUsersTable();
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
                duration: parseInt($('#exam-duration').val(), 10) || 0,
                pass_percentage: parseFloat($('#exam-pass-percentage').val()) || 0,
                image: $('#exam-image').val(), // Note: File handling will be different
                description: $('#exam-description').val(),
                instructions: $('#exam-instructions').val(),
                examiners: examiners
            };
        }
    }
    
    function collectQuestionsData() {
        // Return category-based selection (Fixed type only)
        return {
            type: 'Fixed',
            question_type_filter: $('#question-type-filter').val(),
            categories: selectedCategoriesData
                .filter(category => category.selectedCount > 0) // Only include categories with selected questions
                .map(category => ({
                    category: category.category,
                    type: category.type,
                    mark: parseInt(category.mark, 10),
                    selectedCount: parseInt(category.selectedCount, 10),
                    totalCount: parseInt(category.totalCount, 10)
                }))
        };
    }
    
    function collectScheduleData() {
        // Get exam name - either the selected existing exam or the newly created one
        const examName = examData.name;
        if (!examName) {
            throw new Error('No exam selected or created');
        }
        
        // Get schedule data
        const scheduleType = $('input[name="schedule-choice"]:checked').val();
        let scheduleData = {
            exam: examName,
            type: scheduleType
        };
        
        if (scheduleType === 'existing') {
            const existingScheduleId = $('#existing-schedule').val();
            if (!existingScheduleId) {
                throw new Error('No existing schedule selected');
            }
            scheduleData.name = existingScheduleId;
        } else {
            const scheduleName = $('#schedule-name').val();
            if (!scheduleName) {
                throw new Error('Schedule name is required');
            }
            
            // Get start datetime and validate it
            const startDateTime = $('#schedule-start-datetime').val();
            if (!startDateTime) {
                throw new Error('Start date and time are required');
            }
            
            // For new schedules, we only need to send the name for the schedule
            // The server will generate a unique document ID
            scheduleData.schedule_name = scheduleName;
            scheduleData.start_datetime = startDateTime; // This is in YYYY-MM-DDTHH:MM format from the datetime-local input
            scheduleData.schedule_type = $('#schedule-type').val();
            scheduleData.visibility = $('#schedule-visibility').val();
            
            // Only add expire days if it's recurring
            if ($('#schedule-type').val() === 'Recurring' && $('#schedule-expire-days').val()) {
                scheduleData.expire_days = $('#schedule-expire-days').val();
            }
            
            console.log('Collected schedule data with start_datetime:', scheduleData.start_datetime);
        }
        
        return scheduleData;
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
    
    function getPendingChanges() {
        return pendingChanges;
    }

    function applyRegistrationChanges() {
        if (pendingChanges.add.length === 0 && pendingChanges.remove.length === 0) {
            frappe.show_alert({
                message: __('No changes to apply'),
                indicator: 'orange'
            });
            return;
        }

        let message = '';
        if (pendingChanges.add.length > 0) {
            message += `Add ${pendingChanges.add.length} users\n`;
        }
        if (pendingChanges.remove.length > 0) {
            message += `Remove ${pendingChanges.remove.length} users\n`;
        }

        frappe.confirm(
            __('Are you sure you want to apply the following changes?\n\n' + message),
            async () => {
                try {
                    // Handle additions
                    if (pendingChanges.add.length > 0) {
                        const result = await frappe.call({
                            method: 'exampro.www.manage.exam_builder.add_registrations',
                            args: {
                                schedule: scheduleData.name,
                                users: JSON.stringify(pendingChanges.add)
                            }
                        });

                        if (result.message && result.message.success) {
                            // Update registrationsData with new registrations
                            // Update the existing users' registration status
                            pendingChanges.add.forEach(email => {
                                const userIndex = registrationsData.findIndex(user => user.email === email);
                                if (userIndex !== -1) {
                                    registrationsData[userIndex].registered = true;
                                    registrationsData[userIndex].status = 'Registered';
                                }
                            });
                        } else {
                            throw new Error(result.message ? result.message.error : 'Failed to add registrations');
                        }
                    }

                    // Handle removals
                    if (pendingChanges.remove.length > 0) {
                        const removePromises = pendingChanges.remove.map(email => 
                            frappe.call({
                                method: 'exampro.www.manage.exam_builder.remove_registration',
                                args: {
                                    schedule: scheduleData.name,
                                    user: email
                                }
                            })
                        );

                        await Promise.all(removePromises);
                        
                        // Update registrationsData by changing status instead of removing users
                        pendingChanges.remove.forEach(email => {
                            const userIndex = registrationsData.findIndex(user => user.email === email);
                            if (userIndex !== -1) {
                                registrationsData[userIndex].registered = false;
                                registrationsData[userIndex].status = 'Not Registered';
                            }
                        });
                    }

                    // Reset pending changes
                    pendingChanges = { add: [], remove: [] };
                    
                    // Refresh the table
                    renderUsersTable();

                    frappe.show_alert({
                        message: __('Changes applied successfully'),
                        indicator: 'green'
                    });

                } catch (error) {
                    console.error('Error applying changes:', error);
                    frappe.throw(__('Error applying changes: ') + error.message);
                }
            }
        );
    }
    
    /**
     * Collect schedule data from the form
     */
    function collectScheduleData() {
        // Get exam name - either the selected existing exam or the newly created one
        const examName = examData.name;
        if (!examName) {
            throw new Error('No exam selected or created');
        }
        
        // Get schedule data
        const scheduleType = $('input[name="schedule-choice"]:checked').val();
        let scheduleData = {
            exam: examName,
            type: scheduleType
        };
        
        if (scheduleType === 'existing') {
            const existingScheduleId = $('#existing-schedule').val();
            if (!existingScheduleId) {
                throw new Error('No existing schedule selected');
            }
            scheduleData.name = existingScheduleId;
        } else {
            const scheduleName = $('#schedule-name').val();
            if (!scheduleName) {
                throw new Error('Schedule name is required');
            }
            
            // Get start datetime and validate it
            const startDateTime = $('#schedule-start-datetime').val();
            if (!startDateTime) {
                throw new Error('Start date and time are required');
            }
            
            // For new schedules, we only need to send the name for the schedule
            // The server will generate a unique document ID
            scheduleData.schedule_name = scheduleName;
            scheduleData.start_datetime = startDateTime; // This is in YYYY-MM-DDTHH:MM format from the datetime-local input
            scheduleData.schedule_type = $('#schedule-type').val();
            scheduleData.visibility = $('#schedule-visibility').val();
            
            // Only add expire days if it's recurring
            if ($('#schedule-type').val() === 'Recurring' && $('#schedule-expire-days').val()) {
                scheduleData.expire_days = $('#schedule-expire-days').val();
            }
            
            console.log('Collected schedule data with start_datetime:', scheduleData.start_datetime);
        }
        
        return scheduleData;
    }
    
    /**
     * Save schedule with confirmation dialog
     */
    function saveScheduleWithConfirmation() {
        const scheduleName = $('#schedule-name').val();
        
        frappe.confirm(
            __(`Are you sure you want to create the schedule "${scheduleName}" for the selected exam?`),
            function() {
                // User confirmed, proceed with saving
                saveScheduleData().then(() => {
                    navigateToStep(4);
                }).catch((error) => {
                    frappe.throw(error.message || 'Failed to save schedule');
                });
            },
            function() {
                // User cancelled, do nothing
            }
        );
    }
    
    /**
     * Save schedule data to the server
     */
    function saveScheduleData() {
        return new Promise((resolve, reject) => {
            try {
                // Collect schedule data
                const scheduleFormData = collectScheduleData();
                
                console.log('Schedule data to save:', scheduleFormData);
                
                // Validate essential data before sending
                if (scheduleFormData.type === 'new') {
                    if (!scheduleFormData.exam) {
                        throw new Error('Missing exam reference');
                    }
                    if (!scheduleFormData.schedule_name) {
                        throw new Error('Schedule name is required');
                    }
                    if (!scheduleFormData.start_datetime) {
                        throw new Error('Start date and time are required');
                    }
                    
                    // Extra validation for start_datetime format
                    const dtRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;
                    if (!dtRegex.test(scheduleFormData.start_datetime)) {
                        throw new Error('Invalid date/time format. Expected YYYY-MM-DDTHH:MM');
                    }
                    
                    // Add extra fields that might be required by the doctype
                    const parts = scheduleFormData.start_datetime.split('T');
                    if (parts.length === 2) {
                        scheduleFormData.schedule_date = parts[0];
                        scheduleFormData.schedule_time = parts[1] + ':00';
                    }
                    
                } else if (scheduleFormData.type === 'existing') {
                    if (!scheduleFormData.name) {
                        throw new Error('No existing schedule selected');
                    }
                }
                
                frappe.call({
                    method: 'exampro.www.manage.exam_builder.save_schedule_from_builder',
                    args: {
                        schedule_data: JSON.stringify(scheduleFormData)
                    },
                    freeze: true,
                    freeze_message: __("Creating schedule..."),
                    callback: function(response) {
                        if (response.message && response.message.success) {
                            frappe.show_alert({
                                message: __(response.message.message),
                                indicator: 'green'
                            });
                            
                            // Update global scheduleData with the saved schedule name for future operations
                            scheduleData = {
                                name: response.message.schedule_name,
                                exam: scheduleFormData.exam,
                                schedule_name: scheduleFormData.schedule_name
                            };
                            
                            console.log('Updated schedule data:', scheduleData);
                            
                            // Load registrations for the new schedule
                            if (scheduleData.name) {
                                setTimeout(() => {
                                    loadRegistrations(scheduleData.name);
                                }, 500); // Short delay to ensure database is updated
                            }
                            
                            resolve(response.message);
                        } else {
                            console.error('Server returned error:', response);
                            reject(new Error(response.message?.error || 'Failed to save schedule'));
                        }
                    },
                    error: function(error) {
                        console.error('Error saving schedule:', error);
                        reject(error);
                    }
                });
            } catch (error) {
                console.error('Error preparing schedule data:', error);
                reject(error);
            }
        });
    }
    
    function showQuestionsPreviewModal(category, type, mark) {
        const modalHtml = `
            <div class="modal fade" id="questionsPreviewModal" tabindex="-1" role="dialog">
                <div class="modal-dialog modal-lg" role="document">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Questions Preview</h5>
                            <button type="button" class="close" data-dismiss="modal">
                                <span>&times;</span>
                            </button>
                        </div>
                        <div class="modal-body">
                            <p><strong>Category:</strong> ${category}</p>
                            <p><strong>Type:</strong> ${type}</p>
                            <p><strong>Mark per question:</strong> ${mark}</p>
                            
                            <div class="border rounded" style="height: 400px; overflow-y: auto;">
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
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        $('#questionsPreviewModal').remove();
        
        // Add modal to body
        $('body').append(modalHtml);
        
        // Show modal
        $('#questionsPreviewModal').modal('show');
        
        // Load questions
        loadQuestionsPreview(category, type, mark);
    }
});