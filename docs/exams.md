# Exams

## Key doctypes

| Doctype | Purpose |
|---------|---------|
| `Exam` | Exam definition — duration, pass percentage, proctoring settings, question weightage |
| `Exam Question` | Question bank entry (MCQ, True/False, Single-best-answer, Subjective) |
| `Exam Question Category` | Groups questions by topic for weightage-based selection |
| `Exam Schedule` | A scheduled run of an exam — date/time, type (Fixed/Flexible), batch assignments |
| `Exam Submission` | One candidate's attempt — status, answers, attention data, result |
| `Exam Answer` | Child table within Exam Submission — one row per submitted answer |
| `Exam Batch` | A named group of candidates |
| `Exam Batch User` | Child table linking candidates to an Exam Batch |

## Question types

- **MCQ** — multiple choice, one correct answer
- **True/False** — binary choice
- **Single-best-answer** — MCQ variant; semantically "best" rather than strictly correct
- **Subjective** — open-ended text answer, requires manual evaluation

Images can be attached to any question type.

## Exam lifecycle

```
Exam created in Studio
        ↓
Exam Schedule created (Fixed or Flexible timing)
        ↓
Candidates added to a Batch → Batch assigned to Schedule
  → Exam Submission created per candidate (status: Registered)
        ↓
Candidate opens /exam/<schedule_uuid>/
  → questions resolved from select_questions weightage table
  → Exam Submission status: Started
        ↓
Candidate submits answers (Exam Answer child rows)
  → objective questions auto-graded (is_correct flag)
  → subjective questions: evaluation_status = Pending
  → Exam Submission status: Submitted
        ↓
Evaluator grades subjective answers  →  see Evaluation docs
        ↓
evaluation_values() computes total_marks, result_status (Passed/Failed/NA)
        ↓
Certificate generated if Passed + enable_certification = 1
```

## Web routes

| Route | Description |
|-------|-------------|
| `/exam/<uuid>/` | Live exam taking interface |
| `/exam/<uuid>/invite` | Invitation link handler for candidates |
| `/exam/<uuid>/result` | Result display after submission |
| `/my-exams` | Candidate dashboard |
| `/open_exams` | Browse publicly available exams |
| `/exams/register` | Registration page for public exams |

## API module

`exampro/exam_pro/api/exam_studio.py`

Key functions:

- `get_exams()` / `save_exam()` / `duplicate_exam()` — exam CRUD
- `save_schedule()` / `get_exam_schedules()` / `get_conflicting_schedules()` — scheduling
- `add_candidates_to_schedule()` / `get_schedule_candidates()` — candidate management
- `get_batches()` / `create_batch()` / `add_users_to_batch()` — batch management
- `get_category_questions()` / `save_questions()` / `update_question()` — question bank
