# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import random
import base64
import os
import requests
import uuid
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now
from werkzeug.utils import secure_filename

from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_status
from exampro.exam_pro.api.examops import evaluation_values

import boto3
from botocore.client import Config

def get_s3_client():
    """
    Get or create an S3 client from the connection pool.
    Stores the client in frappe.local for reuse within the same request.
    
    Returns:
        boto3.client: S3 client with appropriate configuration
    """
    # Check if we already have a client in the current request
    if hasattr(frappe.local, "s3_client"):
        return frappe.local.s3_client
        
    # Get settings
    settings = frappe.get_single("Exam Settings")
    cfdomain = settings.get_storage_endpoint()
    if not cfdomain:
        frappe.throw(_("Storage endpoint is not configured. Please check Exam Settings."))
        
    # Create a new client
    s3_client = boto3.client(
        's3',
        endpoint_url=cfdomain,
        aws_access_key_id=settings.aws_key,
        aws_secret_access_key=settings.get_password("aws_secret"),
        config=Config(
            signature_version='s3v4',
            # Add connection pooling settings
            max_pool_connections=50,  # Reuse connections
            connect_timeout=5,        # Connection timeout
            read_timeout=60           # Read timeout for uploads
        )
    )
    
    # Store in frappe.local for this request
    frappe.local.s3_client = s3_client
    
    return s3_client

def convert_image_to_base64(image_path):
    """
    Convert image file to base64 string.
    Handles both local file paths, URLs, and Frappe file paths.
    
    Args:
        image_path (str): Path to image file, URL, or Frappe file path
        
    Returns:
        str: Base64 encoded image string or None if conversion fails
    """
    if not image_path:
        return None
        
    try:
        # Check if it's already base64
        if image_path.startswith('data:'):
            return image_path
            
        # Handle Frappe file paths (/files/ and /private/files/)
        if image_path.startswith('/files/') or image_path.startswith('/private/files/'):
            # Remove leading slash and convert to site-relative path
            if image_path.startswith('/files/'):
                # Public files are in public/files/
                local_path = frappe.get_site_path('public', image_path[1:])  # Remove leading slash
            elif image_path.startswith('/private/files/'):
                # Private files are in private/files/
                local_path = frappe.get_site_path('private', image_path[9:])  # Remove '/private/' prefix
            
            # Check if file exists
            if os.path.exists(local_path):
                with open(local_path, 'rb') as image_file:
                    image_data = image_file.read()
                    base64_string = base64.b64encode(image_data).decode('utf-8')
                    return base64_string
            else:
                frappe.log_error(f"Frappe file not found: {local_path} (original path: {image_path})", "convert_image_to_base64")
                return None
        
        # Handle file:// URLs or local paths
        elif image_path.startswith('file://') or not image_path.startswith('http'):
            # Remove file:// prefix if present
            local_path = image_path.replace('file://', '')
            
            # If it's a relative path, make it absolute relative to frappe site public/files
            if not os.path.isabs(local_path):
                local_path = frappe.get_site_path('public', 'files', local_path)
            
            # Check if file exists
            if os.path.exists(local_path):
                with open(local_path, 'rb') as image_file:
                    image_data = image_file.read()
                    base64_string = base64.b64encode(image_data).decode('utf-8')
                    return base64_string
            else:
                frappe.log_error(f"Image file not found: {local_path}", "convert_image_to_base64")
                return None
                
        # Handle HTTP/HTTPS URLs
        elif image_path.startswith('http'):
            response = requests.get(image_path, timeout=10)
            if response.status_code == 200:
                image_data = response.content
                base64_string = base64.b64encode(image_data).decode('utf-8')
                return base64_string
            else:
                frappe.log_error(f"Failed to fetch image from URL: {image_path}, Status: {response.status_code}", "convert_image_to_base64")
                return None
                
    except Exception as e:
        frappe.log_error(f"Error converting image to base64: {image_path}, Error: {str(e)}", "convert_image_to_base64")
        return None
        
    return None

def create_website_user(full_name, email):
    # Check if the user already exists
    if frappe.db.exists("User", email):
        return email

    # Split full name into first name and last name
    name_parts = full_name.split()
    first_name = name_parts[0]
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
    
    # Create a new user
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
		"full_name": full_name,
        "enabled": 1,
        "user_type": "Website User",
		"send_welcome_email": 0
    })
    
    # Save the user
    user.insert(ignore_permissions=True)
    return email


