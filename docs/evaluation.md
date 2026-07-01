# Evaluation

Manual evaluation applies to exams with **subjective (open-ended) questions**. Objective questions are auto-graded immediately on submission.

## When it applies

An Exam Submission enters manual evaluation when:
- The exam contains at least one `Subjective` question type
- At least one submitted answer has `evaluation_status = "Pending"` after auto-grading

## Key fields on Exam Submission

| Field | Values | Meaning |
|-------|--------|---------|
| `evaluation_status` | `Pending` / `Done` / `NA` | Overall grading state for the submission |
| `assigned_evaluator` | Frappe user | Examiner assigned to grade this submission |
| `total_marks` | float | Computed after all answers are graded |
| `result_status` | `Passed` / `Failed` / `NA` | Set after `evaluation_values()` runs |

## Key fields on Exam Answer (child table)

| Field | Values | Meaning |
|-------|--------|---------|
| `evaluation_status` | `Pending` / `Auto` / `Done` | Per-answer grading state |
| `evaluator_response` | text | Examiner's feedback on the answer |
| `mark` | float | Marks awarded for this answer |

## Examiner role

Examiners are assigned per Exam Schedule. The `Examiner` doctype designates a Frappe user as an evaluator. The `assigned_evaluator` field on Exam Submission links the specific examiner for that attempt.

## Grading flow

1. Examiner opens `/evaluate.html`
2. Page lists Exam Submissions with `evaluation_status = "Pending"` assigned to them
3. Examiner reviews each `submitted_answers` child row for subjective questions
4. Sets `mark` and optionally `evaluator_response` per answer
5. Sets answer's `evaluation_status = "Done"`
6. When all answers are graded, Exam Submission `evaluation_status` → `"Done"`

## Score calculation

`evaluation_values(exam, submitted_answers)` in `exampro/exam_pro/api/examops.py`:

1. Sums marks from auto-graded objective answers
2. Adds manually assigned marks from subjective answers
3. Computes `total_marks` and compares against `exam.pass_percentage`
4. Sets `result_status = "Passed"` or `"Failed"` (or `"NA"` if pass percentage is not set)
5. If `Passed` and `enable_certification = 1` on the Exam, triggers certificate generation
