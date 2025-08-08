/**
 * Gazer.js - MediaPipe-based Gaze Tracking Library
 * A standalone library for face detection and gaze tracking using MediaPipe
 * 
 *  
 * GitHub: https://github.com/lebmatter/gazerjs
 * 
 * @version 1.1.0
 * @author Gazer.js
 * @license MIT
 */

class Gazer {
  constructor(videoElementId, options = {}) {
    // Performance mode presets
    this.performancePresets = {
      low: {
        targetFps: 10,
        frameSkip: 3,
        pauseOnIdle: true,
        reducedCanvas: true,
        description: "Low CPU usage - Basic tracking"
      },
      medium: {
        targetFps: 15,
        frameSkip: 2,
        pauseOnIdle: true,
        reducedCanvas: false,
        description: "Balanced performance - Recommended"
      },
      high: {
        targetFps: 25,
        frameSkip: 1,
        pauseOnIdle: false,
        reducedCanvas: false,
        description: "High performance - Smooth tracking"
      }
    };

    // Gaze sensitivity presets
    this.sensitivityPresets = {
      strict: {
        horizontalThreshold: 0.2,
        verticalThreshold: 0.1,
        gazeHistorySize: 3,
        description: "Strict detection - Requires precise gaze alignment"
      },
      medium: {
        horizontalThreshold: 0.3,
        verticalThreshold: 0.15,
        gazeHistorySize: 5,
        description: "Balanced sensitivity - Recommended for most users"
      },
      relaxed: {
        horizontalThreshold: 0.5,
        verticalThreshold: 0.25,
        gazeHistorySize: 7,
        description: "Relaxed detection - More forgiving gaze tracking"
      }
    };

    // Default configuration
    this.config = {
      // Performance mode (low, medium, high, or null for manual)
      performanceMode: "medium",
      
      // Gaze sensitivity mode (strict, medium, relaxed, or null for manual)
      sensitivityMode: "medium",
      
      // Performance settings
      targetFps: 15,
      frameSkip: 1,
      pauseOnIdle: true,
      reducedCanvas: false,
      idleTimeout: 3000,
      
      // Gaze sensitivity
      horizontalThreshold: 0.3,
      verticalThreshold: 0.15,
      gazeHistorySize: 5,
      
      // Display options
      showGazeVector: true,
      showEyePoints: true,
      showFaceRectangle: true,
      enableLogs: true,
      
      // MediaPipe settings
      faceDetectionModel: "short",
      faceDetectionConfidence: 0.5,
      faceMeshConfidence: 0.5,
      faceMeshTracking: 0.5,
      maxNumFaces: 1,
      refineLandmarks: true,
      
      // Camera settings
      cameraWidth: 640,
      cameraHeight: 480,
      
      // Tracking data posting
      postTrackingDataInterval: 30, // seconds - set to 0 to disable
      
      // Retina location tracking
      trackRetinaLocations: true,
      retinaLocationChangeThreshold: 0.1, // 10% change to record new position
      retinaLocationInterval: 5, // seconds - record location every X seconds regardless of change
      
      // Callbacks
      onFaceDetected: null,
      onGazeChange: null,
      onAttentionChange: null,
      onStatsUpdate: null,
      onPostTrackingData: null,
      onError: null,
      onModelLoaded: null,
      
      ...options
    };

    // Apply performance mode if specified
    this.applyPerformanceMode(options);
    
    // Apply sensitivity mode if specified
    this.applySensitivityMode(options);

    // Get video element
    this.video = document.getElementById(videoElementId);
    if (!this.video) {
      throw new Error(`Video element with id "${videoElementId}" not found`);
    }

    // Create canvas for overlays
    this.canvas = this.createCanvas();
    this.ctx = this.canvas.getContext("2d");

    // Initialize state
    this.initializeState();
    
    // Initialize MediaPipe
    this.initializeMediaPipe();
  }

  createCanvas() {
    const canvas = document.createElement("canvas");
    canvas.style.position = "absolute";
    canvas.style.top = "0";
    canvas.style.left = "0";
    canvas.style.pointerEvents = "none";
    canvas.style.zIndex = "10";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    
    // Insert canvas after video element
    this.video.parentNode.insertBefore(canvas, this.video.nextSibling);
    
    return canvas;
  }

  // Apply performance mode settings
  applyPerformanceMode(userOptions = {}) {
    const mode = this.config.performanceMode;
    
    if (mode && this.performancePresets[mode]) {
      const preset = this.performancePresets[mode];
      
      // Check for manual overrides and warn if conflicts exist
      const manualSettings = ['targetFps', 'frameSkip', 'pauseOnIdle', 'reducedCanvas'];
      const hasManualOverrides = manualSettings.some(setting => 
        userOptions.hasOwnProperty(setting)
      );
      
      if (hasManualOverrides) {
        this.log(`Performance mode "${mode}" selected, but manual settings detected. Manual settings will take precedence.`, "warning");
        this.log(`Performance mode "${mode}": ${preset.description}`, "info");
      } else {
        // Apply preset settings
        this.config.targetFps = preset.targetFps;
        this.config.frameSkip = preset.frameSkip;
        this.config.pauseOnIdle = preset.pauseOnIdle;
        this.config.reducedCanvas = preset.reducedCanvas;
        
        this.log(`Applied performance mode "${mode}": ${preset.description}`, "success");
        this.log(`Settings - FPS: ${preset.targetFps}, Frame Skip: ${preset.frameSkip}, Pause on Idle: ${preset.pauseOnIdle}, Reduced Canvas: ${preset.reducedCanvas}`, "info");
      }
    }
  }

