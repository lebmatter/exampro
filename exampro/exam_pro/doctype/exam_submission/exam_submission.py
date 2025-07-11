# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import random
import json
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.file_manager import get_uploaded_content
from frappe.utils import now
from werkzeug.utils import secure_filename

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
	# add marks and evalualtion pending count if applicable
	total_marks = sum([s.mark for s in submitted_answers if s.is_correct])
	eval_pending = len([s for s in submitted_answers if s.evaluation_status == "Pending"])
	result_status = "NA"
	# check result status
	exam_total_mark, pass_perc = frappe.get_cached_value(
		"Exam", exam, ["total_marks", "pass_percentage"]
	)
	pass_mark = (exam_total_mark * pass_perc)/100
	if total_marks >= pass_mark:
		result_status = "Passed"
	elif eval_pending == 0 and total_marks < pass_mark:
		result_status = "Failed"
	else:
		result_status = "NA"
	
	evaluation_status = "NA"
	if eval_pending > 0:
		evaluation_status = "Pending"
	
	return total_marks, evaluation_status, result_status
	

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
		"Exam Added Question", filters={"parent": doc.exam}, fields=["exam_question"]
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


def rebuild_exam_trackers():
    """
    Rebuild tracker keys and exam data for ongoing exams in case of app restart.
    This preserves the cache entries that track ongoing exam sessions.
    Called from on_app_init hook.
    """
    # Clear any existing S3 client
    if hasattr(frappe.local, "s3_client"):
        delattr(frappe.local, "s3_client")
    
    # Get all ongoing exams (status = "Started")
    ongoing_exams = frappe.get_all(
        "Exam Submission", 
        filters={"status": "Started"}, 
        fields=["name", "exam", "exam_schedule", "exam_started_time", "additional_time_given", 
                "candidate", "assigned_evaluator", "assigned_proctor"]
    )
    
    rebuilt_count = 0
    for exam in ongoing_exams:
        # Check if the tracker key exists
        if frappe.cache().get("{}:tracker".format(exam.name)):
            continue
        
        try:
            # Get required values to calculate expiration time
            start_date_time, duration = frappe.get_cached_value(
                "Exam Schedule", exam.exam_schedule, ["start_date_time", "duration"]
            )
            
            # Calculate end time (same logic as in start_exam)
            end_time = start_date_time + timedelta(minutes=duration) + \
                    timedelta(minutes=exam.additional_time_given)
            
            # Calculate remaining time
            current_time = datetime.strptime(now(), '%Y-%m-%d %H:%M:%S.%f')
            remaining_seconds = max(0, int((end_time - current_time).total_seconds()))
            
            # Only rebuild if exam is still in progress (has remaining time)
            if remaining_seconds > 0:
                # Rebuild the tracker key with remaining time
                frappe.cache().setex("{}:tracker".format(exam.name), remaining_seconds, 1)
                
                # Rebuild all exam cache data
                exam_doc = frappe.get_doc("Exam Submission", exam.name)
                
                # Cache submission details (similar to start_exam function)
                data = {
                    "candidate": exam.candidate,
                    "exam_schedule": exam.exam_schedule,
                    "exam": exam.exam,
                    "total_questions": str(frappe.get_cached_value(
                        "Exam", exam.exam, "total_questions"
                    )),
                    "status": "Started",
                    "exam_started_time": exam.exam_started_time.isoformat(),
                    "exam_end_time": end_time.isoformat(),
                    "additional_time_given": str(exam.additional_time_given),
                    "assigned_evaluator": exam.assigned_evaluator or "",
                    "assigned_proctor": exam.assigned_proctor or "",
                    "warning_count": 0,
                }
                
                # Get question data
                submitted_answers = frappe.get_all(
                    "Exam Answer", 
                    filters={"parent": exam.name},
                    fields=["seq_no", "exam_question", "evaluation_status"]
                )
                
                # Cache question data
                for ans in submitted_answers:
                    data[f"qs:{ans.seq_no}"] = f"{ans.exam_question}:{ans.evaluation_status}"
                
                # Set all cache entries
                for k, v in data.items():
                    frappe.cache().hset(exam.name, k, v)
                
                rebuilt_count += 1
                
                # Log for monitoring purposes
                frappe.logger().info(f"Rebuilt cache for exam submission: {exam.name} with {remaining_seconds} seconds remaining")
            else:
                # If the exam has expired, mark it as submitted
                exam_doc = frappe.get_doc("Exam Submission", exam.name)
                if exam_doc.status == "Started":
                    exam_doc.status = "Submitted"
                    exam_doc.exam_submitted_time = datetime.now()
                    exam_doc.save(ignore_permissions=True)
                    frappe.logger().info(f"Marked expired exam as submitted: {exam.name}")
                
        except Exception as error:
            frappe.logger().error(f"Failed to rebuild cache for exam {exam.name}: {str(error)}")
    
    frappe.logger().info(f"Rebuilt cache for {rebuilt_count} ongoing exams")
    return rebuilt_count


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
		doc.status = "Submitted"
		total_marks, evaluation_status, result_status = evaluation_values(
			doc.exam, doc.submitted_answers
		)
		doc.total_marks = total_marks
		doc.evaluation_status = evaluation_status
		doc.result_status = result_status
		doc.save(ignore_permissions=True)
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

	submission = frappe.get_doc("Exam Submission", exam_submission, ignore_permissions=True)
	# check of the logged in user is same as exam submission candidate
	if frappe.session.user != submission.candidate:
		raise PermissionError("You don't have access to submit and answer.")

	can_process_question(submission)
	if not frappe.db.exists("Exam Answer", "{}-{}".format(exam_submission, qs_name)):
		frappe.throw("Invalid question.")

	result_doc = frappe.get_doc("Exam Answer", "{}-{}".format(exam_submission, qs_name), ignore_permissions=True)
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

	# make sure that logged in user is valid proctor
	if frappe.session.user != frappe.cache().hget(exam_submission, "assigned_proctor"):
		raise frappe.PermissionError(_("No proctor access to the exam."))

	ttl = frappe.cache().ttl("{}:tracker".format(exam_submission))
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

	if not frappe.cache().get("{}:tracker".format(exam_submission)):
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
	ttl = frappe.cache().ttl("{}:tracker".format(exam_submission))

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


