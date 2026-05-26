# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import random
import base64
import os
import requests
import secrets
import time
import uuid
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now
from werkzeug.utils import secure_filename

from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_status
from exampro.exam_pro.api.examops import evaluation_values
from exampro.exam_pro.api.utils import calculate_attention_score

import boto3
from botocore.client import Config

# Max size of a single video chunk uploaded by the browser. The proctor recorder
# emits ~10s webm chunks; 10 MB is a generous safety cap.
MAX_VIDEO_CHUNK_BYTES = 10 * 1024 * 1024
# Presigned POST lifetime (seconds). Short — minted every chunk.
VIDEO_UPLOAD_URL_TTL = 60
# Minimum gap (seconds) between URL mints per submission. Recorder cadence is 10s.
VIDEO_UPLOAD_URL_MIN_INTERVAL = 5

# Process-wide boto3 client cache. boto3 clients are thread-safe; reusing them
# across requests avoids the per-request handshake cost that previously
# bottlenecked the upload path.
_S3_CLIENT_CACHE = {}


def get_s3_client():
    """
    Return a process-cached boto3 S3 client.

    Cached by (endpoint, access key, bucket) so credential rotation in Exam
    Settings produces a fresh client without a restart.
    """
    try:
        settings = frappe.get_single("Exam Settings")
        cfdomain = settings.get_storage_endpoint()
        if not cfdomain:
            frappe.throw(_("Storage endpoint is not configured. Please check Exam Settings."))

        secret = settings.get_password("aws_secret")
        if not settings.aws_key or not secret:
            frappe.throw(_("AWS credentials are not configured. Please check Exam Settings."))

        cache_key = (cfdomain, settings.aws_key, settings.s3_bucket)
        client = _S3_CLIENT_CACHE.get(cache_key)
        if client is not None:
            return client

        client = boto3.client(
            's3',
            endpoint_url=cfdomain,
            aws_access_key_id=settings.aws_key,
            aws_secret_access_key=secret,
            config=Config(
                signature_version='s3v4',
                max_pool_connections=50,
                connect_timeout=5,
                read_timeout=60,
                retries={'max_attempts': 3},
                region_name='auto',
            ),
        )
        _S3_CLIENT_CACHE[cache_key] = client
        return client

    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(f"Failed to create S3 client: {str(e)}", "S3 Client Creation Error")
        frappe.throw(_("Unable to connect to video storage. Please check your storage configuration or contact administrator."))

# Cap for cached base64 payload size; oversize images bypass the cache so a
# single huge upload can't blow out Redis memory.
_IMAGE_B64_CACHE_MAX_BYTES = 2 * 1024 * 1024  # 2 MB encoded
# TTL for remote (http) images we don't control — re-fetch occasionally so a
# replaced image eventually propagates.
_IMAGE_B64_REMOTE_TTL = 6 * 60 * 60  # 6 hours


def _resolve_local_image_path(image_path):
    """Return the on-disk path for a Frappe file URL, or None if not local."""
    if image_path.startswith('/files/'):
        return frappe.get_site_path('public', image_path[1:])
    if image_path.startswith('/private/files/'):
        return frappe.get_site_path('private', image_path[9:])
    if image_path.startswith('file://') or not image_path.startswith('http'):
        local_path = image_path.replace('file://', '')
        if not os.path.isabs(local_path):
            local_path = frappe.get_site_path('public', 'files', local_path)
        return local_path
    return None


