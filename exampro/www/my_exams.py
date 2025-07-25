from datetime import datetime, timedelta
import frappe
from frappe.utils import now, format_datetime
from exampro.exam_pro.api.utils import submit_candidate_pending_exams


def get_user_exams(member=None, page=1, page_size=10):
	"""
	Get upcoming/ongoing exam of a candidate.
	Supports pagination with page and page_size parameters.
	"""
	res = []

	submissions = frappe.get_all(
		"Exam Submission",
		{"candidate": member or frappe.session.user},[
			"name",
			"exam_schedule",
			"status",
			"exam_started_time",
			"exam_submitted_time",
			"additional_time_given",
			"result_status"], ignore_permissions=True)
	for submission in submissions:
		schedule = frappe.get_doc("Exam Schedule", submission["exam_schedule"], ignore_permissions=True)
		exam = frappe.get_doc("Exam", schedule.exam, ignore_permissions=True)

		# end time is schedule start time + duration + additional time given
		end_time = schedule.start_date_time + timedelta(minutes=schedule.duration) + \
			timedelta(minutes=submission["additional_time_given"])
		if schedule.schedule_type == "Flexible":
			# For flexible schedules, we consider the end time as start time + duration + 5 min buffer
			end_time += timedelta(days=schedule.schedule_expire_in_days)

		# Check if certificate exists for this submission
		certificate_exists = frappe.db.exists("Exam Certificate", {"exam_submission": submission["name"]})
		exam.leaderboard = exam.leaderboard or "No Leaderboard"
		exam_details = {
			"exam_submission": submission["name"],
			"exam": schedule.exam,
			"exam_name": exam.name,
			"exam_title": exam.title,  # Add exam title for display
			"exam_schedule": submission["exam_schedule"],
			"start_time": schedule.start_date_time,
			"schedule_time": format_datetime(schedule.start_date_time, "dd MMM YYYY, HH:mm"),  # Added for template
			"end_time": end_time,
			"additional_time_given": submission["additional_time_given"],
			"submission_status": submission["status"],
			"status": submission["status"],  # Added for template
			"duration": f"{schedule.duration} min",  # Format duration as "X min"
			"enable_calculator": exam.enable_calculator,
			"schedule_status": schedule.get_status(),
			"schedule_type": schedule.schedule_type,
			"enable_video_proctoring": exam.enable_video_proctoring,
			"enable_chat": exam.enable_chat,
			"submission": submission["name"],  # Added for view result link
			"result_status": submission["result_status"],
			# Leaderboard information
			"leaderboard_enabled": exam.leaderboard != "No Leaderboard",
			"leaderboard_type": exam.leaderboard,
			# Certificate information
			"certification_enabled": exam.enable_certification,
			"certificate_exists": certificate_exists,
			"certificate_name": certificate_exists if certificate_exists else None
			}

		# make datetime in isoformat
		for key,val in exam_details.items():
			if isinstance(val, datetime):
				exam_details[key] = val.isoformat()

		# checks if current time is between schedule start and end time
		# ongoing exams can be in Not started, started or submitted states
		if exam_details["schedule_status"] == "Ongoing" and schedule.schedule_type == "Fixed" and submission["status"] in ["Registered", "Started"]:
			frappe.local.flags.redirect_location = "/exam"
			raise frappe.Redirect
		if exam_details["schedule_status"] == "Ongoing" and schedule.schedule_type == "Flexible":
			exam_details["flexible_schedule_status"] = "Finish before " + format_datetime(end_time, "dd MMM, HH:mm")
		# if time is over, submit if applicable
		if submission["status"] != "Submitted" and exam_details["schedule_status"] == "Completed":
			doc = frappe.get_doc("Exam Submission", submission["name"], ignore_permissions=True)
			doc.status = "Submitted"
			doc.save(ignore_permissions=True)
				
		# Set status field to match template expectations
		if submission["status"] == "Not Started":
			exam_details["status"] = "Upcoming"
		else:
			exam_details["status"] = submission["status"]
				
		res.append(exam_details)

	# Sort exams by schedule time
	res.sort(key=lambda x: x["start_time"], reverse=True)

	# Calculate pagination
	total_exams = len(res)
	total_pages = (total_exams + page_size - 1) // page_size  # Ceiling division
	start_idx = (page - 1) * page_size
	end_idx = min(start_idx + page_size, total_exams)
	
	# Return paginated results and pagination metadata
	return {
		"exams": res[start_idx:end_idx],
		"pagination": {
			"total": total_exams,
			"page": page,
			"page_size": page_size,
			"total_pages": total_pages,
			"has_prev": page > 1,
			"has_next": page < total_pages
		}
	}