def generate_short_uuid():
	"""Generate a short UUID (8 characters)"""
	return str(uuid.uuid4()).replace('-', '')[:8]

class ExamSubmission(Document):

	def can_start_exam(self):
		scheduled_start = frappe.get_cached_value(
		"Exam Schedule", self.exam_schedule, "start_date_time"
		)
		if self.exam_started_time:
			frappe.throw("Exam already started at {}".format(self.exam_started_time))

		start_time = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
		if start_time < scheduled_start:
			frappe.throw("This exam can be started only after {}".format(scheduled_start))

		return start_time
	
	def on_trash(self):
		frappe.db.delete("Exam Messages", {"exam_submission": self.name})
		frappe.db.delete("Exam Certificate", {"exam_submission": self.name})
		
		# Delete uploaded videos from S3
		try:
			settings = frappe.get_single("Exam Settings")
			s3_client = get_s3_client()
			
			# List all objects with the exam submission prefix
			paginator = s3_client.get_paginator('list_objects_v2')
			for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=self.name):
				if 'Contents' in page:
					# Delete objects in batches
					objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
					if objects_to_delete:
						s3_client.delete_objects(
							Bucket=settings.s3_bucket,
							Delete={'Objects': objects_to_delete}
						)
		except Exception as e:
			frappe.log_error(f"Error deleting videos for exam submission {self.name}: {str(e)}", "exam_submission_video_cleanup")

	
	def before_save(self):
		# if frappe.db.exists(
		# 	"Exam Submission",
		# 	{"candidate": self.candidate, "exam_schedule": self.exam_schedule}
		# ):
		# 	frappe.throw("Duplicate submission exists for {} - {}".format(self.candidate, self.exam_schedule))

		# If this is a new submission, make sure the candidate has the Exam Candidate role
		if self.candidate:
			user = frappe.get_doc("User", self.candidate)
			roles = [ro.role for ro in user.roles]
			if "Exam Candidate" not in roles:
				user.add_roles("Exam Candidate")
				user.save(ignore_permissions=True)

		sched = frappe.get_doc("Exam Schedule", self.exam_schedule)
		if sched.examiners:
			if not self.assigned_proctor or not self.assigned_evaluator:
				self.assign_proctor_evaluator()

	def assign_proctor_evaluator(self):
		"""
		Assign a proctor keeping round robin
		"""
		sched = frappe.get_doc("Exam Schedule", self.exam_schedule)
		# proctor
		pcount = {
			ex.examiner: ex.proctoring_count for ex in sched.examiners if ex.can_proctor
		}
		if pcount:
			# Determine the examiner with the least number of assignments
			next_proctor = min(pcount, key=pcount.get)
			self.assigned_proctor = next_proctor
			pcount[next_proctor] += 1

		# examiner asignement
		ecount = {
			ex.examiner: ex.evaluation_count for ex in sched.examiners if ex.can_evaluate
		}
		if ecount:
			# Determine the examiner with the least number of assignments
			next_evaluator = min(ecount, key=pcount.get)
			self.assigned_evaluator = next_evaluator
			ecount[next_evaluator] += 1
		
		# set the updated counts
		for ex_ in sched.examiners:
			ex_.proctoring_count = pcount[ex_.examiner]
			ex_.evaluation_count = ecount[ex_.examiner]
		sched.save(ignore_permissions=True)
	
	def before_insert(self):
		if not self.short_uuid:
			self.short_uuid = generate_short_uuid()
			
		last_login = frappe.db.get_value("User", self.candidate, "last_login")
		if not last_login:
			self.new_user = 1
			self.reset_password_key = frappe.db.get_value("User", self.candidate, "reset_password_key")

		# get questions
		questions = frappe.get_all(
			"Exam Added Question", filters={"parent": self.exam}, fields=["exam_question"]
		)
		random_questions = frappe.get_cached_value("Exam", self.exam, "randomize_questions")
		if random_questions:
			random.shuffle(questions)

		self.submitted_answers = []
		for idx, qs in enumerate(questions):
			seq_no = idx + 1
			qs_ = {
					"seq_no": seq_no,
					"exam_question": qs["exam_question"],
					"evaluation_status": "Not Attempted"
			}
			self.append('submitted_answers', qs_)