def convert_image_to_base64(image_path):
    """
    Return a base64 string for an image referenced by Frappe file URL, local
    path, or HTTP(S) URL.

    Cached in Redis. Cache key for local files includes mtime+size so the cache
    invalidates automatically when the underlying file is replaced; remote URLs
    cache for a fixed TTL.
    """
    if not image_path:
        return None

    # Already-encoded data URIs are returned as-is, no caching needed.
    if image_path.startswith('data:'):
        return image_path

    try:
        cache = frappe.cache()

        local_path = _resolve_local_image_path(image_path)
        if local_path is not None:
            try:
                st = os.stat(local_path)
            except FileNotFoundError:
                frappe.log_error(
                    f"Image file not found: {local_path} (original path: {image_path})",
                    "convert_image_to_base64",
                )
                return None

            cache_key = f"exampro:imgb64:local:{local_path}:{int(st.st_mtime)}:{st.st_size}"
            cached = cache.get_value(cache_key)
            if cached is not None:
                return cached

            with open(local_path, 'rb') as image_file:
                image_data = image_file.read()
            b64 = base64.b64encode(image_data).decode('utf-8')

            if len(b64) <= _IMAGE_B64_CACHE_MAX_BYTES:
                cache.set_value(cache_key, b64)
            return b64

        # Remote HTTP(S) URL
        cache_key = f"exampro:imgb64:remote:{image_path}"
        cached = cache.get_value(cache_key)
        if cached is not None:
            return cached

        response = requests.get(image_path, timeout=10)
        if response.status_code != 200:
            frappe.log_error(
                f"Failed to fetch image from URL: {image_path}, Status: {response.status_code}",
                "convert_image_to_base64",
            )
            return None

        b64 = base64.b64encode(response.content).decode('utf-8')
        if len(b64) <= _IMAGE_B64_CACHE_MAX_BYTES:
            cache.set_value(cache_key, b64, expires_in_sec=_IMAGE_B64_REMOTE_TTL)
        return b64

    except Exception as e:
        frappe.log_error(
            f"Error converting image to base64: {image_path}, Error: {str(e)}",
            "convert_image_to_base64",
        )
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

		# Only attempt to clean up S3 videos if the exam used video proctoring.
		if not frappe.db.get_value("Exam", self.exam, "enable_video_proctoring"):
			return

		try:
			settings = frappe.get_single("Exam Settings")
			s3_client = get_s3_client()

			paginator = s3_client.get_paginator('list_objects_v2')
			for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=self.name):
				if 'Contents' in page:
					objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
					if objects_to_delete:
						s3_client.delete_objects(
							Bucket=settings.s3_bucket,
							Delete={'Objects': objects_to_delete}
						)
		except Exception as e:
			frappe.log_error(
				message=f"Error deleting videos for exam submission {self.name}: {str(e)}",
				title="exam_submission_video_cleanup",
			)

	
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
			# Check if exam needs proctoring and evaluation before assigning
			exam_doc = frappe.get_doc("Exam", self.exam)
			needs_proctoring = getattr(exam_doc, 'needs_proctoring', True)
			needs_evaluation = exam_doc.question_type != "Choices"
			
			# Only assign if needed and not already assigned
			if (needs_proctoring and not self.assigned_proctor) or (needs_evaluation and not self.assigned_evaluator):
				self.assign_proctor_evaluator()

	def assign_proctor_evaluator(self):
		"""
		Assign a proctor and evaluator keeping round robin distribution
		Only assign if proctoring/evaluation is required
		"""
		sched = frappe.get_doc("Exam Schedule", self.exam_schedule)
		
		# Check if exam needs proctoring and evaluation
		exam_doc = frappe.get_doc("Exam", self.exam)
		needs_proctoring = getattr(exam_doc, 'needs_proctoring', True)  # Default to True if field doesn't exist
		needs_evaluation = exam_doc.question_type != "Choices"  # Non-choice questions need manual evaluation
		
		if not needs_proctoring and not needs_evaluation:
			return  # No assignment needed
		
		# Get current assignment counts from database dynamically
		current_counts = get_examiner_assignment_counts(self.exam_schedule)
		
		# Proctor assignment
		if needs_proctoring and not self.assigned_proctor:
			proctors = [ex.examiner for ex in sched.examiners if ex.can_proctor]
			if proctors:
				# Find proctor with least assignments
				next_proctor = min(proctors, key=lambda x: current_counts.get(x, {}).get('proctoring_count', 0))
				self.assigned_proctor = next_proctor

		# Evaluator assignment
		if needs_evaluation and not self.assigned_evaluator:
			evaluators = [ex.examiner for ex in sched.examiners if ex.can_evaluate]
			if evaluators:
				# Find evaluator with least assignments
				next_evaluator = min(evaluators, key=lambda x: current_counts.get(x, {}).get('evaluation_count', 0))
				self.assigned_evaluator = next_evaluator

	def before_insert(self):
		# Check if there are any existing submissions for the same candidate and schedule
		# that are NOT in ["Terminated", "Submitted"]
		existing_doctypes = frappe.get_all(
			"Exam Submission",
			filters={
				"candidate": self.candidate,
				"exam_schedule": self.exam_schedule,
				"status": ("not in", ["Terminated", "Submitted"])
			}
		)
		if existing_doctypes:
			frappe.throw("An active submission already exists for this candidate and schedule.")
			return


		if not self.short_uuid:
			self.short_uuid = generate_short_uuid()

		last_login = frappe.db.get_value("User", self.candidate, "last_login")
		if not last_login:
			self.new_user = 1
			self.reset_password_key = frappe.db.get_value("User", self.candidate, "reset_password_key")

		# Child Exam Answer rows are bulk-inserted in after_insert (see _bulk_insert_answers).
		# Leaving submitted_answers empty here means Frappe's standard child-row insert
		# loop is a no-op, so we skip ~N per-row INSERTs for an N-question exam.
		self.submitted_answers = []

	def after_insert(self):
		self._bulk_insert_answers()

	def _bulk_insert_answers(self):
		"""
		Create one Exam Answer row per question in a single INSERT.

		Replaces the per-row inserts that the framework would issue if these
		were appended to the child table before insert(). At 500 candidates ×
		60 questions, this collapses ~30k INSERTs into ~500.
		"""
		questions = frappe.get_all(
			"Exam Added Question",
			filters={"parent": self.exam},
			fields=["exam_question"],
			order_by="idx asc",
		)
		if not questions:
			return

		if frappe.get_cached_value("Exam", self.exam, "randomize_questions"):
			random.shuffle(questions)

		now_ts = frappe.utils.now()
		user = frappe.session.user or "Administrator"

		fields = [
			"name", "creation", "modified", "modified_by", "owner",
			"docstatus", "idx",
			"parent", "parentfield", "parenttype",
			"seq_no", "exam_question", "evaluation_status",
			"marked_for_later", "is_correct", "mark",
		]

		values = []
		for idx, qs in enumerate(questions):
			seq_no = idx + 1
			values.append((
				frappe.generate_hash(length=10),  # name
				now_ts, now_ts, user, user,
				0,            # docstatus
				seq_no,       # idx
				self.name, "submitted_answers", "Exam Submission",
				seq_no,
				qs["exam_question"],
				"Not Attempted",
				0,            # marked_for_later
				0,            # is_correct
				0.0,          # mark
			))

		frappe.db.bulk_insert("Exam Answer", fields=fields, values=values)