  // Apply sensitivity mode settings
  applySensitivityMode(userOptions = {}) {
    const mode = this.config.sensitivityMode;
    
    if (mode && this.sensitivityPresets[mode]) {
      const preset = this.sensitivityPresets[mode];
      
      // Check for manual overrides and warn if conflicts exist
      const manualSettings = ['horizontalThreshold', 'verticalThreshold', 'gazeHistorySize'];
      const hasManualOverrides = manualSettings.some(setting => 
        userOptions.hasOwnProperty(setting)
      );
      
      if (hasManualOverrides) {
        this.log(`Sensitivity mode "${mode}" selected, but manual gaze settings detected. Manual settings will take precedence.`, "warning");
        this.log(`Sensitivity mode "${mode}": ${preset.description}`, "info");
      } else {
        // Apply preset settings
        this.config.horizontalThreshold = preset.horizontalThreshold;
        this.config.verticalThreshold = preset.verticalThreshold;
        this.config.gazeHistorySize = preset.gazeHistorySize;
        
        this.log(`Applied sensitivity mode "${mode}": ${preset.description}`, "success");
        this.log(`Settings - Horizontal: ${preset.horizontalThreshold}, Vertical: ${preset.verticalThreshold}, Smoothing: ${preset.gazeHistorySize} frames`, "info");
      }
    }
  }

  // Update canvas size to match video display size
  updateCanvasSize() {
    if (!this.video || !this.canvas) return;
    
    // Wait for video to have dimensions
    if (this.video.videoWidth === 0 || this.video.videoHeight === 0) {
      setTimeout(() => this.updateCanvasSize(), 100);
      return;
    }
    
    // Set canvas internal dimensions to match video resolution
    this.canvas.width = this.video.videoWidth;
    this.canvas.height = this.video.videoHeight;
    
    // Reset transform to ensure proper scaling
    this.canvas.style.transform = "none";
    this.canvas.style.transformOrigin = "top left";
    
    this.log(`Canvas updated to ${this.canvas.width}x${this.canvas.height}`, "info");
  }

  initializeState() {
    // MediaPipe instances
    this.faceDetection = null;
    this.faceMesh = null;
    this.camera = null;
    
    // Running state
    this.isRunning = false;
    this.isModelLoaded = false;
    this.isIdle = false;
    
    // Event listeners
    this.resizeListener = null;
    
    // Tracking data
    this.currentFaces = [];
    this.lastFaceCount = -1;
    this.lastGazeState = null;
    this.gazeHistory = [];
    this.currentMeshResults = null;
    
    // Statistics
    this.faceCount = 0;
    this.awayStartTime = null;
    this.totalAwayTime = 0;
    this.distractedStartTime = null;
    this.totalDistractedTime = 0;
    this.faceCountChanges = 0; // Track number of face count changes
    
    // Tracking data posting
    this.trackingDataTimer = null;
    this.lastTrackingDataPost = Date.now();
    
    // Retina location tracking
    this.retinaLocations = [];
    this.lastRetinaPosition = null;
    this.lastRetinaLocationRecord = Date.now();
    
    // Performance tracking
    this.frameCounter = 0;
    this.lastFrameTime = Date.now();
    this.processingFps = 0;
    this.framesSkipped = 0;
    this.canvasUpdates = 0;
    this.lastIdleTime = Date.now();
  }

  // Logging function
  log(message, type = "info") {
    if (!this.config.enableLogs) return;
    
    const timestamp = new Date().toLocaleTimeString();
    const logMessage = `[${timestamp}] [Gazer.js] ${message}`;
    
    switch (type) {
      case "warning":
        console.warn(logMessage);
        break;
      case "success":
        console.log(`✅ ${logMessage}`);
        break;
      case "gaze":
        console.log(`👁️ ${logMessage}`);
        break;
      case "error":
        console.error(`❌ ${logMessage}`);
        break;
      case "info":
      default:
        console.log(`ℹ️ ${logMessage}`);
        break;
    }
  }