def can_process_question(doc, member=None):
	"""
	validatior function to run before getting or updating a question
	"""
	if doc.status == "Submitted":
		frappe.throw("Exam submitted!")
	elif doc.status == "Started":
		# check if the exam is ended, if so, submit the exam
		exam_ended, end_time = has_submission_ended(doc.name)
		if exam_ended:
			doc.status = "Submitted"
			doc.save(ignore_permissions=True)
			frappe.throw("This exam has ended at {}".format(end_time))
	elif doc.status == "Terminated":
		frappe.throw("Exam is terminated.")
	else:
		frappe.throw("Exam is not started yet.")
	if doc.candidate != (member or frappe.session.user):
		frappe.throw("Invalid exam requested.")

def get_submitted_questions(exam_submission, fields=["exam_question"]):
	all_submitted = frappe.db.get_all(
		"Exam Answer",
		filters={"parent": exam_submission, "evaluation_status": ("!=", "Not Attempted")},
		fields=fields,
		order_by="seq_no asc"
	)

	return all_submitted

def get_current_qs(exam_submission):
	"""
	Current qs: last qs attempted
	Next qs: next valid qs
	"""
	all_attempted = frappe.db.get_all(
		"Exam Answer",
		filters={"parent": exam_submission, "evaluation_status": ("!=", "Not Attempted")},
		fields=["exam_question", "seq_no"],
		order_by="seq_no asc"
	)
	if all_attempted:
		attempted_qs = all_attempted[-1]["exam_question"]
		qs_no = all_attempted[-1]["seq_no"]
		
		return attempted_qs, qs_no
	else:
		return None, None
	

@frappe.whitelist()
def start_exam(exam_submission=None):
	"""
	start exam, Get questions and store in order
	Caching flow:
	> cache exam submission on exam_start
	> SUBMISSION TOTAL_QS, EXPIRY, QS:1, QS:2...
	> SUBMISSION:EXPIRY_TRACKER single key with cache expiry
	> check EXPIRY_TRACKER, if not there, validate with db
	"""
	assert exam_submission
	doc = frappe.get_doc("Exam Submission", exam_submission)
	if doc.status == "Started":
		return True

	if frappe.session.user != doc.candidate:
		raise PermissionError("Incorrect exam for the user.")

	start_time = doc.can_start_exam()
	doc.exam_started_time = start_time

	doc.status = "Started"
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	schedule = frappe.get_doc("Exam Schedule", doc.exam_schedule)

	# end time is schedule start time + duration + additional time given
	end_time = schedule.start_date_time + timedelta(minutes=schedule.duration) + \
		timedelta(minutes=doc.additional_time_given)

	return {"end_time": end_time}


@frappe.whitelist()
def end_exam(exam_submission=None):
	"""
	Submit Candidate exam
	"""
	assert exam_submission
	doc = frappe.get_doc("Exam Submission", exam_submission)

	# check of the logged in user is same as exam submission candidate
	if frappe.session.user != doc.candidate:
		raise PermissionError("You don't have access to this exam.")
	
	if doc.status == "Started":
		save_tracking_info(doc.name)
		doc.reload()

		doc.status = "Submitted"
		total_marks, evaluation_status, result_status = evaluation_values(
			doc.exam, doc.submitted_answers
		)
		doc.exam_submitted_time = frappe.utils.now()
		doc.total_marks = total_marks
		doc.evaluation_status = evaluation_status
		doc.result_status = result_status
		doc.save(ignore_permissions=True)

		# delete frappe cache data
		cache_key = f"tracking_data:{doc.name}"
		frappe.cache().delete(cache_key)

		frappe.db.commit()

	# return result details
	exam = frappe.get_cached_value(
		"Exam", doc.exam,
		["show_result", "question_type"],
		as_dict=True
	)
	if exam["question_type"] == "Choices" \
		and exam["show_result"] == "After Exam Submission":
		return {"show_result": 1}
	
	return {"show_result": 0}

