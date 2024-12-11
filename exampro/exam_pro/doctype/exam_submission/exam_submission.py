# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import random
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.file_manager import get_uploaded_content
from frappe.utils import now
from werkzeug.utils import secure_filename

import boto3
from botocore.client import Config

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
    
    # Add roles (adjust as needed)
    user.add_roles("Exam Candidate")
    # Save the user
    user.insert(ignore_permissions=True)
    return email


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

	def exam_ended(self):
		"""
		End time is schedule start time + duration + additional time given
		returns True, end_time if exam has ended
		"""
		scheduled_start, duration = frappe.get_cached_value(
		"Exam Schedule", self.exam_schedule, ["start_date_time", "duration"]
		)
		end_time = scheduled_start + timedelta(minutes=duration) + \
			timedelta(minutes=self.additional_time_given)
		
		current_time = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')

		if current_time >= end_time:
			return True, end_time
		
		return False, end_time
	
	def before_save(self):
		# if frappe.db.exists(
		# 	"Exam Submission",
		# 	{"candidate": self.candidate, "exam_schedule": self.exam_schedule}
		# ):
		# 	frappe.throw("Duplicate submission exists for {} - {}".format(self.candidate, self.exam_schedule))

		if self.exam_started_time:
			self.total_marks, self.evaluation_pending, self.result_status = evaluation_values(
				self.exam, self.submitted_answers
			)

		if "System Manager" in frappe.get_roles():
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
		sched.save()
	
	def before_insert(self):
		last_login = frappe.db.get_value("User", self.candidate, "last_login")
		if not last_login:
			self.new_user = 1
			self.reset_password_key = frappe.db.get_value("User", self.candidate, "reset_password_key")


def can_process_question(doc, member=None):
	"""
	validatior function to run before getting or updating a question
	"""
	if doc.status == "Submitted":
		frappe.throw("Exam submitted!")
	elif doc.status == "Started":
		# check if the exam is ended, if so, submit the exam
		exam_ended, end_time = doc.exam_ended()
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


def evaluation_values(exam, submitted_answers):
	# add marks and evalualtion oending count is applicable
	total_marks = 0
	eval_pending = 0
	result_status = "NA"
	for ans in submitted_answers:
		if ans.is_correct:
			total_marks += ans.mark
		if ans.evaluation_status == "Pending":
			eval_pending += 1
	# check result status
	exam_total_mark, pass_perc = frappe.get_cached_value(
		"Exam", exam, ["total_marks", "pass_percentage"]
	)
	pass_mark = (exam_total_mark * pass_perc)/100
	if total_marks >= pass_mark:
		result_status = "Passed"
	elif eval_pending == 0:
		result_status = "Failed"
	else:
		result_status = "NA"
	
	return total_marks, eval_pending, result_status

def rebuild_cache(exam_submission):
	"""
	If the system restarts/crashes in while an ongoing exam,
	Restart it
	"""
	doc = frappe.get_doc("Exam Submission", exam_submission)
	doc.can_start_exam()
	if doc.status != "Started":
		return
	cached_exam = frappe.cache().hget(exam_submission, "exam")
	if cached_exam:
		return
	

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
	# get questions
	questions = frappe.get_all(
		"Exam Schedule Question", filters={"parent": doc.exam}, fields=["exam_question"]
	)
	random_questions = frappe.get_cached_value("Exam", doc.exam, "randomize_questions")
	if random_questions:
		random.shuffle(questions)

	doc.submitted_answers = []
	qs_data = {}
	for idx, qs in enumerate(questions):
		seq_no = idx + 1
		qs_ = {
				"seq_no": seq_no,
				"exam_question": qs["exam_question"],
				"evaluation_status": "Not Attempted"
		}
		doc.append('submitted_answers', qs_)
		qs_data["qs:{}".format(seq_no)] = "{}:{}".format(qs["exam_question"], "Not Attempted")
	

	doc.status = "Started"
	doc.save(ignore_permissions=True)

	# cache submission details
	start_date_time, duration = frappe.get_cached_value(
		"Exam Schedule", doc.exam_schedule, ["start_date_time", "duration"]
	)
	# end time is schedule start time + duration + additional time given
	end_time = start_date_time + timedelta(minutes=duration) + \
			timedelta(minutes=doc.additional_time_given)
	data = {
		"candidate": doc.candidate,
		"exam_schedule": doc.exam_schedule,
		"exam": doc.exam,
		"total_questions": str(frappe.get_cached_value(
			"Exam", doc.exam, "total_questions"
		)),
		"status": doc.status,
		"exam_started_time": start_time.isoformat(),
		"exam_end_time": end_time.isoformat(),
		"additional_time_given": str(doc.additional_time_given),
		"assigned_evaluator": doc.assigned_evaluator or "",
		"assigned_proctor": doc.assigned_proctor or "",
		"warning_count": 0,
	}
	for k, v in qs_data.items():
		data[k] = v
	for k,v in data.items():
		frappe.cache().hset(exam_submission, k, v)
	expiration = (end_time - start_date_time).seconds
	frappe.cache().setex("{}:tracker".format(doc.name), expiration, 1)

	return True

