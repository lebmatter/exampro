# Roles & Permissions

## Four roles

| Role | Who | What they can do |
|------|-----|-----------------|
| `Exam Manager` | Platform admin | Full access — all exams, questions, submissions, settings, any partner's data |
| `Exam Partner` | Tenant / content creator org | Create and manage own exams, questions, schedules, and batches only |
| `Examiner` | Manual evaluator | View and grade Exam Submissions assigned to them |
| `Candidate / Member` | Exam taker | Take exams, view own results, download own certificates |

## Multi-tenancy

ExamPro supports multiple organisations (partners) sharing a single installation. Each partner's data is isolated by default.

**`Exam Partner` doctype** — represents a partner organisation.

**`Exam Partner User` child table** — lists the Frappe users who belong to that partner.

All Studio API functions call `_assert_exam_partner()` (in `exam_studio.py`) before any read or write. This guard:
1. Identifies which `Exam Partner` the calling user belongs to
2. Scopes the query to only that partner's records
3. Raises a `PermissionError` if the user tries to access another partner's data

`Exam Manager` role bypasses this guard and can see all data.

## Permissions matrix

| Action | Exam Manager | Exam Partner | Examiner | Candidate |
|--------|:---:|:---:|:---:|:---:|
| Create / edit exams | ✓ | ✓ (own) | — | — |
| View all submissions | ✓ | ✓ (own) | — | — |
| Grade subjective answers | ✓ | — | ✓ (assigned) | — |
| Monitor via proctor UI | ✓ | — | — | — |
| Access Exam Settings | ✓ | — | — | — |
| Take exams | — | — | — | ✓ |
| View own results | — | — | — | ✓ |

## Adding a new partner

1. In Frappe Desk, open **Exam Partner** and create a new record
2. Add staff users via the **Exam Partner User** child table
3. Assign the `Exam Partner` role to each staff user in **User → Roles**

Those users can now log in to `/exam-studio` and manage their own exams and questions.