@frappe.whitelist()
def get_question(exam_submission=None, qsno=1):
	"""
	Single function to fetch a new question or a submitted one.
	> get qs from cache, if not there, get from db
	"""
	assert exam_submission
	qs_no = int(qsno)

	exam_schedule, exam = frappe.get_cached_value("Exam Submission", exam_submission, ["exam_schedule", "exam"])
	if get_schedule_status(exam_schedule) != "Ongoing":
		frappe.throw("Exam is not ongoing or has ended.")
	
	if frappe.db.get_value("Exam Submission", exam_submission, "status") != "Started":
		frappe.throw("Exam is not started yet.")
	exam_ended, _ = has_submission_ended(exam_submission)
	if exam_ended:
		frappe.throw("Exam has ended.")

	total_qs = frappe.get_cached_value(
		"Exam", exam, "total_questions"
	)
	if qs_no < 1 or qs_no > total_qs:
		frappe.throw("Invalid question number requested: {}".format(qs_no))

	answer_doc = frappe.db.get_value("Exam Answer", {"parent": exam_submission, "seq_no": qs_no}, "*")
	if not answer_doc:
		frappe.throw("Invalid question requested.")

	try:
		question_doc = frappe.get_cached_doc("Exam Question", answer_doc["exam_question"])
	except frappe.DoesNotExistError:
		frappe.throw("Invalid question requested.")

	res = {
		"question": question_doc.question,
		"qs_no": answer_doc["seq_no"],
		"name": question_doc.name,
		"type": question_doc.type,
		"description_image": convert_image_to_base64(question_doc.description_image),
		"option_1": question_doc.option_1,
		"option_2": question_doc.option_2,
		"option_3": question_doc.option_3,
		"option_4": question_doc.option_4,
		"option_1_image": convert_image_to_base64(question_doc.option_1_image),
		"option_2_image": convert_image_to_base64(question_doc.option_2_image),
		"option_3_image": convert_image_to_base64(question_doc.option_3_image),
		"option_4_image": convert_image_to_base64(question_doc.option_4_image),
		"multiple": question_doc.multiple,
		# submitted answer
		"marked_for_later": answer_doc["marked_for_later"],
		"answer": answer_doc["answer"]
	}

	return res


@frappe.whitelist()
def submit_question_response(exam_submission=None, qs_name=None, answer="", markdflater=0):
	"""
	Submit response and add marks if applicable
	"""
	assert exam_submission, qs_name

	submission = frappe.get_doc("Exam Submission", exam_submission, ignore_permissions=True)
	# check of the logged in user is same as exam submission candidate
	if frappe.session.user != submission.candidate:
		raise PermissionError("You don't have access to submit and answer.")

	can_process_question(submission)
	save_tracking_info(exam_submission)

	answer_docname = frappe.db.get_value("Exam Answer", {"parent": exam_submission, "exam_question": qs_name}, "name")
	if not answer_docname:
		frappe.throw("Invalid question requested.")

	result_doc = frappe.get_doc("Exam Answer", answer_docname)
	result_doc.answer = answer
	result_doc.marked_for_later = markdflater
	result_doc.evaluation_status = "Pending"
	result_doc.save(ignore_permissions=True)
		
	return {"qs_name": qs_name, "qs_no": result_doc.seq_no}


@frappe.whitelist()
def post_exam_message(exam_submission=None, message=None, type_of_message="General", warning_type="other"):
	"""
	Submit response and add marks if applicable
	"""
	assert exam_submission
	assert message

	doc = frappe.get_doc("Exam Submission", exam_submission)

	# check of the logged in user is same as exam submission candidate
	if frappe.session.user not in [doc.candidate, doc.assigned_proctor]:
		raise PermissionError("You don't have access to post messages.")

	type_of_user = "System"
	if frappe.session.user == doc.assigned_proctor:
		type_of_user = "Proctor"
	elif frappe.session.user == doc.candidate:
		type_of_user = "Candidate"

	tnow = frappe.utils.now()
	msg_doc = frappe.get_doc({
		"doctype": "Exam Messages",
		"exam_submission": exam_submission,
		"timestamp": tnow,
		"from": type_of_user,
		"from_user": frappe.session.user,
		"message": message,
		"type_of_message": type_of_message,
		"warning_type": warning_type
	})
	msg_doc.insert(ignore_permissions=True)

	# Check if the warning is for tab change and update the warning count
	if warning_type == "tabchange":
		# Count the number of tabchange warnings for this exam submission
		warning_count = frappe.db.count("Exam Messages", 
			filters={"exam_submission": exam_submission, "warning_type": "tabchange"})

		# Get the max_warning_count from Exam
		max_warning_count = frappe.get_value("Exam", doc.exam, "max_warning_count")

		# If warning count exceeds max_warning_count, terminate the exam
		if warning_count >= max_warning_count:
			doc.reload()
			doc.status = "Terminated"
			doc.save(ignore_permissions=True)
			frappe.db.commit()

			# Add a message for exam termination
			terminate_msg = frappe.get_doc({
				"doctype": "Exam Messages",
				"exam_submission": exam_submission,
				"timestamp": frappe.utils.now(),
				"from": "System",
				"from_user": "Administrator",
				"message": "Exam terminated due to excessive tab changes.",
				"type_of_message": "Critical",
				"warning_type": "other"
			})
			terminate_msg.insert(ignore_permissions=True)
	
	# Terminate exam immediately if warning_type is nowebcam
	elif warning_type == "nowebcam":
		doc.reload()
		doc.status = "Terminated"
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		# Add a message for exam termination
		terminate_msg = frappe.get_doc({
			"doctype": "Exam Messages",
			"exam_submission": exam_submission,
			"timestamp": frappe.utils.now(),
			"from": "System",
			"from_user": "Administrator",
			"message": "Exam terminated due to webcam disconnection.",
			"type_of_message": "Critical",
			"warning_type": "nowebcam"
		})
		terminate_msg.insert(ignore_permissions=True)

	return {"status": 1}

