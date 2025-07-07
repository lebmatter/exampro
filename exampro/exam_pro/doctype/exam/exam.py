# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import re
import random
import frappe
from frappe.model.document import Document

RE_SLUG_NOTALLOWED = re.compile("[^a-z0-9]+")

def generate_slug(title, doctype):
	result = frappe.get_all(doctype, fields=["name"])
	slugs = {row["name"] for row in result}
	return slugify(title, used_slugs=slugs)

def validate_image(path):
	if path and "/private" in path:
		file = frappe.get_doc("File", {"file_url": path})
		file.is_private = 0
		file.save(ignore_permissions=True)
		return file.file_url
	return path

def slugify(title, used_slugs=None):
	"""Converts title to a slug.

	If a list of used slugs is specified, it will make sure the generated slug
	is not one of them.

	    >>> slugify("Hello World!")
	    'hello-world'
	    >>> slugify("Hello World!", ['hello-world'])
	    'hello-world-2'
	    >>> slugify("Hello World!", ['hello-world', 'hello-world-2'])
	    'hello-world-3'
	"""
	if not used_slugs:
		used_slugs = []

	slug = RE_SLUG_NOTALLOWED.sub("-", title.lower()).strip("-")
	used_slugs = set(used_slugs)

	if slug not in used_slugs:
		return slug

	count = 2
	while True:
		new_slug = f"{slug}-{count}"
		if new_slug not in used_slugs:
			return new_slug
		count = count + 1

class Exam(Document):

	def validate(self):
		self.image = validate_image(self.image)

		if self.duration <= 0:
			frappe.thow("Duration should be greater than 0.")
		
		self.validate_weightage_table()

		if not self.pass_percentage:
			frappe.throw("Please enter a valid pass percentage")
		
		if self.pass_percentage > 100.0:
			frappe.throw("Pass percentage should not be more than 100")
		
		if self.show_result == "After Specific Date":
			if not self.show_result_after_date:
				frappe.throw("Specify date for showing result.")
		
		settings = frappe.get_single("Exam Settings")
		if self.enable_video_proctoring and not settings.validate_video_settings():
			frappe.throw("Video storage is not configured for proctoring.")


	def autoname(self):
		if not self.name:
			title = self.title
			if self.title == "New Exam":
				title = self.title + str(random.randint(0, 99))
			self.name = generate_slug(title, "Exam")

	def before_save(self):
		# TODO update question list only if the picked list is changed
		"""
		Function to update assigned questions
		> Validate if required no. of questions
		> Delete existing questions
		> Add questions

		returns: total marks, no of marks
		"""
		if self.question_type != "Choices":
			self.evaluation_required = 1
		else:
			self.evaluation_required = 0
		self.validate_weightage_table()

		self.added_questions = []
		
		total_qs = 0
		total_marks = 0
		for cat in self.select_questions:
			picked_questions = get_random_questions(
				cat.question_category, cat.mark_per_question,
				cat.no_of_questions, self.question_type
			)
			for qs in picked_questions:
				qs_data = frappe.db.get_value(
					"Exam Question", qs["name"],
					["question", "mark", "type"], as_dict=True
				)
				self.append("added_questions", {
						"exam_question": qs["name"],
						"question": qs_data["question"],
						"mark": qs_data["mark"],
						"question_type": qs_data["type"]
				})
				total_marks += qs_data["mark"]
				total_qs += 1
		
		# update count fields
		self.total_questions = total_qs
		self.total_marks = total_marks

	def validate_weightage_table(self):
		for cat in self.select_questions:
			if not cat.mark_per_question or not cat.no_of_questions:
				frappe.throw("No. of Qs & Marks per Qs columns for {} category should be more than 0.".format(
					cat.question_category
				))

			# check if selected no. of questions are available in question bank
			get_random_questions(
				cat.question_category, cat.mark_per_question, cat.no_of_questions,
				self.question_type
			)




	def __repr__(self):
		return f"<Exam#{self.name}>"


@frappe.whitelist(allow_guest=True)
def search_exam(text):
	exams = frappe.get_all(
		"Exam",
		or_filters={
			"title": ["like", f"%{text}%"],
			"tags": ["like", f"%{text}%"],
			"description": ["like", f"%{text}%"],
		},
		fields=["name", "title"],
	)
	return exams

