// Reusable Chatbox JavaScript Functions
// This file contains common chat functionality that can be used across different pages

/**
 * Initialize chatbox event handlers
 * @param {Object} config - Configuration object
 * @param {string} config.sendButtonId - ID of the send button (default: 'send-message')
 * @param {string} config.inputId - ID of the input field (default: 'chat-input')
 * @param {Function} config.sendFunction - Function to call when sending a message
 */
function initializeChatbox(config = {}) {
    const sendButtonId = config.sendButtonId || 'send-message';
    const inputId = config.inputId || 'chat-input';
    const sendFunction = config.sendFunction || defaultSendMessage;
    
    // Remove any existing event handlers to prevent duplicates
    $(`#${sendButtonId}`).off('click.chatbox click');
    $(`#${inputId}`).off('keypress.chatbox keypress');
    
    // Send button click handler
    $(`#${sendButtonId}`).on('click.chatbox', function(e) {
        e.preventDefault();
        sendFunction();
    });
    
    // Enter key handler
    $(`#${inputId}`).on('keypress.chatbox', function(e) {
        if (e.which === 13) {
            e.preventDefault();
            sendFunction();
            return false;
        }
    });
    
    // Auto-scroll on input focus
    $(`#${inputId}`).off('click.chatbox-scroll').on('click.chatbox-scroll', function() {
        const chatContainer = $('#chat-messages')[0];
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    });
}

/**
 * Default send message function - can be overridden
 */
function defaultSendMessage() {
    console.warn('Default send message function called. Please provide a custom sendFunction in config.');
}

/**
 * Clear chat input field
 * @param {string} inputId - ID of the input field (default: 'chat-input')
 */
function clearChatInput(inputId = 'chat-input') {
    $(`#${inputId}`).val('');
}

/**
 * Get chat input value
 * @param {string} inputId - ID of the input field (default: 'chat-input')
 * @returns {string} - Trimmed input value
 */
function getChatInputValue(inputId = 'chat-input') {
    return $(`#${inputId}`).val().trim();
}

/**
 * Add chat bubble to chat messages container
 * Uses the existing addChatBubble function from examutils.js
 * @param {string} timestamp - Message timestamp
 * @param {string} message - Message content
 * @param {string} messageType - Type of message (General, Warning, Critical)
 * @param {string} messageFrom - Who sent the message (Candidate, Proctor)
 */
function addChatMessage(timestamp, message, messageType, messageFrom) {
    // Use the existing addChatBubble function if available
    if (typeof addChatBubble === 'function') {
        addChatBubble(timestamp, message, messageType, messageFrom);
    } else {
        console.error('addChatBubble function not found. Make sure examutils.js is loaded.');
    }
}

/**
 * Scroll chat messages to bottom
 * @param {string} containerId - ID of the chat messages container (default: 'chat-messages')
 */
function scrollChatToBottom(containerId = 'chat-messages') {
    const container = document.getElementById(containerId);
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

/**
 * Update message count badge
 * @param {number} count - Message count
 * @param {string} badgeId - ID of the badge element (default: 'msgCount')
 */
function updateMessageCount(count, badgeId = 'msgCount') {
    $(`#${badgeId}`).text(count);
}