// Copyright (c) 2024, Labeeb Mattra and contributors
// For license information, please see license.txt

frappe.ui.form.on("Exam Certificate Template", {
	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__('Preview Template'), function() {
				show_preview_dialog(frm);
			});
		}
	}
});

function show_preview_dialog(frm) {
	// Extract template variables from HTML template
	const template_vars = extract_template_variables(frm.doc.html_template);
	const sample_data = generate_sample_data(template_vars);
	
	let d = new frappe.ui.Dialog({
		title: 'Preview Certificate Template',
		fields: [
			{
				label: 'Template Variables',
				fieldname: 'template_info',
				fieldtype: 'HTML',
				options: `<div style="margin-bottom: 15px;">
					<strong>Available variables:</strong> ${template_vars.join(', ')}
				</div>`
			},
			{
				label: 'Context Parameters (JSON)',
				fieldname: 'context_params',
				fieldtype: 'JSON',
				description: 'Modify the values below to customize the certificate preview',
				default: JSON.stringify(sample_data, null, 2)
			}
		],
		primary_action_label: 'Preview',
		primary_action(values) {
			preview_template(frm.doc.name, values.context_params);
			d.hide();
		}
	});
	
	// Set the default value after dialog is shown
	d.show();
	d.set_value('context_params', JSON.stringify(sample_data, null, 2));
}

function extract_template_variables(html_template) {
	if (!html_template) return [];
	
	// Regular expressions to match Jinja2 variables
	const variable_patterns = [
		/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^}]*)?\s*\}\}/g,  // {{ variable }} or {{ variable | filter }}
		/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+or\s+[^}]+\s*\}\}/g,     // {{ variable or "default" }}
	];
	
	let variables = new Set();
	
	// Extract variables using different patterns
	variable_patterns.forEach(pattern => {
		let match;
		while ((match = pattern.exec(html_template)) !== null) {
			const variable_name = match[1].trim();
			// Skip Jinja2 functions and filters
			if (!['if', 'endif', 'for', 'endfor', 'else', 'elif'].includes(variable_name)) {
				variables.add(variable_name);
			}
		}
	});
	
	// Also look for variables in conditional statements like {% if variable %}
	const conditional_pattern = /\{%\s*if\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*%\}/g;
	let match;
	while ((match = conditional_pattern.exec(html_template)) !== null) {
		variables.add(match[1].trim());
	}
	
	return Array.from(variables).sort();
}

function generate_sample_data(template_vars) {
	const sample_data = {};
	
	// Generate sample values based on variable names
	template_vars.forEach(variable => {
		switch (variable.toLowerCase()) {
			case 'student_name':
				sample_data[variable] = 'John Doe';
				break;
			case 'exam_title':
				sample_data[variable] = 'Sample Exam Title';
				break;
			case 'score':
				sample_data[variable] = '85';
				break;
			case 'marks_obtained':
				sample_data[variable] = '17';
				break;
			case 'total_marks':
				sample_data[variable] = '20';
				break;
			case 'pass_percentage':
				sample_data[variable] = '70';
				break;
			case 'completion_date':
				sample_data[variable] = frappe.datetime.get_today();
				break;
			case 'exam_duration':
				sample_data[variable] = '60 minutes';
				break;
			case 'instructor_name':
				sample_data[variable] = 'Dr. Smith';
				break;
			case 'institution_name':
				sample_data[variable] = 'Example Institution';
				break;
			case 'certificate_id':
				sample_data[variable] = 'CERT-' + Math.random().toString(36).substr(2, 8).toUpperCase();
				break;
			case 'grade':
				sample_data[variable] = 'A';
				break;
			default:
				// Generate a sample value based on variable name pattern
				if (variable.includes('name')) {
					sample_data[variable] = 'Sample Name';
				} else if (variable.includes('date')) {
					sample_data[variable] = frappe.datetime.get_today();
				} else if (variable.includes('score') || variable.includes('mark') || variable.includes('percentage')) {
					sample_data[variable] = '80';
				} else if (variable.includes('id')) {
					sample_data[variable] = 'ID-' + Math.random().toString(36).substr(2, 6).toUpperCase();
				} else {
					sample_data[variable] = 'Sample Value';
				}
				break;
		}
	});
	
	return sample_data;
}

function preview_template(template_name, context_params) {
	frappe.call({
		method: 'exampro.exam_pro.doctype.exam_certificate_template.exam_certificate_template.preview_certificate_template',
		args: {
			template_name: template_name,
			context_params: context_params
		},
		callback: function(r) {
			if (r.message) {
				// Create blob from base64 data
				const byteCharacters = atob(r.message.pdf);
				const byteNumbers = new Array(byteCharacters.length);
				for (let i = 0; i < byteCharacters.length; i++) {
					byteNumbers[i] = byteCharacters.charCodeAt(i);
				}
				const byteArray = new Uint8Array(byteNumbers);
				const blob = new Blob([byteArray], {type: 'application/pdf'});
				
				// Create URL and open in new window
				const url = URL.createObjectURL(blob);
				window.open(url, '_blank');
				
				// Clean up the URL after a delay
				setTimeout(() => URL.revokeObjectURL(url), 1000);
			}
		},
		error: function(r) {
			frappe.msgprint({
				title: 'Error',
				message: r.message || 'Failed to generate preview',
				indicator: 'red'
			});
		}
	});
}
