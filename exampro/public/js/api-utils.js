/**
 * API Utilities for ExamPro
 * Provides reusable functions for API calls with proper authentication
 */

/**
 * Get CSRF token for authenticated requests
 * @returns {string} CSRF token
 */
function getCSRFToken() {
    return frappe.csrf_token || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

/**
 * Get auth headers for API requests
 * @returns {Object} Headers object with authentication info
 */
function getAuthHeaders() {
    const headers = {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': getCSRFToken()
    };

    // Add session-based auth if available
    if (frappe.session && frappe.session.user) {
        headers['X-Frappe-User'] = frappe.session.user;
    }

    // Add API key/secret if available (for programmatic access)
    if (frappe.boot && frappe.boot.api_key) {
        headers['Authorization'] = `token ${frappe.boot.api_key}:${frappe.boot.api_secret}`;
    }

    return headers;
}

/**
 * Reusable function for making authenticated Frappe API calls
 * @param {Object} options - API call options
 * @param {string} options.method - Python method to call
 * @param {Object} options.args - Arguments to pass to the method
 * @param {string} options.type - HTTP method (GET, POST, etc.)
 * @param {Function} options.callback - Success callback function
 * @param {Function} options.error - Error callback function
 * @param {boolean} options.async - Whether to make async call (default: true)
 * @returns {Promise} Promise that resolves with the response
 */
async function apiCall(options = {}) {
    const {
        method,
        args = {},
        type = 'POST',
        callback,
        error,
        async = true
    } = options;

    if (!method) {
        throw new Error('Method is required for API calls');
    }

    // Prepare the request data
    const requestData = {
        cmd: method,
        ...args
    };

    const requestOptions = {
        method: type,
        headers: getAuthHeaders(),
        credentials: 'same-origin' // Include cookies for session-based auth
    };

    // Add body for POST requests
    if (type.toUpperCase() !== 'GET') {
        requestOptions.body = JSON.stringify(requestData);
    }

    // Build URL for GET requests
    let url = '/api/method/' + method;
    if (type.toUpperCase() === 'GET' && Object.keys(args).length > 0) {
        const params = new URLSearchParams(args);
        url += '?' + params.toString();
    }

    try {
        const response = await fetch(url, requestOptions);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Handle Frappe-style responses
        if (data.exc) {
            throw new Error(data.exc);
        }

        // Call success callback if provided
        if (callback && typeof callback === 'function') {
            callback(data);
        }

        return data;

    } catch (err) {
        console.error('API call failed:', err);
        
        // Call error callback if provided
        if (error && typeof error === 'function') {
            error(err);
        } else {
            // Default error handling
            frappe.show_alert({
                message: 'API call failed: ' + err.message,
                indicator: 'red'
            });
        }

        throw err;
    }
}

/**
 * Wrapper function that mimics frappe.call() but with enhanced auth
 * @param {Object} options - Same options as frappe.call()
 * @returns {Promise} Promise that resolves with the response
 */
function authApiCall(options = {}) {
    // Convert frappe.call format to our apiCall format
    const apiOptions = {
        method: options.method,
        args: options.args || {},
        type: options.type || 'POST',
        callback: options.callback,
        error: options.error,
        async: options.async !== false
    };

    return apiCall(apiOptions);
}

// Export functions for use in other files
window.apiCall = apiCall;
window.authApiCall = authApiCall;
window.getAuthHeaders = getAuthHeaders;
window.getCSRFToken = getCSRFToken;