# ExamPro

Proctored online examination platform built on **Frappe Framework v15**.

## Tech stack

- **Backend:** Python 3.10+, Frappe v15, MariaDB, Redis (3 instances: cache, queue, socketio)
- **Frontend:** Jinja2 templates + vanilla JS (`exampro/public/js/`)
- **PDF certificates:** weasyprint
- **Video storage:** AWS S3 or Cloudflare R2 (direct browser uploads via presigned URLs)

## Local development

Enter the dev container first, then use `bench`:

```bash
distrobox enter frappebox

bench start                          # web + workers + redis via Honcho
bench --site <site> migrate          # after pulling schema changes
bench --site <site> console          # Python REPL with Frappe context
bench --site <site> run-tests exampro
```

## Key directories

```
exampro/exam_pro/
  api/           # @frappe.whitelist() API endpoints
  doctype/       # Frappe DocType definitions (.json + .py per doctype)
  page/          # Frappe desk pages
exampro/www/     # Web-facing pages (.py controller + .html template pairs)
exampro/public/  # Static assets (JS, CSS)
exampro/fixtures/# Default roles/templates seeded on install
```

## API pattern

All server functions live in `exam_pro/api/` and are decorated with `@frappe.whitelist()`.

```python
# Python
@frappe.whitelist()
def my_function(arg):
    ...
```

```js
// JavaScript caller
frappe.call({ method: "exampro.exam_pro.api.<module>.<fn>", args: { arg: value } })
```

## Roles

| Role | Access |
|------|--------|
| `Exam Manager` | Admin — full access to all exams and data |
| `Exam Partner` | Tenant-scoped content creator (own exams/questions only) |
| `Examiner` | Evaluates subjective answers for assigned schedules |
| `Candidate / Member` | Takes exams and quizzes |

## Do not

- Commit AWS/R2 credentials. They live in the `Exam Settings` doctype, populated at deploy time.
- Route video through the app server. Browsers upload video chunks directly to S3/R2 via presigned POST URLs — the server never touches video bytes.
- Add Font Awesome or Bootstrap Icons — use Feather Icons only.