@frappe.whitelist()
def get_examiner_assignment_counts(exam_schedule):
	"""
	Get the current assignment counts for all examiners for a specific exam schedule.
	Args:
		exam_schedule (str): The exam schedule name		
	Returns:
		dict: Dictionary with examiner as key and counts as value
			  Format: {examiner_id: {'proctoring_count': int, 'evaluation_count': int}}
	"""
	# Get proctoring counts
	proctor_counts = frappe.db.sql("""
		SELECT assigned_proctor, COUNT(*) as count
		FROM `tabExam Submission`
		WHERE exam_schedule = %s 
		AND assigned_proctor IS NOT NULL 
		AND assigned_proctor != ''
		GROUP BY assigned_proctor
	""", (exam_schedule,), as_dict=True)
	
	# Get evaluation counts
	evaluator_counts = frappe.db.sql("""
		SELECT assigned_evaluator, COUNT(*) as count
		FROM `tabExam Submission`
		WHERE exam_schedule = %s 
		AND assigned_evaluator IS NOT NULL 
		AND assigned_evaluator != ''
		GROUP BY assigned_evaluator
	""", (exam_schedule,), as_dict=True)
	
	# Build the result dictionary
	result = {}
	
	# Add proctoring counts
	for row in proctor_counts:
		examiner = row['assigned_proctor']
		if examiner not in result:
			result[examiner] = {'proctoring_count': 0, 'evaluation_count': 0}
		result[examiner]['proctoring_count'] = row['count']
	
	# Add evaluation counts
	for row in evaluator_counts:
		examiner = row['assigned_evaluator']
		if examiner not in result:
			result[examiner] = {'proctoring_count': 0, 'evaluation_count': 0}
		result[examiner]['evaluation_count'] = row['count']
	
	return result

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


