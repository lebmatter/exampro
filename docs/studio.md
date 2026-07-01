# Studio

The Studio is the unified authoring and management interface for exam creators.

## What it is

**URL:** `/exam-studio.html`

A single-page application with five tabs:

| Tab | Purpose |
|-----|---------|
| Exams | Create and manage exams, schedules, and batch assignments |
| Questions | Build and categorize the shared question bank |
| Quick Quiz | Create and manage lightweight quizzes |
| Users | Manage candidate batches |
| Calendar | View all upcoming and ongoing schedules |

## Exam authoring flow

1. **Create an Exam** — set title, duration, pass percentage, and proctoring options
2. **Add question categories** — define a weightage table (`Exam Category Settings`) specifying how many questions to draw from each category and marks per question
3. **Create a Schedule** — set date/time (Fixed) or allow flexible timing (Flexible), assign examiners
4. **Assign batches** — link `Exam Batch` groups to the schedule via `Schedule Batch Assignment`; candidates receive invitations

## Question bank

Questions are stored in `Exam Question` doctypes and grouped by `Exam Question Category`. They are reusable across multiple exams.

AI-assisted authoring functions in `exam_studio.py`:
- `generate_questions(category, count)` — generates MCQ questions from a category prompt
- `generate_help_text(question)` — writes an explanation for a question
- `generate_image(prompt, style)` — produces an image for a question (`"realistic"`, `"cartoon"`, `"exampro_slider"`)

## Multi-tenancy

`Exam Partner` organizations scope content to their own namespace. The `_assert_exam_partner()` guard in `exam_studio.py` enforces that partner users can only read and write their own exams and questions.

Partner staff are managed via the `Exam Partner User` child table on the `Exam Partner` doctype.

## State persistence

The Studio caches UI state in Redis so work-in-progress survives page refreshes and browser restarts.

- Key: `exam_studio_state:<user_id>`
- TTL: 24 hours
- Functions: `get_cached_state()`, `set_cached_state()`, `clear_cached_state()`

An equivalent cache exists for the Quick Quiz Studio: `quiz_studio_state:<user_id>`.

## API module

`exampro/exam_pro/api/exam_studio.py` (~1400 lines, 30+ whitelisted endpoints)