@frappe.whitelist()
def end_exam(exam_submission=None):
	"""
	Submit Candidate exam
	"""
	assert exam_submission
	doc = frappe.get_doc("Exam Submission", exam_submission)
	if doc.status == "Submitted":
		frappe.throw("Exam is sbumitted already.")
	if doc.status != "Started":
		frappe.throw("Exam is not in started state.")

	doc.status = "Submitted"
	doc.exam_submitted_time = datetime.now()
	doc.save(ignore_permissions=True)

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
	exam = frappe.cache().hget(exam_submission, "exam")
	if not exam:
		frappe.throw("Invalid exam.")

	if not frappe.cache().get("{}:tracker".format(exam_submission)):
		doc = frappe.get_doc("Exam Submission", exam_submission)
		can_process_question(doc)

	# check if the requested question is valid
	if qs_no > int(frappe.cache().hget(exam_submission, "total_questions")):
		frappe.throw("Invalid question no. {} requested.".format(qs_no))
	# check if the previous question is answered. else throw err
	# if qs_no > 1:
	# 	prev = frappe.cache().hget(exam_submission, "qs:{}".format(qs_no-1))
	# 	if prev.split(":")[-1] == "Not Attempted":
	# 		frappe.throw("Previous question not attempted.")

	# get the qs with seq no
	qs_ = frappe.cache().hget(exam_submission, "qs:{}".format(qs_no))
	if not qs_:
		frappe.throw("Invalid question no. {} requested.".format(qs_no))
	qs_name = qs_.split(":")[0]
	
	try:
		question_doc = frappe.get_cached_doc("Exam Question", qs_name)
	except frappe.DoesNotExistError:
		frappe.throw("Invalid question requested.")


	answer_doc = frappe.get_value(
		"Exam Answer", "{}-{}".format(exam_submission, qs_name),
		["marked_for_later", "answer", "seq_no"], as_dict=True
	)

	res = {
		"question": question_doc.question,
		"qs_no": answer_doc["seq_no"],
		"name": question_doc.name,
		"type": question_doc.type,
		"description_image": question_doc.description_image,
		"option_1": question_doc.option_1,
		"option_2": question_doc.option_2,
		"option_3": question_doc.option_3,
		"option_4": question_doc.option_4,
		"option_1_image": question_doc.option_1_image,
		"option_2_image": question_doc.option_2_image,
		"option_3_image": question_doc.option_3_image,
		"option_4_image": question_doc.option_4_image,
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

	submission = frappe.get_doc("Exam Submission", exam_submission)
	# check of the logged in user is same as exam submission candidate
	if frappe.session.user != submission.candidate:
		raise PermissionError("You don't have access to submit and answer.")

	can_process_question(submission)
	if not frappe.db.exists("Exam Answer", "{}-{}".format(exam_submission, qs_name)):
		frappe.throw("Invalid question.")

	result_doc = frappe.get_doc("Exam Answer", "{}-{}".format(exam_submission, qs_name))
	frappe.cache().hset(
		exam_submission,
		"qs:{}".format(result_doc.seq_no),
		"{}:{}".format(qs_name, "Pending"
	))

	result_doc.answer = answer
	result_doc.marked_for_later = markdflater
	result_doc.evaluation_status = "Pending"
	result_doc.save(ignore_permissions=True)

		
	return {"qs_name": qs_name, "qs_no": result_doc.seq_no}


@frappe.whitelist()
def submit_exam(exam_submission=None):
	"""
	Submit response and add marks if applicable
	"""
	assert exam_submission

	doc = frappe.get_doc("Exam Submission", exam_submission)
	# check of the logged in user is same as exam submission candidate
	if frappe.session.user != doc.candidate:
		raise PermissionError("You don't have access to this exam.")

	if doc.status == "Submitted":
		frappe.throw("Exam submitted!")
	elif doc.status == "Started":
		# check if the exam is ended, if so, submit the exam
		exam_ended, end_time = doc.exam_ended()
		if exam_ended:
			doc.status = "Submitted"
			doc.save(ignore_permissions=True)

	return {"status": "Submitted"}

@frappe.whitelist()
def post_exam_message(exam_submission=None, message=None, type_of_message="General", warning_type="other"):
	"""
	Submit response and add marks if applicable
	"""
	assert exam_submission
	assert message

	doc = frappe.get_doc("Exam Submission", exam_submission)
	if doc.status != "Started":
		{"status": 0}

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
	doc = frappe.get_doc("Exam Submission", exam_submission)

	# check of the logged in user is same as exam submission candidate or proctor
	if frappe.session.user not in [doc.candidate, doc.assigned_proctor]:
		raise PermissionError("You don't have access to view messages.")

	res = frappe.get_all("Exam Messages", filters={
		"exam_submission": exam_submission
	}, fields=["creation", "from", "message", "type_of_message"])
	for idx, _ in enumerate(res):
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
	cfdomain = 'https://{}.r2.cloudflarestorage.com'.format(
		settings.aws_account_id
	)
	s3_client = boto3.client(
		's3', 
		endpoint_url = cfdomain,
		aws_access_key_id=settings.aws_key, 
		aws_secret_access_key=settings.get_password("aws_secret"),
		config=Config(signature_version='s3v4')
	)
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

	required_roles = ["Class Evaluator", "System Manager"]
	user_roles = frappe.get_roles(frappe.session.user)
	has_role = any(item in user_roles for item in required_roles)
	if not has_role:
		raise frappe.PermissionError(_("No permission to access this page."))

	res = get_videos(exam_submission)

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

	# make sure that logged in user is valid proctor
	if frappe.session.user != frappe.cache().hget(exam_submission, "assigned_proctor"):
		raise frappe.PermissionError(_("No proctor access to the exam."))

	ttl = frappe.cache().ttl("{}:tracker".format(exam_submission))
	res = get_videos(exam_submission, ttl)

	return res

@frappe.whitelist()
def upload_video(exam_submission=None):
	"""
	Get the list of videos from s3
	TODO Add a caching layer to avoid creating boto3 connections/req
	"""
	assert exam_submission
	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please login to access this page."))

	if not frappe.cache().get("{}:tracker".format(exam_submission)):
		raise frappe.PermissionError(_("Exam is invalid/ended."))
	# check if the exam is of logged in user
	if frappe.session.user != \
		frappe.get_cached_value("Exam Submission", exam_submission, "candidate"):
		raise frappe.PermissionError(_("Exam does not belongs to the user."))
	
	settings = frappe.get_single("Exam Settings")
	cfdomain = 'https://{}.r2.cloudflarestorage.com'.format(
		settings.aws_account_id
	)
	s3_client = boto3.client(
		's3',
		endpoint_url = cfdomain,
		aws_access_key_id=settings.aws_key, 
		aws_secret_access_key=settings.get_password("aws_secret"),
		config=Config(signature_version='s3v4')
	)
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
	ttl = frappe.cache().ttl("{}:tracker".format(exam_submission))

	try:
		# Stream the file directly to S3
		s3_client.upload_fileobj(file, bucket_name, object_name)
	except Exception as e:
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
		frappe.publish_realtime(
			event='newproctorvideo',
			message={
				"exam_submission": exam_submission,
				"ts": filename[:-5],
				"url": presigned_url
			},
			user=frappe.cache().hget(exam_submission, "assigned_proctor")
		)
		return {"status": True}

def val_secs(securities):
	for row in securities:
		print(row["qty"], row["isin"])
	return {"done": 1}

@frappe.whitelist()
def ping(securities):
	return val_secs(securities)


@frappe.whitelist()
def register_candidate(schedule=None, user_email=None, user_name=None):
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
	if not frappe.db.exists({"doctype": "Exam Submission", "candidate": user_email, "exam_schedule": schedule}):
		new_submission = frappe.get_doc(
			{"doctype": "Exam Submission", "candidate": user_email, "exam_schedule": schedule}
		)
		new_submission.insert(ignore_permissions=True)
		frappe.db.commit()