@frappe.whitelist()
def terminate_exam(exam_submission, check_permission=True):
	doc = frappe.get_doc("Exam Submission", exam_submission)
	# only proctor can terminate exam
	if check_permission:
		if frappe.session.user != doc.assigned_proctor:
			raise PermissionError("No permission to terminate this exam.")
	doc.status = "Terminated"
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	# add a message
	post_exam_message(
		exam_submission,
		message="Exam is terminated.",
		type_of_message="Critical"
	)

	return {"status": "Terminated"}



@frappe.whitelist()
def exam_messages(exam_submission=None):
	"""
	Get messages
	"""
	assert exam_submission
	doc = frappe.get_doc("Exam Submission", exam_submission, ignore_permissions=True)

	# check of the logged in user is same as exam submission candidate or proctor
	if frappe.session.user not in [doc.candidate, doc.assigned_proctor]:
		raise PermissionError("You don't have access to view messages.")

	res = frappe.get_all(
		"Exam Messages", filters={
		"exam_submission": exam_submission
		}, fields=["creation", "from", "message", "type_of_message"],
		ignore_permissions=True
	)
	for idx, msg in enumerate(res):
		res[idx]["creation"] = res[idx]["creation"].isoformat()

	# sort by datetime
	res = sorted(res, key=lambda x: x['creation'])

	return {"messages": res}


@frappe.whitelist()
def exam_overview(exam_submission=None):
	"""
	return list of questions and its status
	"""
	assert exam_submission
	all_submitted = get_submitted_questions(
		exam_submission, fields=["marked_for_later", "exam_question", "answer", "seq_no"]
	)
	exam_schedule = frappe.get_cached_value(
		"Exam Submission", exam_submission, "exam_schedule"
	)
	exam = frappe.get_cached_value("Exam Schedule", exam_schedule, "exam")
	total_questions = frappe.get_cached_value("Exam", exam, "total_questions")
	res = {
		"exam_submission": exam_submission,
		"submitted": {},
		"total_questions": total_questions,
		"total_answered": 0,
		"total_marked_for_later": 0,
		"total_not_attempted": 0
	}

	for idx, resitem in enumerate(all_submitted):
		res["submitted"][resitem["seq_no"]] = {
			"name": resitem["exam_question"],
			"marked_for_later": resitem["marked_for_later"],
			"answer": resitem["answer"]
			}
		if resitem["marked_for_later"]:
			res["total_marked_for_later"] += 1
		else:
			res["total_answered"] += 1

	# find total non-attempted
	res["total_not_attempted"] = res["total_questions"] - \
		res["total_answered"] - res["total_marked_for_later"]

	return res

def get_videos(exam_submission, ttl=None):
	"""
	Get list of videos. Optional cache the urls with ttl
	"""
	settings = frappe.get_single("Exam Settings")
	s3_client = get_s3_client()
	res = {"videos": {}}

	# Paginator to handle buckets with many objects
	paginator = s3_client.get_paginator('list_objects_v2')
	for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=exam_submission):
		if 'Contents' in page:
			for obj in page['Contents']:
				if not obj['Key'].endswith('.webm'):
					continue

				# check cache for presigned url
				filetimestamp = obj['Key'].split("/")[-1][:-4]
				cached_url = frappe.cache().get(obj['Key'])
				if not cached_url:
					presigned_url = s3_client.generate_presigned_url(
						'get_object', Params={
							'Bucket': settings.s3_bucket,
							'Key': obj['Key']},
							ExpiresIn=ttl
					)
					res["videos"][filetimestamp] = presigned_url
					if ttl:
						frappe.cache().setex(obj['Key'], ttl, presigned_url)
				else:
					res["videos"][filetimestamp] = cached_url.decode()
	return res