def _validate_submission_writable(exam_submission, candidate, status, member=None):
	"""
	Lighter version of can_process_question that operates on raw fields, so
	the hot answer-submit path doesn't have to load the full Exam Submission
	doc (which pulls all child Exam Answer rows).

	If the exam window has elapsed, the submission is flipped to Submitted via
	frappe.db.set_value — skipping before_save is safe here because the
	candidate/role/examiner assignment hooks have already run on start_exam.
	"""
	if status == "Submitted":
		frappe.throw("Exam submitted!")
	elif status == "Terminated":
		frappe.throw("Exam is terminated.")
	elif status != "Started":
		frappe.throw("Exam is not started yet.")
	else:
		exam_ended, end_time = has_submission_ended(exam_submission)
		if exam_ended:
			frappe.db.set_value("Exam Submission", exam_submission, "status", "Submitted")
			frappe.db.commit()
			frappe.throw("This exam has ended at {}".format(end_time))

	if candidate != (member or frappe.session.user):
		frappe.throw("Invalid exam requested.")


# Minimum gap (seconds) between tracking-info flushes triggered from
# submit_question_response. Without this, every keystroke-driven answer
# save would run calculate_attention_score on the full retina log.
_TRACKING_INFO_MIN_INTERVAL = 30


def _maybe_save_tracking_info(exam_submission):
	"""Persist tracking metrics at most once per _TRACKING_INFO_MIN_INTERVAL.

	end_exam still calls save_tracking_info directly so the final state is
	always captured regardless of this throttle.
	"""
	cache_key = f"tracking_flush:{exam_submission}"
	if frappe.cache().get_value(cache_key):
		return False
	frappe.cache().set_value(
		cache_key, 1, expires_in_sec=_TRACKING_INFO_MIN_INTERVAL
	)
	return save_tracking_info(exam_submission)

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

	help_show = question_doc.help_show or "Do not show"
	help_quiz = []
	if help_show != "Do not show":
		help_quiz = [
			{
				"quiz_question": r.quiz_question,
				"choice_1": r.choice_1,
				"choice_2": r.choice_2,
				"choice_3": r.choice_3,
				"correct_choice": r.correct_choice,
			}
			for r in (question_doc.help_quiz or [])
		]

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
		"answer": answer_doc["answer"],
		# optional training help text
		"help_show": help_show,
		"help_minimum_reading_time": question_doc.help_minimum_reading_time or 0,
		"help_text": question_doc.help_text or "",
		"help_quiz": help_quiz,
	}

	return res


