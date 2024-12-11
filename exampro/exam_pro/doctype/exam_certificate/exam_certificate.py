# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt
import os
import subprocess
import tempfile

import frappe
from frappe.model.document import Document


class ExamCertificate(Document):

    def before_save(self):
        # only one certificate per exam submission
        existing_certs = frappe.get_all("LMS Exam Certificate", filters={"exam_submission": self.exam_submission})
        if len(existing_certs) > 0:
            frappe.throw("Duplicate certificate exist for exam submission {}.".format(self.exam_submission))


    def after_insert(self):
        self.send_email()

    def can_send_certificate(self):
        has_certification = frappe.db.get_value("LMS Exam", self.exam, "enable_certification")
        assert has_certification, "Exam does not have certification enabled."
        # assert result status
        result_status = frappe.db.get_value("LMS Exam Submission", self.exam_submission, "result_status")
        assert result_status == "Passed", "Exam is not passed. Can't send certificate."

    def send_email(self):
        self.can_send_certificate()

        cert_template = frappe.db.get_value("LMS Exam", self.exam, "certificate_template")
        cert_template_path = frappe.db.get_value("LMS Exam Certificate Template", cert_template, "template_path")
        assert cert_template_path
        assert os.path.exists(cert_template_path)

        # Render certificate content
        context = {
            "name": self.member_name,
            "score": frappe.db.get_value("LMS Exam Submission", self.exam_submission, "total_marks"),
            "total_marks": frappe.db.get_value("LMS Exam", self.exam, "total_marks")
        }
        input_html = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.html')
        cert_pdf = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pdf')

        # template temporary file
        with open(cert_template_path, "r") as file:
            html_content = file.read()
            rendered_html = frappe.render_template(html_content, context)
            # Save the rendered HTML to a new file
            with open(input_html.name, "w") as file:
                file.write(rendered_html)

        # Generate PDF
        command = [
            "wkhtmltopdf",
            "-L", "0mm",
            "-R", "0mm",
            "-T", "0mm",
            "-B", "0mm",
            "--no-outline",
            "--no-pdf-compression",
            "--page-width", "9.8in",
            "--page-height", "13.5in",
            "--disable-smart-shrinking",
            input_html.name,
            cert_pdf.name
        ]
        # Execute the command
        try:
            subprocess.run(command, check=True)
            print("PDF generated successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error generating PDF: {e}")

        # Retrieve the email template document
        email_template = frappe.get_doc("Email Template", "Exam Certificate Issue")

        # Render the subject and message
        subject = frappe.render_template(email_template.subject, context)
        message = frappe.render_template(email_template.response, context)

        member_email = frappe.db.get_value("User", self.member, "email")

        # Read the PDF content from the temporary file
        with open(cert_pdf.name, 'rb') as pdf_file:
            pdf_attachment = pdf_file.read()

        try:
            frappe.sendmail(
                recipients=[member_email],
                subject=subject,
                message=message,
                attachments=[{
                    'fname': 'certificate.pdf',
                    'fcontent': pdf_attachment
                }]
            )
        finally:
            # Delete the temporary file
            cert_pdf.close()
            input_html.close()


