# Quick Quiz

Quick Quiz is a lightweight quiz format — no proctoring, instant feedback, suitable for practice and engagement.

## Key doctypes

| Doctype | Purpose |
|---------|---------|
| `Quick Quiz` | Quiz definition — title, PIN, theme, randomization settings |
| `Quick Quiz Question` | Child table — questions embedded directly in the quiz |
| `Quick Quiz Answer` | Child table — answer options for each question |
| `Quick Quiz Submission` | A candidate's completed attempt with score |

## Differences from Exams

| Feature | Exam | Quick Quiz |
|---------|------|------------|
| Video proctoring | Optional | Never |
| Access control | Batch/invitation | PIN or public link |
| Feedback | After evaluation | Instant on submission |
| Live-hosted mode | No | Yes |
| Scheduling | Exam Schedule doctype | No — open/close manually |
| Question bank | Shared category-based bank | Embedded in quiz or imported |

## Two modes

### Self-paced
Share a link or PIN. Candidates join at any time while the quiz is open and receive their score immediately after submitting. Suitable for practice assessments.

### Live-hosted
The host controls the flow — they advance to each question and reveal the leaderboard between rounds. Candidates see questions only when the host shows them. Suitable for live classroom or event quizzes.

Host controls (via `quick_quiz.py`):
- `host_start_quiz()` / `host_end_quiz()` / `host_restart_quiz()`
- `host_next_question()` — advance to next question
- `host_show_leaderboard()` — broadcast current rankings
- `get_live_participants()` — real-time participant list

## Web route

`/quiz.html` — both self-paced and live-hosted use the same page; mode is determined by the quiz's configuration.

## API modules

| Module | Purpose |
|--------|---------|
| `exampro/exam_pro/api/quick_quiz_studio.py` | Quiz authoring — CRUD, AI generation, analytics |
| `exampro/exam_pro/api/quick_quiz.py` | Quiz taking — join, submit answers, leaderboard |

Key studio functions:
- `get_quiz_list()` / `get_quiz_detail()` / `save_quiz()` / `delete_quiz()` / `duplicate_quiz()`
- `generate_quiz_questions()` — AI-assisted: generates questions from a topic prompt
- `import_from_question_bank()` — pull questions from the shared Exam Question bank
- `get_quiz_submissions()` / `get_quiz_analytics()`

Key participant functions (all `allow_guest=True`):
- `get_quiz_info()` / `validate_pin()` / `join_quiz()`
- `submit_answer()` / `finish_quiz()`
- `get_quiz_results()` / `get_leaderboard()`
