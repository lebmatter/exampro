# Certificates

ExamPro generates PDF certificates for candidates who pass an exam, using a customizable HTML/CSS template.

## Key doctypes

| Doctype | Purpose |
|---------|---------|
| `Exam Certificate Template` | HTML/CSS template for the certificate design |
| `Exam Certificate` | A generated certificate for one candidate — links to template, submission, and PDF file |
| `Certificate Verification Request` | Audit record created when a third party verifies a certificate |

## Generation

Certificates are created automatically when:
- `result_status = "Passed"` on the Exam Submission
- `enable_certification = 1` on the Exam

PDF rendering uses **weasyprint** (Python). The HTML template is rendered with candidate-specific merge fields, then converted to PDF.

## Template authoring

`Exam Certificate Template` stores the full HTML/CSS for the certificate layout. Supported merge fields:

- Candidate name
- Exam title
- Score / marks
- Pass date
- Exam Manager / issuing organisation name

Templates are authored in the Frappe Desk interface.

## Automated email

On certificate generation, the PDF is attached and sent to the candidate's registered email address.

## Public verification

Certificates can be verified by third parties at `/certificate-verify`.

The verification flow creates a `Certificate Verification Request` record, providing an audit trail of who verified which certificate and when.
