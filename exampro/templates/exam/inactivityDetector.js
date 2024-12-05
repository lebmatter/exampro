// inactivityDetector.js

/**
 * InactivityDetector class
 * This class provides functionality to detect user inactivity based on page visibility,
 * monitor configuration changes, and detect window close events.
 */
class InactivityDetector {
  /**
   * Create an InactivityDetector instance.
   * @param {Object} options - Configuration options
   * @param {number} [options.warningThreshold=5] - Inactivity time (in seconds) before triggering a warning
   * @param {Function} [options.onInactivityStart] - Callback function when inactivity is first detected
   * @param {Function} [options.onInactive] - Callback function when user becomes inactive
   * @param {Function} [options.onActive] - Callback function when user becomes active again
   * @param {Function} [options.onMonitorChange] - Callback function when monitor configuration changes
   * @param {Function} [options.onWindowClose] - Callback function when window is about to close
   */
  constructor(options = {}) {
    // Merge default options with provided options
    this.options = {
      warningThreshold: 5,
      onInactivityStart: () => {},
      onInactive: () => {},
      onActive: () => {},
      onMonitorChange: () => {},
      onWindowClose: () => {},
      ...options
    };

    // Key for storing hiddenTime in localStorage
    this.storageKey = 'inactivityDetectorHiddenTime';
    
    // Store initial screen configuration
    this.lastScreens = `${window.screen.width}x${window.screen.height}`;

    // Bind methods to ensure correct 'this' context when used as event listeners
    this.handleActivityChange = this.handleActivityChange.bind(this);
    this.checkMonitorChange = this.checkMonitorChange.bind(this);
    this.handleBeforeUnload = this.handleBeforeUnload.bind(this);
  }

  /**
   * Initialize the detector by setting up event listeners and intervals.
   */
  init() {
    // Clear any existing hiddenTime in localStorage
    localStorage.removeItem(this.storageKey);

    // Set up visibility change and focus/blur listeners
    document.addEventListener('visibilitychange', this.handleActivityChange);
    window.addEventListener('blur', this.handleActivityChange);
    window.addEventListener('focus', this.handleActivityChange);
    
    // Set up beforeunload listener to detect when the window is about to close
    window.addEventListener('beforeunload', this.handleBeforeUnload);
    
    // Start the monitor change checker, checking every second
    this.monitorInterval = setInterval(this.checkMonitorChange, 1000);

    // Check if the page was hidden when it was last unloaded
    this.checkInitialState();
  }

  /**
   * Clean up by removing event listeners and clearing intervals.
   */
  destroy() {
    // Remove all event listeners
    document.removeEventListener('visibilitychange', this.handleActivityChange);
    window.removeEventListener('blur', this.handleActivityChange);
    window.removeEventListener('focus', this.handleActivityChange);
    window.removeEventListener('beforeunload', this.handleBeforeUnload);
    
    // Clear monitor change interval
    clearInterval(this.monitorInterval);

    // Clear hiddenTime from localStorage on destroy
    localStorage.removeItem(this.storageKey);
  }

  /**
   * Check the initial state when the detector is initialized.
   * This handles cases where the page was hidden when it was last unloaded.
   */
  checkInitialState() {
    const storedHiddenTime = localStorage.getItem(this.storageKey);
    if (storedHiddenTime) {
      const hiddenDuration = (new Date() - new Date(storedHiddenTime)) / 1000;
      if (hiddenDuration >= 1) {
        if (hiddenDuration >= this.options.warningThreshold) {
          this.options.onInactive("Page was hidden", Math.floor(hiddenDuration));
        }
        this.options.onActive(Math.floor(hiddenDuration));
      }
      localStorage.removeItem(this.storageKey);
    }
  }

  /**
   * Handle focus change events.
   * This method is called when the window gains or loses focus.
   * @param {FocusEvent} event - The focus/blur event
   */
  /**
   * Handle both visibility and focus change events.
   * This unified method handles both page visibility and window focus changes.
   */
  handleActivityChange() {
    const isInactive = document.hidden || !document.hasFocus();
    
    if (isInactive) {
      // Page is hidden or window lost focus
      if (!localStorage.getItem(this.storageKey)) {
        localStorage.setItem(this.storageKey, new Date().toISOString());
        this.options.onInactivityStart();
      }
    } else {
      // Page is visible or window gained focus
      const storedHiddenTime = localStorage.getItem(this.storageKey);
      if (storedHiddenTime) {
        const hiddenDuration = (new Date() - new Date(storedHiddenTime)) / 1000;
        if (hiddenDuration >= 1) {
          if (hiddenDuration >= this.options.warningThreshold) {
            const reason = document.hidden ? "Page was hidden" : "Window was blurred";
            this.options.onInactive(reason, Math.floor(hiddenDuration));
          }
          this.options.onActive(Math.floor(hiddenDuration));
        }
        localStorage.removeItem(this.storageKey);
      }
    }
  }

  /**
   * Check for changes in monitor configuration (e.g., resolution changes).
   */
  checkMonitorChange() {
    const currentScreens = `${window.screen.width}x${window.screen.height}`;
    if (currentScreens !== this.lastScreens) {
      this.options.onMonitorChange(this.lastScreens, currentScreens);
      this.lastScreens = currentScreens;
    }
  }

  /**
   * Handle beforeunload event.
   * This method is called when the window is about to be closed.
   * @param {Event} event - The beforeunload event
   */
  handleBeforeUnload(event) {
    const storedHiddenTime = localStorage.getItem(this.storageKey);
    if (storedHiddenTime) {
      const hiddenDuration = (new Date() - new Date(storedHiddenTime)) / 1000;
      this.options.onWindowClose(Math.floor(hiddenDuration));
    } else {
      this.options.onWindowClose(0);
    }
    
    // Uncomment the following lines if you want to show a confirmation dialog
    // event.preventDefault(); // Cancel the event
    // event.returnValue = ''; // Chrome requires returnValue to be set
  }
}

// Expose InactivityDetector to the global scope if in a browser environment
if (typeof window !== 'undefined') {
  window.InactivityDetector = InactivityDetector;
}