@frappe.whitelist()
def exam_video_list(exam_submission):
	"""
	Get the list of videos from s3
	"""
	assert exam_submission
	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please login to access this page."))

	try:
		res = get_videos(exam_submission)
	except Exception:
		frappe.log_error("Error retrieving videos for exam submission", "exam_video_list error")
		res = {"videos": {}}
	
	return res

#########################
### Examiner APIs ########
#########################
@frappe.whitelist()
def proctor_video_list(exam_submission=None):
	"""
	Get the list of videos from s3
	TODO Add a caching layer to stop generating duplicate urls
	"""
	assert exam_submission
	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please login to access this page."))

	assigned_proctor = frappe.get_cached_value(
		"Exam Submission", exam_submission, "assigned_proctor"
	)
	# make sure that logged in user is valid proctor
	if frappe.session.user != assigned_proctor:
		raise frappe.PermissionError(_("No permission to access this exam."))

	exam = frappe.get_cached_value(
		"Exam Submission", exam_submission, "exam"
	)
	ttl = frappe.get_cached_value("Exam", exam, "duration") * 60 + 900  # ttl is exam duration + 15 min buffer
	res = get_videos(exam_submission, ttl)

	return res

@frappe.whitelist()
def upload_video(exam_submission=None):
	"""
	Upload video to S3 storage and notify proctor
	Uses connection pooling for better performance with multiple uploads
	"""
	assert exam_submission
	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please login to access this page."))

	if frappe.db.get_value("Exam Submission", exam_submission, "status") != "Started":
		raise frappe.PermissionError(_("Exam is invalid/ended."))
	# check if the exam is of logged in user
	if frappe.session.user != \
		frappe.get_cached_value("Exam Submission", exam_submission, "candidate"):
		raise frappe.PermissionError(_("Exam does not belongs to the user."))
	
	settings = frappe.get_single("Exam Settings")
	s3_client = get_s3_client()
	
	if 'file' not in frappe.request.files:
		return {"status": False}

	file = frappe.request.files['file']
	if file.filename == '':
		return {"status": False}

	# Secure the filename
	filename = secure_filename(file.filename)

	# Specify your S3 bucket and folder
	bucket_name = settings.s3_bucket
	object_name = "{}/{}".format(exam_submission, filename)
	exam = frappe.get_cached_value(
		"Exam Submission", exam_submission, "exam"
	)
	duration = frappe.get_cached_value("Exam", exam, "duration")
	ttl = duration * 60 + 900  # ttl is exam duration + 15 min buffer

	try:
		# Stream the file directly to S3
		s3_client.upload_fileobj(file, bucket_name, object_name)
	except Exception:
		# return str(e), 500
		return {"status": False}
	else:
		presigned_url = s3_client.generate_presigned_url(
			'get_object', Params={
				'Bucket': settings.s3_bucket,
				'Key': object_name},
				ExpiresIn=ttl,
				HttpMethod='GET'
			)
		frappe.cache().setex(object_name, ttl, presigned_url)

		# trigger webocket msg to proctor
		# frappe.publish_realtime(
		# 	event='newproctorvideo',
		# 	message={
		# 		"exam_submission": exam_submission,
		# 		"ts": filename[:-5],
		# 		"url": presigned_url
		# 	},
		# 	user=frappe.cache().hget(exam_submission, "assigned_proctor")
		# )
		return {"status": True}

def val_secs(securities):
	for row in securities:
		print(row["qty"], row["isin"])
	return {"done": 1}

@frappe.whitelist()
def ping(securities):
	return val_secs(securities)


# def send_registration_email(uname, uemail, exam_name, sched_time, duration):
# 		context = {
# 			"exam": exam_name,
# 			"scheduled_time": self.start_date_time
# 		}
# 		# Retrieve the email template document
# 		email_template = frappe.get_doc("Email Template", "Exam Proctor Assignment")

