# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
import json
import pdfkit
from frappe.model.document import Document
from frappe.utils import get_site_path
import os


class ExamCertificateTemplate(Document):
	def generate_pdf(self, context_data=None):
		"""Generate PDF from HTML template using wkhtmltopdf"""
		if not self.html_template:
			frappe.throw("HTML template is required to generate PDF")
		
		# Parse wkhtmltopdf parameters
		pdf_options = {}
		if self.wkhtmltopdf_params:
			try:
				pdf_options = json.loads(self.wkhtmltopdf_params)
			except json.JSONDecodeError:
				frappe.throw("Invalid JSON in wkhtmltopdf parameters")
		
		# Default PDF options
		default_options = {
			'page-size': 'A4',
			'margin-top': '0.75in',
			'margin-right': '0.75in',
			'margin-bottom': '0.75in',
			'margin-left': '0.75in',
			'encoding': "UTF-8",
			'no-outline': None
		}
		
		# Merge default options with custom ones
		pdf_options = {**default_options, **pdf_options}
		
		# Render HTML template with context
		html_content = self.html_template
		if context_data:
			html_content = frappe.render_template(self.html_template, context_data)
		
		# Generate PDF
		try:
			pdf_bytes = pdfkit.from_string(html_content, False, options=pdf_options)
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