def get_random_questions(category, mark_per_qs, no_of_qs, question_type):
	if question_type == "Mixed":
		cat_qs = frappe.get_all(
				"Exam Question",
				{"category": category, "mark": mark_per_qs},
		)
	else:
		cat_qs = frappe.get_all(
				"Exam Question",
				{"category": category, "mark": mark_per_qs, "type": question_type},
		)
	try:
		return random.sample(cat_qs, no_of_qs)
	except ValueError:
			frappe.throw(
				"Insufficient no. of {} mark '{}' questions in {} category. Available: {}".format(
				mark_per_qs, question_type, category, len(cat_qs)
			))

@frappe.whitelist()
def get_question_categories(exam):
    """
    Get all question categories with their counts and marks, along with the exam's current configuration.
    
    Args:
        exam (str): Name of the exam to get categories for
    """
    if not frappe.has_permission("Exam", "read"):
        return {"success": False, "error": _("Not permitted to view exam"), "categories": []}
    
    try:
        # Get the exam
        exam_doc = frappe.get_doc("Exam", exam)
        
        # Get categories with associated questions and marks
        # Group questions by category AND mark to show different rows for different mark values
        category_marks_questions = frappe.db.sql("""
            SELECT 
                eqc.name as category_id,
                eqc.title as category_name,
                IFNULL(eq.mark, 1) as marks_per_question,
                COUNT(eq.name) as question_count
            FROM 
                `tabExam Question Category` eqc
            LEFT JOIN 
                `tabExam Question` eq ON eq.category = eqc.name
            WHERE
                eq.name IS NOT NULL
            GROUP BY 
                eqc.name, eq.mark
            ORDER BY 
                eqc.title, eq.mark
        """, as_dict=True)
        
        # Also get categories that don't have questions yet
        empty_categories = frappe.db.sql("""
            SELECT 
                eqc.name as category_id,
                eqc.title as category_name,
                1 as marks_per_question,
                0 as question_count
            FROM 
                `tabExam Question Category` eqc
            LEFT JOIN 
                `tabExam Question` eq ON eq.category = eqc.name
            WHERE
                eq.name IS NULL
            GROUP BY 
                eqc.name
            ORDER BY 
                eqc.title
        """, as_dict=True)
        
        # Combine both sets of categories
        categories = category_marks_questions + empty_categories
        
        # Create a dictionary of the exam's current configuration
        # We need to track both category and marks per question
        exam_config = {}
        if exam_doc.added_questions:
            for question in exam_doc.added_questions:
                try:
                    # Get both category and mark for each question
                    question_data = frappe.db.get_value(
                        "Exam Question", 
                        question.exam_question, 
                        ["category", "mark"], 
                        as_dict=True
                    )
                    
                    if not question_data or not question_data.category:
                        continue
                        
                    marks = question_data.mark or 1  # Default to 1 if mark is None
                    
                    # Create a composite key: category_id:marks_per_question
                    composite_key = f"{question_data.category}:{marks}"
                    exam_config[composite_key] = exam_config.get(composite_key, 0) + 1
                        
                except Exception as e:
                    frappe.log_error(f"Error processing question {question.exam_question}: {str(e)}")
                    continue
        
        # Format the categories for the frontend with composite keys
        formatted_categories = []
        for cat in categories:
            # Create a unique identifier for this category+marks combination
            composite_key = f"{cat.category_id}:{cat.marks_per_question}"
            formatted_cat = {
                "id": composite_key,  # Unique ID for this category+marks combination
                "category_id": cat.category_id,
                "category_name": cat.category_name,
                "marks_per_question": cat.marks_per_question,
                "question_count": cat.question_count
            }
            formatted_categories.append(formatted_cat)
            
        return {
            "success": True, 
            "categories": formatted_categories,
            "exam_config": exam_config
        }
    
    except Exception as e:
        error_msg = f"Error getting question categories for exam {exam}: {str(e)}"
        frappe.log_error(frappe.get_traceback(), error_msg)
        return {"success": False, "error": str(e), "categories": []}