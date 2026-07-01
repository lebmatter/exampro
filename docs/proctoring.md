# Proctoring

ExamPro's proctoring system provides real-time video monitoring, attention tracking, and configurable policy enforcement during exams.

## Overview

When an exam has `enable_video_proctoring = 1`, each candidate's session is:
- Recorded to S3/R2 via direct browser uploads
- Monitored live by an assigned proctor
- Scored for attention using gaze and face detection
- Subject to auto-termination on policy violations

## Proctoring data on Exam Submission

| Field | Description |
|-------|-------------|
| `assigned_proctor` | Frappe user assigned to monitor this candidate |
| `candidate_video` | S3/R2 URL to the assembled recording |
| `screenshot_gallery` | Periodic screenshots captured during the exam |
| `attention_score` | Computed 0–100 score from gaze and activity data |
| `warning_count` | Number of warnings issued by the proctor |
| `face_count_changes` | Count of face-detection anomalies (potential identity swaps) |
| `total_away_time` | Cumulative seconds candidate was away from screen |
| `total_distracted_time` | Cumulative seconds gaze was off the exam window |
| `retina_location_log` | Timestamped gaze position log |

## Video architecture

Browsers upload video chunks **directly to S3/R2** — the app server never handles video bytes.

```
Candidate browser
  → POST video chunk to presigned URL (60s TTL, max 10 MB per chunk)
  → S3 / Cloudflare R2 bucket
```

Presigned URL generation and chunk validation are handled in `exam_submission.py`. Bucket CORS must allow `PUT` from the exam domain (see [Deployment](deployment.md)).

## Attention scoring

`calculate_attention_score()` in `exampro/exam_pro/api/utils.py` combines:
- `face_count_changes` — anomalies suggesting someone else entered the frame
- `total_away_time` — time candidate left the screen
- `total_distracted_time` — time gaze was off the exam window

Returns a 0–100 score stored on Exam Submission.

## Proctor interface

**URL:** `/proctor.html`

Features:
- Live candidate video feed grid
- Two-way chat (`chatbox.js`) — proctor can message individual candidates
- Warning controls — proctor issues warnings; count stored in `warning_count`
- Post-exam review at `/proctor-archive.html` with video playback (`video_player.js`)

## JavaScript utilities

| File | Purpose |
|------|---------|
| `public/js/gazer.js` | ML-based gaze tracking — feeds attention and distraction metrics |
| `public/js/inactivityDetector.js` | Detects tab switches and inactivity |
| `public/js/screenCapture.js` | Screen recording (when `enable_screen_recording = 1`) |
| `public/js/proctorutils.js` | Proctor-side alert logic and UI helpers |

## Configuration

On the `Exam` doctype:

| Field | Effect |
|-------|--------|
| `enable_video_proctoring` | Turns on candidate video recording and proctor monitoring |
| `enable_screen_recording` | Also records the candidate's screen |
| `max_warning_count` | Auto-terminates the exam when this threshold is reached |
| `enable_live_chat` | Enables two-way chat between candidate and proctor |