def get_next_exam(exams):
	"""
	Get the next upcoming or current exam for the user.
	This now gets all exams (not just the paginated ones) to ensure we always show the correct next exam.
	"""
	# For the next exam banner, we need to consider ALL exams, not just the paginated ones
	if not exams:
		all_exams = get_user_exams(page=1, page_size=1000)["exams"]  # Get all exams
	else:
		all_exams = exams
		
	if not all_exams:
		return None
	
	# Group exams by status
	started_exams = [exam for exam in all_exams if exam["submission_status"] == "Started"]
	ongoing_exams = [exam for exam in all_exams if "Ongoing" in exam["schedule_status"] and exam["submission_status"] == "Registered"]
	upcoming_exams = [exam for exam in all_exams if exam["schedule_status"] == "Upcoming"]
	
	# Return started exam first if available
	if started_exams:
		return started_exams[0]
	
	if ongoing_exams:
		# Sort ongoing exams by start time and return the first one
		return sorted(ongoing_exams, key=lambda x: x["start_time"])[0]
	
	# Otherwise return the next upcoming exam (closest to current time)
	if upcoming_exams:
		# Sort by start_time
		return sorted(upcoming_exams, key=lambda x: x["start_time"])[0]
	
	return None

def get_time_until(target_datetime_str):
	"""Calculate time difference between now and target datetime."""
	target_datetime = datetime.fromisoformat(target_datetime_str)
	now_datetime = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
	diff = target_datetime - now_datetime
	
	days = diff.days
	hours, remainder = divmod(diff.seconds, 3600)
	minutes, seconds = divmod(remainder, 60)
	
	if days > 0:
		return f"{days} days, {hours} hours"
	elif hours > 0:
		return f"{hours} hours, {minutes} minutes"
	else:
		return f"{minutes} minutes"

def get_context(context):
	"""
	Check if there is any started exam for the user,
	If so redirect to it. Otherwise show exam list with upcoming exam banner.
	"""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	submit_candidate_pending_exams()
	context.no_cache = 1
	
	# Get page number from query parameters, default to 1
	page = int(frappe.form_dict.get('page', 1))
	page_size = 10
	
	# Get paginated exams
	exams_data = get_user_exams(page=page, page_size=page_size)
	context.exams = exams = exams_data["exams"]
	context.pagination = exams_data["pagination"]
	
	# Get next exam information for banner
	context.next_exam = next_exam = get_next_exam(exams)
	if next_exam:
		if next_exam["submission_status"] == "Started":
			context.next_exam_message = "You have an exam in progress. Continue where you left off."
			context.next_exam_link = "/exam"
			context.next_exam_link_text = "Continue Exam"
		elif next_exam["schedule_type"] == "Fixed" and next_exam["schedule_status"] == "Upcoming":
			time_until = get_time_until(next_exam["start_time"])
			context.next_exam_message = "Your next exam '{}' is scheduled to start in {}.".format(next_exam["exam_name"], time_until)
			context.next_exam_link = "/exam"
			context.next_exam_link_text = "View Details"
		elif next_exam["schedule_type"] == "Flexible":
			context.next_exam_message = "Your flexible schedule exam '{}' is available. {}".format(
				next_exam["exam_title"], 
				next_exam["schedule_status"]
			)
			context.next_exam_link = "/exam"
			context.next_exam_link_text = "Start Exam"
	
	context.metatags = {
		"title": "My Exams",
		"description": "View your upcoming and past exams"
	}

@frappe.whitelist()
def download_certificate(certificate_name):
	"""Download certificate PDF"""
	# Check if user has access to this certificate
	cert_doc = frappe.get_doc("Exam Certificate", certificate_name)
	
	if cert_doc.candidate != frappe.session.user:
		frappe.throw("You don't have permission to download this certificate")
	
	# Generate PDF using the certificate's generate_pdf method
	try:
		pdf_bytes = cert_doc.generate_pdf()
		
		# Return base64 encoded PDF for JavaScript download
		import base64
		pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
		return pdf_base64
		
	except Exception as e:
		frappe.throw(f"Error generating certificate PDF: {str(e)}")
