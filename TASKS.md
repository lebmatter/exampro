# ExamPro Feature Tasks

## Quick Wins

- [ ] Enable scheduler events in `hooks.py` — uncomment scheduler_events for auto-submission of expired exams
- [ ] Enable desk notifications — uncomment `notification_config` in `hooks.py`
- [ ] Wire up email sending — connect existing email templates to trigger points (exam assignment, reminders, score publish, certificate, proctor assignment) in `exam_submission.py`
- [ ] CSV result export — download button on schedule-dashboard to export candidate results per schedule
- [ ] Pre-exam system compatibility check — page to verify camera, mic, screen share, browser compatibility before exam day
- [ ] Configurable tab-switch limit — move hardcoded anti-cheat values to Exam Settings doctype

## Exam Analytics & Item Analysis

- [ ] Per-question stats: success rate, average time spent, discrimination index
- [ ] Exam-level stats: score distribution histogram, pass/fail breakdown, average completion time
- [ ] Schedule comparison: performance trends across repeated schedules of the same exam
- [ ] New `/exam-analytics` page for Exam Managers

## Bulk Export & Reporting

- [ ] Export exam results per schedule as CSV (candidate name, email, score, percentage, pass/fail, time taken, status)
- [ ] Export question-level breakdown per candidate
- [ ] Add export buttons to schedule-dashboard and proctor-archive pages

## Question Bank Enhancements

- [ ] Difficulty tagging (Easy/Medium/Hard) and topic tags on questions
- [ ] Random question selection: "Pick N random questions from category X, difficulty Y"
- [ ] Question versioning: track edits without breaking historical submissions
- [ ] Question import from CSV/spreadsheet
- [ ] Question usage stats: how many exams use each question, last used date

## Practice / Mock Exam Mode

- [ ] "Practice" flag on exams: no proctoring, no video, unlimited retakes, instant feedback
- [ ] Show correct answer and help text after each question submission
- [ ] Optional time limit (or untimed)
- [ ] No certificate generation, no leaderboard entry
- [ ] Accessible from candidate dashboard

## Candidate Self-Service Improvements

- [ ] Unified candidate portal: upcoming exams with countdown, past results, certificates in one view
- [ ] Download all certificates in bulk

## Advanced Proctor Tools

- [ ] Flag/bookmark suspicious moments with timestamped notes during live proctoring
- [ ] Proctor handoff: transfer candidate monitoring to another proctor mid-exam
- [ ] Incident report generation: compile flagged moments + video clips into a review document
- [ ] Bulk actions: terminate multiple candidates, send group messages

## Configurable Exam Policies & Anti-Cheat

- [ ] Per-exam configurable policies: max tab switches, inactivity timeout, grace period
- [ ] Copy-paste detection and blocking
- [ ] Browser lockdown mode (disable right-click, dev tools detection)
- [ ] IP-based access restriction

## Multi-Language / i18n Support

- [ ] Frappe translation system for UI strings
- [ ] Per-question language variants
- [ ] Exam instructions in multiple languages

## Webhook / Integration API

- [ ] Webhook notifications on key events: exam completed, score published, certificate issued
- [ ] REST API for external systems to query candidate results
- [ ] SSO integration (SAML, OAuth)
- [ ] LMS integration: auto-assign exams based on course completion
