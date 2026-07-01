# ExamPro Documentation

ExamPro is a **Frappe Framework v15** application for running video-proctored online examinations. It supports objective and subjective question types, live proctor monitoring, manual evaluation, certificate generation, and a lightweight Quick Quiz format.

## Feature map

| Page | Description |
|------|-------------|
| [Exams](exams.md) | Exam lifecycle — creation, scheduling, question loading, submission, grading |
| [Quick Quiz](quiz.md) | Lightweight quizzes — self-paced and live-hosted modes |
| [Studio](studio.md) | Unified authoring UI for exams, questions, quizzes, users, and calendar |
| [Proctoring](proctoring.md) | Video monitoring, attention scoring, warnings, and auto-termination |
| [Evaluation](evaluation.md) | Manual grading flow for subjective questions |
| [Certificates](certificates.md) | Certificate templates, PDF generation, and public verification |
| [Roles & Permissions](roles.md) | RBAC model and multi-tenancy via Exam Partner |
| [Analytics](analytics.md) | Score reports, leaderboards, and result exports |
| [Child Tables](tables.md) | Reference for all Frappe child table doctypes |
| [Deployment](DEPLOYMENT.md) | Infrastructure, S3/R2 setup, scaling, and SSL requirements |

## Quick start

1. **Install** — see [README](../README.md) for `bench get-app` / `bench install-app` commands.
2. **Configure storage** — set S3/R2 credentials in Desk → Exam Settings.
3. **Create content** — open `/exam-studio` and create your first exam or quiz.
4. **Deploy** — see [Deployment](deployment.md) for production setup.