  // Initialize MediaPipe models
  async initializeMediaPipe() {
    try {
      this.log("Loading MediaPipe Face Detection and Mesh...", "info");

      // Initialize face detection
      this.faceDetection = new FaceDetection({
        locateFile: (file) => {
          return `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`;
        },
      });

      this.faceDetection.setOptions({
        model: this.config.faceDetectionModel,
        minDetectionConfidence: this.config.faceDetectionConfidence,
      });

      // Initialize face mesh
      this.faceMesh = new FaceMesh({
        locateFile: (file) => {
          return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`;
        },
      });

      this.faceMesh.setOptions({
        maxNumFaces: this.config.maxNumFaces,
        refineLandmarks: this.config.refineLandmarks,
        minDetectionConfidence: this.config.faceMeshConfidence,
        minTrackingConfidence: this.config.faceMeshTracking,
      });

      // Set up callbacks
      this.faceDetection.onResults(this.onFaceDetectionResults.bind(this));
      this.faceMesh.onResults(this.onFaceMeshResults.bind(this));

      this.isModelLoaded = true;
      this.log("MediaPipe models loaded successfully", "success");
      
      if (this.config.onModelLoaded) {
        this.config.onModelLoaded();
      }
      
    } catch (error) {
      this.log("Error loading MediaPipe: " + error.message, "error");
      if (this.config.onError) {
        this.config.onError(error);
      }
    }
  }

  // Calculate gaze direction from landmarks
  calculateGazeDirection(landmarks) {
    if (!landmarks || landmarks.length < 468) return null;

    const leftEyeOuter = landmarks[33] || null;
    const leftEyeInner = landmarks[133] || null;
    const rightEyeOuter = landmarks[362] || null;
    const rightEyeInner = landmarks[263] || null;
    const noseTip = landmarks[1] || null;
    const leftEyeTop = landmarks[159] || null;
    const leftEyeBottom = landmarks[145] || null;
    const rightEyeTop = landmarks[386] || null;
    const rightEyeBottom = landmarks[374] || null;

    if (!leftEyeOuter || !rightEyeOuter || !noseTip) return null;

    // Calculate eye centers
    const leftEyeCenter = {
      x: (leftEyeOuter.x + leftEyeInner.x) / 2,
      y: (leftEyeTop.y + leftEyeBottom.y) / 2,
    };

    const rightEyeCenter = {
      x: (rightEyeOuter.x + rightEyeInner.x) / 2,
      y: (rightEyeTop.y + rightEyeBottom.y) / 2,
    };

    // Calculate face center
    const faceCenter = {
      x: (leftEyeCenter.x + rightEyeCenter.x) / 2,
      y: (leftEyeCenter.y + rightEyeCenter.y) / 2,
    };

    // Calculate gaze offsets
    const eyeDistance = Math.abs(rightEyeCenter.x - leftEyeCenter.x);
    const horizontalGaze = (faceCenter.x - 0.5) / eyeDistance;
    const verticalGaze = faceCenter.y - 0.4;

    // Determine gaze direction
    let gazeDirection = "screen";
    if (Math.abs(horizontalGaze) > this.config.horizontalThreshold) {
      gazeDirection = "away";
    } else if (Math.abs(verticalGaze) > this.config.verticalThreshold) {
      gazeDirection = "away";
    }

    return {
      direction: gazeDirection,
      horizontal: horizontalGaze,
      vertical: verticalGaze,
      confidence: Math.max(0.5, 1 - Math.abs(horizontalGaze) - Math.abs(verticalGaze)),
      leftEyeCenter,
      rightEyeCenter,
      faceCenter,
    };
  }

  // Calculate and record retina position if tracking is enabled
  recordRetinaPosition(gazeData) {
    if (!this.config.trackRetinaLocations || !gazeData) {
      return;
    }

    const now = Date.now();
    const timeSinceLastRecord = (now - this.lastRetinaLocationRecord) / 1000;
    
    // Convert gaze data to screen coordinates (normalized 0-1)
    const retinaPosition = {
      x: Math.max(0, Math.min(1, 0.5 + gazeData.horizontal)),
      y: Math.max(0, Math.min(1, 0.5 + gazeData.vertical)),
      confidence: gazeData.confidence,
      timestamp: now
    };

    let shouldRecord = false;

    // Record if this is the first position
    if (!this.lastRetinaPosition) {
      shouldRecord = true;
    }
    // Record if enough time has passed (interval-based recording)
    else if (timeSinceLastRecord >= this.config.retinaLocationInterval) {
      shouldRecord = true;
    }
    // Record if position changed significantly (change-based recording)
    else if (this.lastRetinaPosition) {
      const deltaX = Math.abs(retinaPosition.x - this.lastRetinaPosition.x);
      const deltaY = Math.abs(retinaPosition.y - this.lastRetinaPosition.y);
      const maxDelta = Math.max(deltaX, deltaY);
      
      if (maxDelta >= this.config.retinaLocationChangeThreshold) {
        shouldRecord = true;
      }
    }

    if (shouldRecord) {
      this.retinaLocations.push({
        x: retinaPosition.x,
        y: retinaPosition.y,
        confidence: retinaPosition.confidence,
        timestamp: retinaPosition.timestamp,
        gazeDirection: gazeData.direction
      });

      this.lastRetinaPosition = retinaPosition;
      this.lastRetinaLocationRecord = now;

      this.log(`Recorded retina position: (${retinaPosition.x.toFixed(3)}, ${retinaPosition.y.toFixed(3)}) confidence: ${retinaPosition.confidence.toFixed(2)}`, "info");
    }
  }

  // Smooth gaze detection
  smoothGazeDetection(currentGaze) {
    if (!currentGaze) return "unknown";

    this.gazeHistory.push(currentGaze.direction);
    if (this.gazeHistory.length > this.config.gazeHistorySize) {
      this.gazeHistory.shift();
    }

    const gazeCounts = this.gazeHistory.reduce((acc, gaze) => {
      acc[gaze] = (acc[gaze] || 0) + 1;
      return acc;
    }, {});

    return Object.keys(gazeCounts).reduce((a, b) =>
      gazeCounts[a] > gazeCounts[b] ? a : b
    );
  }

  // Handle face detection results
  onFaceDetectionResults(results) {
    if (!this.ctx) return;

    // Update performance tracking
    this.frameCounter++;
    const now = Date.now();
    if (now - this.lastFrameTime >= 1000) {
      this.processingFps = this.frameCounter;
      this.frameCounter = 0;
      this.lastFrameTime = now;
    }

    this.currentFaces = results.detections || results.faces || [];

    // Check for idle state
    if (this.config.pauseOnIdle) {
      if (this.currentFaces.length === 0) {
        if (!this.isIdle && now - this.lastIdleTime > this.config.idleTimeout) {
          this.isIdle = true;
          this.log("Entering idle mode (no faces detected)", "info");
        }
      } else {
        if (this.isIdle) {
          this.isIdle = false;
          this.log("Exiting idle mode (faces detected)", "info");
        }
        this.lastIdleTime = now;
      }
    }

    if (this.isIdle && this.config.pauseOnIdle) {
      return;
    }

    // Update canvas
    const shouldUpdateCanvas =
      !this.config.reducedCanvas ||
      this.currentFaces.length !== this.lastFaceCount ||
      Math.abs(now - this.lastFrameTime) > 500;

    if (shouldUpdateCanvas) {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      if (this.currentFaces.length > 0 && this.config.showFaceRectangle) {
        this.drawFaces(this.currentFaces);
      }
      this.canvasUpdates++;
    }

    this.updateStats(this.currentFaces);
  }

  // Handle face mesh results
  onFaceMeshResults(results) {
    if (this.frameCounter % this.config.frameSkip !== 0) {
      this.framesSkipped++;
      return;
    }

    this.currentMeshResults = results;

    if (this.isIdle && this.config.pauseOnIdle) {
      return;
    }

    if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
      const landmarks = results.multiFaceLandmarks[0];
      const gazeData = this.calculateGazeDirection(landmarks);

      if (gazeData) {
        const smoothedGaze = this.smoothGazeDetection(gazeData);
        
        // Record retina position if tracking is enabled
        this.recordRetinaPosition(gazeData);
        
        this.updateGazeStatus(smoothedGaze, gazeData);

        if (this.config.showGazeVector || this.config.showEyePoints) {
          this.drawGazeIndicators(landmarks, gazeData);
        }
      }
    } else {
      this.updateGazeStatus("unknown", null);
    }
  }

  // Update gaze status
  updateGazeStatus(gazeState, gazeData) {
    const now = Date.now();

    if (gazeState !== this.lastGazeState) {
      if (gazeState === "screen") {
        this.log("Person looking at screen", "gaze");
      } else if (gazeState === "away") {
        this.log("Person looking away from screen", "gaze");
      } else {
        this.log("Gaze direction unknown", "info");
      }
      this.lastGazeState = gazeState;

      if (this.config.onGazeChange) {
        this.config.onGazeChange(gazeState, gazeData);
      }
    }

    // Track distracted time
    const isDistracted = gazeState === "away";

    if (isDistracted && this.distractedStartTime === null) {
      this.distractedStartTime = now;
    } else if (!isDistracted && this.distractedStartTime !== null) {
      this.totalDistractedTime += now - this.distractedStartTime;
      this.distractedStartTime = null;
    }

    let currentDistractedTime = this.totalDistractedTime;
    if (this.distractedStartTime !== null) {
      currentDistractedTime += now - this.distractedStartTime;
    }
  }

  // Draw face rectangles
  drawFaces(faces) {
    if (!this.config.showFaceRectangle) return;

    faces.forEach((detection, index) => {
      const bbox = detection.boundingBox || detection.bbox;
      if (!bbox) return;

      const x = bbox.xCenter * this.canvas.width - (bbox.width * this.canvas.width) / 2;
      const y = bbox.yCenter * this.canvas.height - (bbox.height * this.canvas.height) / 2;
      const width = bbox.width * this.canvas.width;
      const height = bbox.height * this.canvas.height;

      this.ctx.strokeStyle = "#00ff00";
      this.ctx.lineWidth = 3;
      this.ctx.strokeRect(x, y, width, height);

      let confidence = 0;
      if (detection.score && detection.score.length > 0) {
        confidence = Math.round(detection.score[0] * 100);
      } else if (detection.score) {
        confidence = Math.round(detection.score * 100);
      } else if (detection.confidence) {
        confidence = Math.round(detection.confidence * 100);
      } else {
        confidence = 85;
      }

      this.ctx.fillStyle = "#00ff00";
      this.ctx.font = "16px Arial";
      this.ctx.fillText(`Face ${index + 1}: ${confidence}%`, x, y - 10);
    });
  }

  // Draw gaze indicators
  drawGazeIndicators(landmarks, gazeData) {
    if (!landmarks || !gazeData) return;

    if (this.config.showEyePoints) {
      const leftEyeCenter = {
        x: gazeData.leftEyeCenter.x * this.canvas.width,
        y: gazeData.leftEyeCenter.y * this.canvas.height,
      };

      const rightEyeCenter = {
        x: gazeData.rightEyeCenter.x * this.canvas.width,
        y: gazeData.rightEyeCenter.y * this.canvas.height,
      };

      this.ctx.fillStyle = gazeData.direction === "screen" ? "#00ff00" : "#ff6600";
      this.ctx.beginPath();
      this.ctx.arc(leftEyeCenter.x, leftEyeCenter.y, 4, 0, 2 * Math.PI);
      this.ctx.fill();

      this.ctx.beginPath();
      this.ctx.arc(rightEyeCenter.x, rightEyeCenter.y, 4, 0, 2 * Math.PI);
      this.ctx.fill();
    }

    if (this.config.showGazeVector && gazeData.faceCenter) {
      const faceCenter = {
        x: gazeData.faceCenter.x * this.canvas.width,
        y: gazeData.faceCenter.y * this.canvas.height,
      };

      this.ctx.strokeStyle = gazeData.direction === "screen" ? "#00ff00" : "#ff6600";
      this.ctx.lineWidth = 2;
      this.ctx.beginPath();
      this.ctx.moveTo(faceCenter.x, faceCenter.y);
      this.ctx.lineTo(
        faceCenter.x + gazeData.horizontal * 50,
        faceCenter.y + gazeData.vertical * 50
      );
      this.ctx.stroke();
    }
  }

  // Update statistics
  updateStats(faces) {
    const now = Date.now();
    this.faceCount = faces.length;
    const isAway = this.faceCount === 0;

    if (this.faceCount !== this.lastFaceCount) {
      // Increment face count change counter
      this.faceCountChanges++;
      
      if (this.faceCount === 0) {
        this.log("No person detected (looking away or left)", "warning");
      } else if (this.faceCount > 1) {
        this.log(`Multiple people detected (${this.faceCount} faces)`, "info");
      } else if (this.faceCount === 1 && this.lastFaceCount !== 1) {
        this.log("Person detected and present", "success");
      }
      this.lastFaceCount = this.faceCount;

      if (this.config.onFaceDetected) {
        this.config.onFaceDetected(faces);
      }
    }

    let avgConfidence = 0;
    if (faces.length > 0) {
      let totalConfidence = 0;
      faces.forEach((face) => {
        if (face.score && face.score.length > 0) {
          totalConfidence += face.score[0];
        } else if (face.score) {
          totalConfidence += face.score;
        } else if (face.confidence) {
          totalConfidence += face.confidence;
        } else {
          totalConfidence += 0.85;
        }
      });
      avgConfidence = totalConfidence / faces.length;
    }

    if (isAway && this.awayStartTime === null) {
      this.awayStartTime = now;
    } else if (!isAway && this.awayStartTime !== null) {
      this.totalAwayTime += now - this.awayStartTime;
      this.awayStartTime = null;
    }

    let currentAwayTime = this.totalAwayTime;
    if (this.awayStartTime !== null) {
      currentAwayTime += now - this.awayStartTime;
    }

    let currentDistractedTime = this.totalDistractedTime;
    if (this.distractedStartTime !== null) {
      currentDistractedTime += now - this.distractedStartTime;
    }

    const stats = {
      faceCount: this.faceCount,
      awayTime: Math.floor(currentAwayTime / 1000),
      distractedTime: Math.floor(currentDistractedTime / 1000),
      confidence: Math.round(avgConfidence * 100),
      processingFps: this.processingFps,
      framesSkipped: this.framesSkipped,
      canvasUpdates: this.canvasUpdates,
      gazeState: this.lastGazeState,
      isIdle: this.isIdle,
      faceCountChanges: this.faceCountChanges,
      retinaLocationCount: this.config.trackRetinaLocations ? this.retinaLocations.length : 0
    };

    if (this.config.onStatsUpdate) {
      this.config.onStatsUpdate(stats);
    }
  }

  // Start tracking data timer
  startTrackingDataTimer() {
    if (this.config.postTrackingDataInterval <= 0 || !this.config.onPostTrackingData) {
      return;
    }

    this.stopTrackingDataTimer(); // Clear any existing timer
    
    const intervalMs = this.config.postTrackingDataInterval * 1000;
    this.trackingDataTimer = setInterval(() => {
      this.postTrackingData();
    }, intervalMs);
    
    this.log(`Tracking data timer started - posting every ${this.config.postTrackingDataInterval} seconds`, "info");
  }

  // Stop tracking data timer
  stopTrackingDataTimer() {
    if (this.trackingDataTimer) {
      clearInterval(this.trackingDataTimer);
      this.trackingDataTimer = null;
      this.log("Tracking data timer stopped", "info");
    }
  }

  // Post tracking data via callback
  postTrackingData() {
    if (!this.config.onPostTrackingData) {
      return;
    }

    const now = Date.now();
    
    let currentAwayTime = this.totalAwayTime;
    if (this.awayStartTime !== null) {
      currentAwayTime += now - this.awayStartTime;
    }

    let currentDistractedTime = this.totalDistractedTime;
    if (this.distractedStartTime !== null) {
      currentDistractedTime += now - this.distractedStartTime;
    }

    const trackingData = {
      timestamp: now,
      sessionDuration: Math.floor((now - this.lastTrackingDataPost) / 1000),
      faceCountChanges: this.faceCountChanges,
      totalAwayTime: Math.floor(currentAwayTime / 1000),
      totalDistractedTime: Math.floor(currentDistractedTime / 1000),
      currentFaceCount: this.faceCount,
      currentGazeState: this.lastGazeState,
      processingFps: this.processingFps,
      framesSkipped: this.framesSkipped,
      canvasUpdates: this.canvasUpdates,
      isRunning: this.isRunning,
      isIdle: this.isIdle,
      retinaLocations: this.config.trackRetinaLocations ? [...this.retinaLocations] : []
    };

    this.log(`Posting tracking data - Face changes: ${this.faceCountChanges}, Away time: ${trackingData.totalAwayTime}s, Distracted time: ${trackingData.totalDistractedTime}s, Retina locations: ${trackingData.retinaLocations.length}`, "info");
    
    // Reset counters for next interval
    this.faceCountChanges = 0;
    this.lastTrackingDataPost = now;
    
    // Reset retina locations array for next interval
    if (this.config.trackRetinaLocations) {
      this.retinaLocations = [];
    }
    
    // Call the callback with the tracking data
    this.config.onPostTrackingData(trackingData);
  }

  // Public API methods
  async start() {
    if (!this.isModelLoaded) {
      throw new Error("MediaPipe models not loaded yet");
    }

    try {
      this.log("Starting camera with gaze tracking...", "info");

      let lastProcessTime = 0;
      const frameInterval = 1000 / this.config.targetFps;

      this.camera = new Camera(this.video, {
        onFrame: async () => {
          if (!this.isRunning) return;

          const now = Date.now();
          if (now - lastProcessTime >= frameInterval) {
            await this.faceDetection.send({ image: this.video });
            await this.faceMesh.send({ image: this.video });
            lastProcessTime = now;
          }
        },
        width: this.config.cameraWidth,
        height: this.config.cameraHeight,
      });

      await this.camera.start();

      // Set canvas size to match video
      this.updateCanvasSize();
      
      // Add resize listener to keep canvas aligned
      this.resizeListener = () => this.updateCanvasSize();
      window.addEventListener('resize', this.resizeListener);
      
      // Also update canvas size when video metadata loads
      this.video.addEventListener('loadedmetadata', this.resizeListener);

      this.isRunning = true;
      
      // Start tracking data timer if configured
      this.startTrackingDataTimer();
      
      this.log("Camera started successfully", "success");

    } catch (error) {
      this.log("Camera error: " + error.message, "error");
      if (this.config.onError) {
        this.config.onError(error);
      }
      throw error;
    }
  }

  async stop() {
    this.isRunning = false;

    // Stop tracking data timer
    this.stopTrackingDataTimer();

    if (this.camera) {
      await this.camera.stop();
      this.camera = null;
    }

    // Remove event listeners
    if (this.resizeListener) {
      window.removeEventListener('resize', this.resizeListener);
      this.video.removeEventListener('loadedmetadata', this.resizeListener);
      this.resizeListener = null;
    }

    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Reset stats
    this.faceCount = 0;
    this.lastFaceCount = -1;
    this.awayStartTime = null;
    this.totalAwayTime = 0;
    this.distractedStartTime = null;
    this.totalDistractedTime = 0;
    this.faceCountChanges = 0;
    this.currentFaces = [];
    this.lastGazeState = null;
    this.gazeHistory = [];
    this.frameCounter = 0;
    this.framesSkipped = 0;
    this.canvasUpdates = 0;
    this.isIdle = false;
    
    // Reset retina tracking
    this.retinaLocations = [];
    this.lastRetinaPosition = null;
    this.lastRetinaLocationRecord = Date.now();

    this.log("Camera stopped", "info");
  }

  // Configuration methods
  updateConfig(newConfig) {
    this.config = { ...this.config, ...newConfig };
    this.log("Configuration updated", "info");
  }

  getConfig() {
    return { ...this.config };
  }

  // NEW: Live control methods for HTML interface
  setFrameRate(fps) {
    const newFps = Math.max(5, Math.min(30, parseInt(fps)));
    this.config.targetFps = newFps;
    this.log(`Frame rate changed to ${newFps} FPS`, "info");
  }

  setFrameSkip(skip) {
    const newSkip = Math.max(1, Math.min(5, parseInt(skip)));
    this.config.frameSkip = newSkip;
    this.log(`Frame skip changed to process every ${newSkip} frame(s)`, "info");
  }

  setPauseOnIdle(enabled) {
    this.config.pauseOnIdle = Boolean(enabled);
    this.log(`Pause on idle ${enabled ? 'enabled' : 'disabled'}`, "info");
  }

  setReducedCanvas(enabled) {
    this.config.reducedCanvas = Boolean(enabled);
    this.log(`Reduced canvas updates ${enabled ? 'enabled' : 'disabled'}`, "info");
  }

  setHorizontalThreshold(threshold) {
    const newThreshold = Math.max(0.1, Math.min(1.0, parseFloat(threshold)));
    this.config.horizontalThreshold = newThreshold;
    this.log(`Horizontal gaze threshold changed to ${newThreshold}`, "info");
  }

  setVerticalThreshold(threshold) {
    const newThreshold = Math.max(0.05, Math.min(0.5, parseFloat(threshold)));
    this.config.verticalThreshold = newThreshold;
    this.log(`Vertical gaze threshold changed to ${newThreshold}`, "info");
  }

  setGazeHistorySize(size) {
    const newSize = Math.max(2, Math.min(10, parseInt(size)));
    this.config.gazeHistorySize = newSize;
    // Clear existing history to apply new size immediately
    this.gazeHistory = [];
    this.log(`Gaze smoothing changed to ${newSize} frames`, "info");
  }

  setShowGazeVector(enabled) {
    this.config.showGazeVector = Boolean(enabled);
    this.log(`Gaze direction indicator ${enabled ? 'enabled' : 'disabled'}`, "info");
  }

  setShowEyePoints(enabled) {
    this.config.showEyePoints = Boolean(enabled);
    this.log(`Eye tracking points ${enabled ? 'enabled' : 'disabled'}`, "info");
  }

  setShowFaceRectangle(enabled) {
    this.config.showFaceRectangle = Boolean(enabled);
    this.log(`Face rectangle ${enabled ? 'enabled' : 'disabled'}`, "info");
  }

  setEnableLogs(enabled) {
    this.config.enableLogs = Boolean(enabled);
    this.log(`Console logging ${enabled ? 'enabled' : 'disabled'}`, "info");
  }

  // Retina tracking configuration methods
  setTrackRetinaLocations(enabled) {
    this.config.trackRetinaLocations = Boolean(enabled);
    if (!enabled) {
      this.retinaLocations = [];
      this.lastRetinaPosition = null;
    }
    this.log(`Retina location tracking ${enabled ? 'enabled' : 'disabled'}`, "info");
  }

  setRetinaLocationChangeThreshold(threshold) {
    const newThreshold = Math.max(0.01, Math.min(1.0, parseFloat(threshold)));
    this.config.retinaLocationChangeThreshold = newThreshold;
    this.log(`Retina location change threshold set to ${(newThreshold * 100).toFixed(1)}%`, "info");
  }

  setRetinaLocationInterval(seconds) {
    const newInterval = Math.max(1, parseInt(seconds));
    this.config.retinaLocationInterval = newInterval;
    this.log(`Retina location recording interval set to ${newInterval} seconds`, "info");
  }

  // Set performance mode
  setPerformanceMode(mode) {
    if (!mode || mode === "manual") {
      this.config.performanceMode = null;
      this.log("Performance mode set to manual - use individual controls", "info");
      return;
    }
    
    if (!this.performancePresets[mode]) {
      this.log(`Unknown performance mode "${mode}". Available modes: ${Object.keys(this.performancePresets).join(', ')}`, "error");
      return;
    }
    
    this.config.performanceMode = mode;
    const preset = this.performancePresets[mode];
    
    // Apply preset settings
    this.config.targetFps = preset.targetFps;
    this.config.frameSkip = preset.frameSkip;
    this.config.pauseOnIdle = preset.pauseOnIdle;
    this.config.reducedCanvas = preset.reducedCanvas;
    
    this.log(`Performance mode changed to "${mode}": ${preset.description}`, "success");
    this.log(`New settings - FPS: ${preset.targetFps}, Frame Skip: ${preset.frameSkip}, Pause on Idle: ${preset.pauseOnIdle}, Reduced Canvas: ${preset.reducedCanvas}`, "info");
  }

  // Set sensitivity mode
  setSensitivityMode(mode) {
    if (!mode || mode === "manual") {
      this.config.sensitivityMode = null;
      this.log("Sensitivity mode set to manual - use individual gaze controls", "info");
      return;
    }
    
    if (!this.sensitivityPresets[mode]) {
      this.log(`Unknown sensitivity mode "${mode}". Available modes: ${Object.keys(this.sensitivityPresets).join(', ')}`, "error");
      return;
    }
    
    this.config.sensitivityMode = mode;
    const preset = this.sensitivityPresets[mode];
    
    // Apply preset settings
    this.config.horizontalThreshold = preset.horizontalThreshold;
    this.config.verticalThreshold = preset.verticalThreshold;
    this.config.gazeHistorySize = preset.gazeHistorySize;
    
    this.log(`Sensitivity mode changed to "${mode}": ${preset.description}`, "success");
    this.log(`New settings - Horizontal: ${preset.horizontalThreshold}, Vertical: ${preset.verticalThreshold}, Smoothing: ${preset.gazeHistorySize} frames`, "info");
  }

  // Get available performance modes
  getPerformanceModes() {
    return Object.keys(this.performancePresets).map(mode => ({
      value: mode,
      label: mode.charAt(0).toUpperCase() + mode.slice(1),
      description: this.performancePresets[mode].description
    }));
  }

  // Get available sensitivity modes
  getSensitivityModes() {
    return Object.keys(this.sensitivityPresets).map(mode => ({
      value: mode,
      label: mode.charAt(0).toUpperCase() + mode.slice(1),
      description: this.sensitivityPresets[mode].description
    }));
  }

  // Batch update method for multiple settings
  updateSettings(settings) {
    const validSettings = {
      performanceMode: (val) => this.setPerformanceMode(val),
      sensitivityMode: (val) => this.setSensitivityMode(val),
      targetFps: (val) => this.setFrameRate(val),
      frameSkip: (val) => this.setFrameSkip(val),
      pauseOnIdle: (val) => this.setPauseOnIdle(val),
      reducedCanvas: (val) => this.setReducedCanvas(val),
      horizontalThreshold: (val) => this.setHorizontalThreshold(val),
      verticalThreshold: (val) => this.setVerticalThreshold(val),
      gazeHistorySize: (val) => this.setGazeHistorySize(val),
      showGazeVector: (val) => this.setShowGazeVector(val),
      showEyePoints: (val) => this.setShowEyePoints(val),
      showFaceRectangle: (val) => this.setShowFaceRectangle(val),
      enableLogs: (val) => this.setEnableLogs(val),
      trackRetinaLocations: (val) => this.setTrackRetinaLocations(val),
      retinaLocationChangeThreshold: (val) => this.setRetinaLocationChangeThreshold(val),
      retinaLocationInterval: (val) => this.setRetinaLocationInterval(val)
    };

    Object.keys(settings).forEach(key => {
      if (validSettings[key]) {
        validSettings[key](settings[key]);
      }
    });
  }

  // Set tracking data posting interval
  setTrackingDataInterval(seconds) {
    const newInterval = Math.max(0, parseInt(seconds));
    this.config.postTrackingDataInterval = newInterval;
    
    if (this.isRunning) {
      if (newInterval > 0 && this.config.onPostTrackingData) {
        this.startTrackingDataTimer();
        this.log(`Tracking data interval changed to ${newInterval} seconds`, "info");
      } else {
        this.stopTrackingDataTimer();
        this.log("Tracking data posting disabled", "info");
      }
    } else {
      this.log(`Tracking data interval set to ${newInterval} seconds (will start when tracking begins)`, "info");
    }
  }

  // Set tracking data callback
  setTrackingDataCallback(callback) {
    this.config.onPostTrackingData = callback;
    
    if (this.isRunning) {
      if (callback && this.config.postTrackingDataInterval > 0) {
        this.startTrackingDataTimer();
        this.log("Tracking data callback set and timer started", "info");
      } else {
        this.stopTrackingDataTimer();
        this.log("Tracking data callback removed and timer stopped", "info");
      }
    } else {
      this.log("Tracking data callback set (will start when tracking begins)", "info");
    }
  }

  // Force post tracking data immediately
  forcePostTrackingData() {
    if (!this.config.onPostTrackingData) {
      this.log("No tracking data callback configured", "warning");
      return;
    }
    
    this.postTrackingData();
    this.log("Tracking data posted immediately", "info");
  }

  getStats() {
    let currentAwayTime = this.totalAwayTime;
    if (this.awayStartTime !== null) {
      currentAwayTime += Date.now() - this.awayStartTime;
    }

    let currentDistractedTime = this.totalDistractedTime;
    if (this.distractedStartTime !== null) {
      currentDistractedTime += Date.now() - this.distractedStartTime;
    }

    return {
      faceCount: this.faceCount,
      faceCountChanges: this.faceCountChanges,
      awayTime: Math.floor(currentAwayTime / 1000),
      distractedTime: Math.floor(currentDistractedTime / 1000),
      processingFps: this.processingFps,
      framesSkipped: this.framesSkipped,
      canvasUpdates: this.canvasUpdates,
      gazeState: this.lastGazeState,
      isRunning: this.isRunning,
      isIdle: this.isIdle
    };
  }

  // Utility methods
  isReady() {
    return this.isModelLoaded;
  }

  isActive() {
    return this.isRunning;
  }

  destroy() {
    if (this.isRunning) {
      this.stop();
    }
    
    // Ensure tracking data timer is stopped
    this.stopTrackingDataTimer();
    
    if (this.canvas && this.canvas.parentNode) {
      this.canvas.parentNode.removeChild(this.canvas);
    }
    
    this.log("Gazer instance destroyed", "info");
  }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = Gazer;
}

// Export for ES6 modules
if (typeof window !== 'undefined') {
  window.Gazer = Gazer;
}