# 		# Render the subject and message
# 		subject = frappe.render_template(email_template.subject, context)
# 		message = frappe.render_template(email_template.response, context)

# 		member_email = frappe.db.get_value("User", self.examiner, "email")
# 		frappe.sendmail(
# 			recipients=[user_email],
# 			subject=subject,
# 			message=message,
# 		)
# 		frappe.db.set_value("Examiner", examiner.name, "notification_sent", 1)


@frappe.whitelist()
def register_candidate(schedule='', user_email='', user_name=''):
	"""
	External API to register candidate
	Create the user if nit exists

	# TODO
	# validate email
	# assert schedule is valid, public, can register
	"""
	assert schedule, "Exam schedule is required."
	assert user_email, "User email is required."
	assert user_name, "User name is required."


	assert frappe.db.exists("Exam Schedule", schedule), "Invalid exam schedule."
	create_website_user(user_name, user_email)
	user = frappe.get_doc("User", user_email)
	roles = [ro.role for ro in user.roles]
	if "Exam Candidate" not in roles:
		user.add_roles("Exam Candidate")
		user.save(ignore_permissions=True)
		frappe.db.commit()

	if not frappe.db.exists({"doctype": "Exam Submission", "candidate": user_email, "exam_schedule": schedule}):
		new_submission = frappe.get_doc(
			{"doctype": "Exam Submission", "candidate": user_email, "exam_schedule": schedule}
		)
		new_submission.insert(ignore_permissions=True)
		frappe.db.commit()


def has_submission_ended(exam_submission):
	"""
	End time is schedule start time + duration + additional time given
	returns True, end_time if exam has ended
	"""
	schedule, additional_time_given = frappe.get_cached_value("Exam Submission", exam_submission, ["exam_schedule", "additional_time_given"])
	submission_status, sub_started_time = frappe.get_cached_value("Exam Submission", exam_submission, ["status", "exam_started_time"])
	scheduled_start, duration, schedule_type = frappe.get_cached_value(
	"Exam Schedule", schedule, ["start_date_time", "duration", "schedule_type"]
	)
	if submission_status != "Started":
		frappe.throw(_("Exam is not started yet."))

	if schedule_type == "Flexible":
		end_time = sub_started_time + timedelta(minutes=duration) + \
			timedelta(minutes=additional_time_given)
	else:
		end_time = scheduled_start + timedelta(minutes=duration) + \
			timedelta(minutes=additional_time_given)

	current_time = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')

	if current_time >= end_time:
		return True, end_time
	
	return False, end_time

@frappe.whitelist()
def post_tracking_info(info=None):
	"""
	Save tracking information for exam operations.
	"""
	assert info, "Tracking info is required"

	info = frappe.parse_json(info)
	exam_submission = info.get("exam_submission")
	if not exam_submission:
		return

	# Extract only the required tracking values
	face_count_changes = info.get("faceCountChanges", 0)
	total_away_time = info.get("totalAwayTime", 0)
	total_distracted_time = info.get("totalDistractedTime", 0)

	# Get cache key for this exam submission
	cache_key = f"tracking_data:{exam_submission}"

	# Get existing cache data or initialize with zeros
	existing_data = frappe.cache().get_value(cache_key) or {
		"face_count_changes": 0,
		"total_away_time": 0.0,
		"total_distracted_time": 0.0
	}
	
	# Add new tracking data to existing data
	existing_data["face_count_changes"] += face_count_changes
	existing_data["total_away_time"] += total_away_time
	existing_data["total_distracted_time"] += total_distracted_time
	
	# Store updated data back to cache
	frappe.cache().set_value(cache_key, existing_data)
	
	return {"status": "success", "cached_data": existing_data}


def save_tracking_info(exam_submission):
	"""
	Save accumulated tracking metrics from cache to exam submission doctype.
	"""
	# Get cache key for this exam submission
	cache_key = f"tracking_data:{exam_submission}"
	
	# Get cached tracking data
	cached_data = frappe.cache().get_value(cache_key)
	if not cached_data:
		return False

	# Update the exam submission document directly using frappe.db.set_value
	frappe.db.set_value("Exam Submission", exam_submission, {
		"face_count_changes": cached_data.get("face_count_changes", 0),
		"total_away_time": cached_data.get("total_away_time", 0.0),
		"total_distracted_time": cached_data.get("total_distracted_time", 0.0)
	})
	
	frappe.db.commit()
	
	return True