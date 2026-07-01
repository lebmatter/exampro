# Analytics & Reporting

## Analytics page

**URL:** `/exam-analytics`

Provides aggregated views of exam performance:
- Score distributions across candidates
- Pass / fail rates per exam
- Question-level statistics (correct answer rates per question)
- Attention and proctoring metrics summary

**API module:** `exampro/exam_pro/api/analytics.py`

## Result export

Exam Submissions can be exported as CSV for offline analysis. The bulk export feature (introduced in recent releases) lets Exam Managers download all submissions for a given schedule in one action from the Studio.

Exported fields include candidate name, score, result status, submission time, and proctoring metrics (attention score, warning count).

## Leaderboard

A ranked leaderboard is available per exam when `enable_leaderboard = 1` on the Exam doctype.

- **Frontend:** `exampro/public/js/leaderboard.js`
- **API:** `get_leaderboard()` in `quick_quiz.py` (also used by Quick Quiz live-hosted mode)
- Ranks candidates by total marks; ties resolved by submission time

## Proctoring metrics per submission

Available on each Exam Submission record and visible to proctors and Exam Managers:

| Metric | Description |
|--------|-------------|
| `attention_score` | 0–100 score from gaze and activity data |
| `warning_count` | Number of proctor warnings issued |
| `face_count_changes` | Face detection anomalies during the session |
| `total_away_time` | Seconds candidate was absent from the screen |
| `total_distracted_time` | Seconds gaze was off the exam window |

See [Proctoring](proctoring.md) for how these are computed.
