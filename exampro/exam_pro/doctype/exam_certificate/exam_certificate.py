# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ExamCertificate(Document):

    def before_save(self):
        # only one certificate per exam submission
        existing_certs = frappe.get_all("Exam Certificate", filters={"exam_submission": self.exam_submission})
        if len(existing_certs) > 0:
            frappe.throw("Duplicate certificate exist for exam submission {}.".format(self.exam_submission))


    def after_insert(self):
        self.send_email()

    def can_send_certificate(self):
        has_certification = frappe.db.get_value("Exam", self.exam, "enable_certification")
        assert has_certification, "Exam does not have certification enabled."
        # assert result status
        result_status = frappe.db.get_value("Exam Submission", self.exam_submission, "result_status")
        assert result_status == "Passed", "Exam is not passed. Can't send certificate."

    def send_email(self):
        self.can_send_certificate()

        cert_template = frappe.db.get_value("Exam", self.exam, "certificate_template")
        if not cert_template:
            frappe.throw("No certificate template configured for this exam")

        # Get the certificate template document
        template_doc = frappe.get_doc("Exam Certificate Template", cert_template)

        # Prepare context data for the certificate
        exam_submission = frappe.get_doc("Exam Submission", self.exam_submission)
        exam_doc = frappe.get_doc("Exam", self.exam)
        
        context = {
            "student_name": self.candidate_name,
            "exam_title": exam_doc.title,
            "score": exam_submission.percentage or 0,
            "marks_obtained": exam_submission.total_marks or 0,
            "total_marks": exam_doc.total_marks or 0,
            "pass_percentage": exam_doc.pass_percentage or 0,
            "completion_date": frappe.utils.format_date(exam_submission.modified, "dd MMM yyyy"),
            "exam_duration": f"{exam_doc.duration} minutes" if exam_doc.duration else "N/A",
            "certificate_id": self.name,
            "issue_date": frappe.utils.format_date(self.issue_date, "dd MMM yyyy") if self.issue_date else frappe.utils.format_date(frappe.utils.nowdate(), "dd MMM yyyy")
        }

        # Save the template parameters used
        self.saved_params = frappe.as_json(context)
        
        # Generate PDF using the template's generate_pdf method
        try:
            pdf_bytes = template_doc.generate_pdf(context)
        except Exception as e:
            frappe.throw(f"Error generating certificate PDF: {str(e)}")

        # Retrieve the email template document
        try:
            email_template = frappe.get_doc("Email Template", "Exam Certificate Issue")
            # Render the subject and message
            subject = frappe.render_template(email_template.subject, context)
            message = frappe.render_template(email_template.response, context)
        except frappe.DoesNotExistError:
            # Fallback email content if template doesn't exist
            subject = f"Certificate for {exam_doc.title}"
            message = f"Dear {self.candidate_name},<br><br>Congratulations! Please find your certificate attached.<br><br>Best regards"

        candidate_email = frappe.db.get_value("User", self.candidate, "email")
        if not candidate_email:
            frappe.throw(f"No email found for candidate {self.candidate}")

        # Send email with PDF attachment
        try:
            frappe.sendmail(
                recipients=[candidate_email],
                subject=subject,
                message=message,
                attachments=[{
                    'fname': f'certificate_{self.name}.pdf',
                    'fcontent': pdf_bytes
                }]
            )
            frappe.msgprint(f"Certificate sent successfully to {candidate_email}")
        except Exception as e:
            frappe.throw(f"Error sending certificate email: {str(e)}")
        
        # Save the document to persist saved_params
        self.save()
    
    def generate_pdf(self):
        """Generate certificate PDF for download"""
        cert_template = frappe.db.get_value("Exam", self.exam, "certificate_template")
        if not cert_template:
            frappe.throw("No certificate template configured for this exam")

        # Get the certificate template document
        template_doc = frappe.get_doc("Exam Certificate Template", cert_template)

        # Use saved context if available, otherwise generate new context
        if self.saved_params:
            try:
                context = frappe.parse_json(self.saved_params)
            except:
                context = self._generate_context()
        else:
            context = self._generate_context()
        
        # Generate and return PDF bytes
        return template_doc.generate_pdf(context)
    
    def _generate_context(self):
        """Generate context data for certificate template"""
        # Prepare context data for the certificate
        exam_submission = frappe.get_doc("Exam Submission", self.exam_submission)
        exam_doc = frappe.get_doc("Exam", self.exam)
        
        # Calculate percentage if not available in submission
        percentage = 0
        if exam_doc.total_marks and exam_submission.total_marks:
            percentage = round((exam_submission.total_marks / exam_doc.total_marks) * 100, 2)
        
        return {
            "student_name": self.candidate_name,
            "exam_title": exam_doc.title,
            "score": percentage,
            "marks_obtained": exam_submission.total_marks or 0,
            "total_marks": exam_doc.total_marks or 0,
            "pass_percentage": exam_doc.pass_percentage or 0,
            "completion_date": frappe.utils.format_date(exam_submission.modified, "dd MMM yyyy"),
            "exam_duration": f"{exam_doc.duration} minutes" if exam_doc.duration else "N/A",
            "certificate_id": self.name,
            "issue_date": frappe.utils.format_date(self.issue_date, "dd MMM yyyy") if self.issue_date else frappe.utils.format_date(frappe.utils.nowdate(), "dd MMM yyyy")
        }


