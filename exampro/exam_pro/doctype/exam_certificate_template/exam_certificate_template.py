# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document


class ExamCertificateTemplate(Document):
			
	def generate_pdf(self, context_data=None):
		"""Generate PDF from HTML template using WeasyPrint"""
		if not self.html_template:
			frappe.throw("HTML template is required to generate PDF")

		html_content = self.html_template
		if context_data:
			html_content = frappe.render_template(self.html_template, context_data)

		try:
			from weasyprint import HTML as WeasyHTML
			pdf_bytes = WeasyHTML(string=html_content).write_pdf()
			return pdf_bytes
		except Exception as e:
			frappe.throw(f"Error generating PDF: {str(e)}")
	
	def preview_template(self, context_params=None):
		"""Preview template with optional context parameters"""
		context_data = {}
		if context_params:
			try:
				context_data = json.loads(context_params)
			except json.JSONDecodeError:
				frappe.throw("Invalid JSON in context parameters")
		
		# Generate PDF for preview
		pdf_bytes = self.generate_pdf(context_data)
		
		# Return PDF as base64 for browser display
		import base64
		pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
		
		return {
			'pdf': pdf_base64,
			'filename': f"{self.title or 'certificate'}_preview.pdf"
		}


@frappe.whitelist()
def preview_certificate_template(template_name, context_params=None):
	"""API endpoint for template preview"""
	template = frappe.get_doc("Exam Certificate Template", template_name)
	return template.preview_template(context_params)