@frappe.whitelist()
def submit_question_response(exam_submission=None, qs_name=None, answer="", markdflater=0, qs_no=None):
	"""
	Submit response and add marks if applicable
	"""
	assert exam_submission, qs_name

	# Pull only the fields needed for validation. Avoids loading the parent
	# Exam Submission doc with all its child Exam Answer rows on every save.
	sub = frappe.db.get_value(
		"Exam Submission",
		exam_submission,
		["candidate", "status"],
		as_dict=True,
	)
	if not sub:
		raise PermissionError("Invalid submission.")
	if frappe.session.user != sub.candidate:
		raise PermissionError("You don't have access to submit and answer.")

	_validate_submission_writable(exam_submission, sub.candidate, sub.status)
	_maybe_save_tracking_info(exam_submission)

	# A question can be added to an exam at multiple positions, so the same
	# exam_question may map to multiple Exam Answer rows. Disambiguate by seq_no.
	answer_filters = {"parent": exam_submission, "exam_question": qs_name}
	if qs_no:
		answer_filters["seq_no"] = int(qs_no)
	answer_docname = frappe.db.get_value("Exam Answer", answer_filters, "name")
	if not answer_docname:
		frappe.throw("Invalid question requested.")

	result_doc = frappe.get_doc("Exam Answer", answer_docname)
	result_doc.answer = answer
	result_doc.marked_for_later = markdflater
	result_doc.evaluation_status = "Pending"
	result_doc.save(ignore_permissions=True)

	return {
		"qs_name": qs_name,
		"qs_no": result_doc.seq_no,
		# 0/1 for Choices (set by ExamAnswer.before_save), None for User Input
		"is_correct": result_doc.is_correct,
	}


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

	# Terminate when no face has been visible for the full grace period (camera covered/shutter closed)
	elif warning_type == "nofacetimeout":
		doc.reload()
		if doc.status not in ("Terminated", "Submitted"):
			doc.status = "Terminated"
			doc.save(ignore_permissions=True)
			frappe.db.commit()

			terminate_msg = frappe.get_doc({
				"doctype": "Exam Messages",
				"exam_submission": exam_submission,
				"timestamp": frappe.utils.now(),
				"from": "System",
				"from_user": "Administrator",
				"message": "Exam terminated because no face was visible to the camera for 60 seconds.",
				"type_of_message": "Critical",
				"warning_type": "nofacetimeout"
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

	# Restrict to the candidate (or assigned proctor for live monitoring)
	candidate, assigned_proctor = frappe.db.get_value(
		"Exam Submission", exam_submission, ["candidate", "assigned_proctor"]
	) or (None, None)
	if frappe.session.user not in [candidate, assigned_proctor]:
		raise PermissionError("You don't have access to view this exam overview.")

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
	try:
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
	except Exception as e:
		# Log the specific error for debugging
		frappe.log_error(f"S3 connection error in get_videos for {exam_submission}: {str(e)}", "S3 Connection Error")
		
		# Check for common botocore/S3 connection issues
		error_msg = str(e).lower()
		if any(keyword in error_msg for keyword in ['connection', 'timeout', 'network', 'botocore', 'endpoint']):
			frappe.logger().warning(f"S3 connectivity issue for exam_submission {exam_submission}: {str(e)}")
		
		# Return empty videos dict instead of crashing
		return {"videos": {}}

@frappe.whitelist()
def exam_video_list(exam_submission):
	"""
	Get the list of videos from s3
	"""
	assert exam_submission
	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please login to access this page."))

	exam = frappe.db.get_value("Exam Submission", exam_submission, "exam")
	if not frappe.db.get_value("Exam", exam, "enable_video_proctoring"):
		return {"videos": {}}

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
	if not frappe.get_cached_value("Exam", exam, "enable_video_proctoring"):
		return {"videos": {}}

	ttl = frappe.get_cached_value("Exam", exam, "duration") * 60 + 900  # ttl is exam duration + 15 min buffer

	try:
		res = get_videos(exam_submission, ttl)
	except Exception as e:
		frappe.log_error(f"Error retrieving videos for exam submission {exam_submission}: {str(e)}", "proctor_video_list error")
		# Return empty video list instead of failing
		res = {"videos": {}}
		
		# Check if it's a botocore connection error specifically
		if "botocore" in str(type(e).__module__) and ("connection" in str(e).lower() or "timeout" in str(e).lower()):
			frappe.msgprint(_("Unable to connect to video storage. Videos may be temporarily unavailable."), 
							title=_("Storage Connection Error"), indicator="orange")

	return res

def _assert_can_upload_video(exam_submission):
	"""
	Authorize the current session to record a proctoring chunk for this submission.
	Returns the submission row (dict) on success; raises otherwise.

	All checks are performed against the database, not client-supplied data,
	so a tampered browser cannot bypass them by sending fake fields.
	"""
	if not exam_submission:
		raise frappe.PermissionError(_("Submission is required."))
	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please login to access this page."))

	sub = frappe.db.get_value(
		"Exam Submission",
		exam_submission,
		["candidate", "status", "exam"],
		as_dict=True,
	)
	if not sub:
		raise frappe.PermissionError(_("Invalid exam submission."))
	if sub.candidate != frappe.session.user:
		raise frappe.PermissionError(_("Exam does not belong to the user."))
	if sub.status != "Started":
		raise frappe.PermissionError(_("Exam is not active."))
	if not frappe.get_cached_value("Exam", sub.exam, "enable_video_proctoring"):
		raise frappe.PermissionError(_("Video proctoring is not enabled for this exam."))

	ended, _end_time = has_submission_ended(exam_submission)
	if ended:
		raise frappe.PermissionError(_("Exam has ended."))

	return sub


@frappe.whitelist()
def get_video_upload_url(exam_submission=None):
	"""
	Mint a short-lived, single-key presigned POST so the browser can upload one
	proctoring chunk directly to S3/R2, bypassing the Frappe request path.

	Tamper-proofing:
	- Auth/state checks against DB on every mint.
	- The S3 key is server-generated (submission prefix + ms timestamp + random
	  suffix). The candidate cannot choose it, predict future keys, or
	  overwrite past keys.
	- Policy pins the exact key, mime type and a content-length range, so even
	  if the URL leaks, it can only upload one webm of bounded size to that
	  one key.
	- Per-submission rate limit prevents URL-mint flooding.
	- 60s TTL.
	"""
	_assert_can_upload_video(exam_submission)

	cache = frappe.cache()
	rate_key = f"video_upload_url_mint:{exam_submission}"
	last = cache.get_value(rate_key)
	now_ts = time.time()
	if last is not None:
		try:
			elapsed = now_ts - float(last)
		except (TypeError, ValueError):
			elapsed = VIDEO_UPLOAD_URL_MIN_INTERVAL
		if elapsed < VIDEO_UPLOAD_URL_MIN_INTERVAL:
			frappe.throw(
				_("Upload URL requested too frequently."),
				frappe.TooManyRequestsError,
			)
	cache.set_value(rate_key, now_ts, expires_in_sec=60)

	settings = frappe.get_single("Exam Settings")
	bucket = settings.s3_bucket
	if not bucket:
		frappe.throw(_("Storage bucket is not configured."))

	# Server-controlled key. Random suffix makes it unguessable, so previous
	# chunks cannot be overwritten by replaying a stale URL request.
	key = "{sub}/{ts}-{rand}.webm".format(
		sub=exam_submission,
		ts=int(now_ts * 1000),
		rand=secrets.token_hex(4),
	)

	s3_client = get_s3_client()
	try:
		presigned = s3_client.generate_presigned_post(
			Bucket=bucket,
			Key=key,
			Fields={"Content-Type": "video/webm"},
			Conditions=[
				{"bucket": bucket},
				{"key": key},
				{"Content-Type": "video/webm"},
				["content-length-range", 1, MAX_VIDEO_CHUNK_BYTES],
			],
			ExpiresIn=VIDEO_UPLOAD_URL_TTL,
		)
	except Exception as e:
		frappe.log_error(
			f"Failed to mint presigned POST for {exam_submission}: {e}",
			"Video upload URL error",
		)
		frappe.throw(_("Unable to prepare video upload. Please retry."))

	return {
		"url": presigned["url"],
		"fields": presigned["fields"],
		"key": key,
		"max_bytes": MAX_VIDEO_CHUNK_BYTES,
		"expires_in": VIDEO_UPLOAD_URL_TTL,
	}

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

	# Only the candidate may post tracking data for their own submission
	candidate = frappe.db.get_value("Exam Submission", exam_submission, "candidate")
	if not candidate or frappe.session.user != candidate:
		raise PermissionError("You don't have access to post tracking data for this exam.")

	# Extract only the required tracking values
	face_count_changes = info.get("faceCountChanges", 0)
	total_away_time = info.get("totalAwayTime", 0)
	total_distracted_time = info.get("totalDistractedTime", 0)
	retina_locations = info.get("retinaLocations", [])

	# Get cache key for this exam submission
	cache_key = f"tracking_data:{exam_submission}"

	# Get existing cache data or initialize with zeros
	existing_data = frappe.cache().get_value(cache_key) or {
		"face_count_changes": 0,
		"total_away_time": 0.0,
		"total_distracted_time": 0.0,
		"retina_locations": []
	}
	
	# Add new tracking data to existing data
	existing_data["face_count_changes"] += face_count_changes
	existing_data["total_away_time"] += total_away_time
	existing_data["total_distracted_time"] += total_distracted_time
	existing_data["retina_locations"].extend(retina_locations)
	
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
	print("#"*100)
	print("Cached Data:", cached_data)
	if not cached_data:
		return False

	# Get existing retina location log from database
	existing_retina_log = frappe.db.get_value("Exam Submission", exam_submission, "retina_location_log")
	
	# Parse existing log or initialize empty list
	if existing_retina_log:
		try:
			retina_locations = frappe.parse_json(existing_retina_log) if isinstance(existing_retina_log, str) else existing_retina_log
			if not isinstance(retina_locations, list):
				retina_locations = []
		except Exception:
			retina_locations = []
	else:
		retina_locations = []
	
	# Add new retina locations from cache
	if cached_data.get("retina_locations"):
		retina_locations.extend(cached_data["retina_locations"])

	# Update the exam submission document directly using frappe.db.set_value
	update_data = {
		"face_count_changes": cached_data.get("face_count_changes", 0),
		"total_away_time": cached_data.get("total_away_time", 0.0),
		"total_distracted_time": cached_data.get("total_distracted_time", 0.0),
		"retina_location_log": frappe.as_json(retina_locations)
	}
	
	print("#"*100)
	print("Update Data:", update_data)
	print("Retina Locations Count:", len(retina_locations))
	
	frappe.db.set_value("Exam Submission", exam_submission, update_data)
	
	frappe.db.commit()
	calculate_attention_score(exam_submission)

	return True