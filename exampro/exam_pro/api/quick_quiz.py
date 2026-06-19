import random

import frappe
from frappe.utils import now


def _get_published_quiz(short_uuid):
	"""Load a Quick Quiz by short_uuid, ensuring it is Published."""
	quiz_name = frappe.get_value(
		"Quick Quiz", {"short_uuid": short_uuid, "status": "Published"}, "name"
	)
	if not quiz_name:
		frappe.throw("Quiz not found or not published", frappe.DoesNotExistError)
	return frappe.get_doc("Quick Quiz", quiz_name)


def _verify_exam_manager():
	"""Raise PermissionError if caller is not an Exam Manager."""
	if "Exam Manager" not in frappe.get_roles():
		frappe.throw(
			"You are not authorized to perform this action", frappe.PermissionError
		)


def _get_correct_option(question_row):
	"""Return the 1-based index of the correct option for a question row."""
	for i in range(1, 5):
		if question_row.get(f"is_correct_{i}"):
			return i
	return None


def _build_question_list(quiz, include_correct=False):
	"""Build a list of question dicts from the quiz, optionally shuffled."""
	questions = []
	ordered = list(enumerate(quiz.questions or [], start=0))
	marks = quiz.marks_per_question or 1

	if quiz.randomize_questions:
		random.shuffle(ordered)

	for idx, q in ordered:
		item = {
			"index": idx,
			"question": q.question,
			"question_image": q.question_image,
			"option_1": q.option_1,
			"option_2": q.option_2,
			"option_3": q.option_3,
			"option_4": q.option_4,
			"points": marks,
		}
		if include_correct:
			item["correct_option"] = _get_correct_option(q)
		questions.append(item)

	return questions


def _build_leaderboard(quiz_name, limit=20):
	"""Return top submissions for a quiz, ordered by score desc then time asc."""
	submissions = frappe.get_all(
		"Quick Quiz Submission",
		filters={
			"quiz": quiz_name,
			"status": ["in", ["In Progress", "Completed"]],
		},
		fields=[
			"participant_name",
			"score",
			"total_points",
			"correct_count",
			"time_taken_seconds",
		],
		order_by="score desc, time_taken_seconds asc",
		limit_page_length=limit,
	)
	return submissions


def _broadcast_question(quiz, question_idx):
	"""Broadcast a single question (without correct answer) to the quiz room."""
	questions = quiz.questions or []
	if question_idx < 0 or question_idx >= len(questions):
		frappe.throw(f"Invalid question index: {question_idx}")

	q = questions[question_idx]
	message = {
		"question_idx": question_idx,
		"question": q.question,
		"question_image": q.question_image,
		"option_1": q.option_1,
		"option_2": q.option_2,
		"option_3": q.option_3,
		"option_4": q.option_4,
		"points": quiz.marks_per_question or 1,
		"total_questions": len(questions),
	}

	if quiz.timer_enabled and quiz.timer_seconds:
		message["timer_seconds"] = quiz.timer_seconds

	frappe.publish_realtime(
		"quiz_question", message=message, room=f"quiz:{quiz.short_uuid}"
	)


# ---------------------------------------------------------------------------
# Guest-facing APIs
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def get_quiz_info(short_uuid):
	"""Return quiz metadata without questions or answers."""
	fields = [
		"name",
		"title",
		"description",
		"image",
		"quiz_mode",
		"access_type",
		"theme",
		"total_questions",
		"timer_enabled",
		"timer_seconds",
		"show_correct_after_answer",
	]
	quiz = frappe.get_value(
		"Quick Quiz",
		{"short_uuid": short_uuid, "status": "Published"},
		fields,
		as_dict=True,
	)
	if not quiz:
		frappe.throw("Quiz not found or not published", frappe.DoesNotExistError)

	if "Exam Manager" in frappe.get_roles():
		quiz["pin_code"] = frappe.get_value("Quick Quiz", quiz.name, "pin_code")

	return quiz


@frappe.whitelist(allow_guest=True)
def validate_pin(short_uuid, pin):
	"""Validate a PIN for a PIN-protected quiz."""
	quiz = _get_published_quiz(short_uuid)

	if quiz.access_type != "PIN":
		frappe.throw("This quiz does not require a PIN")

	if pin != quiz.pin_code:
		frappe.throw("Invalid PIN")

	return {"valid": True}


@frappe.whitelist(allow_guest=True)
def join_quiz(short_uuid, participant_name, pin=None):
	"""Create a submission and return quiz questions (without correct answers)."""
	quiz = _get_published_quiz(short_uuid)

	# Access control
	if quiz.access_type == "PIN":
		if pin != quiz.pin_code:
			frappe.throw("Invalid PIN")
	elif quiz.access_type == "Auth":
		if frappe.session.user == "Guest":
			frappe.throw("You must be logged in to join this quiz")

	# Determine participant info
	participant_email = None
	user_link = None
	if frappe.session.user != "Guest":
		participant_email = frappe.session.user
		user_link = frappe.session.user
		if not participant_name:
			participant_name = frappe.get_value("User", frappe.session.user, "full_name")

	# Create submission
	submission = frappe.get_doc({
		"doctype": "Quick Quiz Submission",
		"quiz": quiz.name,
		"quiz_mode": quiz.quiz_mode,
		"status": "Waiting",
		"participant_name": participant_name,
		"participant_email": participant_email,
		"user": user_link,
	})
	submission.insert(ignore_permissions=True)

	# Build questions list without correct answers
	questions = _build_question_list(quiz, include_correct=False)

	return {
		"submission_id": submission.name,
		"short_uuid": submission.short_uuid,
		"quiz_mode": quiz.quiz_mode,
		"questions": questions,
	}


@frappe.whitelist(allow_guest=True)
def submit_answer(submission_id, question_idx, selected_option, time_taken_ms=0):
	"""Record an answer for a question and calculate points."""
	question_idx = int(question_idx)
	selected_option = int(selected_option)
	time_taken_ms = int(time_taken_ms or 0)

	submission = frappe.get_doc(
		"Quick Quiz Submission", submission_id, ignore_permissions=True
	)
	if submission.status not in ("Waiting", "In Progress"):
		frappe.throw("This submission is no longer active")

	quiz = frappe.get_doc("Quick Quiz", submission.quiz)
	questions = quiz.questions or []

	if question_idx < 0 or question_idx >= len(questions):
		frappe.throw(f"Invalid question index: {question_idx}")

	q = questions[question_idx]
	correct_option = _get_correct_option(q)
	is_correct = selected_option == correct_option
	base_points = quiz.marks_per_question or 1

	# Calculate points
	points_earned = 0
	if is_correct:
		if quiz.quiz_mode == "Kahoot" and quiz.timer_enabled and quiz.timer_seconds:
			total_time_ms = quiz.timer_seconds * 1000
			remaining_ms = max(0, total_time_ms - time_taken_ms)
			points_earned = int(base_points * (remaining_ms / total_time_ms))
		else:
			points_earned = base_points

	# Check if answer already exists for this question_idx, update or create
	existing_row = None
	for row in submission.answers or []:
		if row.question_idx == question_idx:
			existing_row = row
			break

	if existing_row:
		existing_row.selected_option = selected_option
		existing_row.is_correct = is_correct
		existing_row.points_earned = points_earned
		existing_row.time_taken_ms = time_taken_ms
	else:
		submission.append("answers", {
			"question_idx": question_idx,
			"selected_option": selected_option,
			"is_correct": is_correct,
			"points_earned": points_earned,
			"time_taken_ms": time_taken_ms,
		})

	# Recalculate submission score
	submission.score = sum(a.points_earned or 0 for a in submission.answers)
	submission.save(ignore_permissions=True)

	# For Kahoot mode, broadcast answer count for this question
	if quiz.quiz_mode == "Kahoot":
		answer_count = frappe.db.count(
			"Quick Quiz Answer",
			filters={
				"parent": ["in", frappe.get_all(
					"Quick Quiz Submission",
					filters={"quiz": quiz.name, "status": ["in", ["In Progress", "Waiting"]]},
					pluck="name",
				)],
				"question_idx": question_idx,
			},
		)
		frappe.publish_realtime(
			"quiz_answer_count",
			message={"question_idx": question_idx, "count": answer_count},
			room=f"quiz:{quiz.short_uuid}",
		)

	# Build response
	response = {"points_earned": points_earned}
	if quiz.show_correct_after_answer:
		response["is_correct"] = is_correct
		response["correct_option"] = correct_option

	return response


@frappe.whitelist(allow_guest=True)
def finish_quiz(submission_id):
	"""Mark a submission as Completed and compute final tallies."""
	submission = frappe.get_doc(
		"Quick Quiz Submission", submission_id, ignore_permissions=True
	)
	if submission.status == "Completed":
		frappe.throw("This submission is already completed")

	submission.status = "Completed"
	submission.completed_at = now()

	# Calculate time taken
	if submission.started_at:
		from frappe.utils import time_diff_in_seconds
		submission.time_taken_seconds = time_diff_in_seconds(
			submission.completed_at, submission.started_at
		)
	else:
		submission.time_taken_seconds = 0

	# Compute final stats from answers
	answers = submission.answers or []
	submission.total_questions = len(answers)
	submission.correct_count = sum(1 for a in answers if a.is_correct)
	submission.score = sum(a.points_earned or 0 for a in answers)

	quiz = frappe.get_doc("Quick Quiz", submission.quiz)
	marks = quiz.marks_per_question or 1
	submission.total_points = marks * len(quiz.questions or [])

	submission.save(ignore_permissions=True)

	return {"status": "Completed"}


@frappe.whitelist(allow_guest=True)
def get_quiz_results(submission_id):
	"""Return results for a completed submission."""
	submission = frappe.get_doc(
		"Quick Quiz Submission", submission_id, ignore_permissions=True
	)
	if submission.status != "Completed":
		frappe.throw("Quiz has not been completed yet")

	if submission.quiz_mode == "Simple":
		return {
			"quiz_mode": "Simple",
			"status": "Completed",
		}

	# Kahoot mode - include score and leaderboard
	leaderboard = _build_leaderboard(submission.quiz, limit=10)

	# Determine rank
	rank = None
	for i, entry in enumerate(leaderboard, start=1):
		if entry.participant_name == submission.participant_name:
			rank = i
			break

	# If not in top 10, compute actual rank
	if rank is None:
		rank = frappe.db.count(
			"Quick Quiz Submission",
			filters={
				"quiz": submission.quiz,
				"status": "Completed",
				"score": [">", submission.score],
			},
		) + 1

	return {
		"quiz_mode": "Kahoot",
		"score": submission.score,
		"total_points": submission.total_points,
		"correct_count": submission.correct_count,
		"total_questions": submission.total_questions,
		"time_taken_seconds": submission.time_taken_seconds,
		"rank": rank,
		"leaderboard": leaderboard,
	}


@frappe.whitelist(allow_guest=True)
def get_leaderboard(short_uuid):
	"""Return top 20 submissions for a Kahoot quiz."""
	quiz = _get_published_quiz(short_uuid)

	if quiz.quiz_mode != "Kahoot":
		frappe.throw("Leaderboard is only available for Kahoot mode quizzes")

	leaderboard = _build_leaderboard(quiz.name, limit=20)
	return {"leaderboard": leaderboard}


# ---------------------------------------------------------------------------
# Host APIs (Exam Manager only)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def host_start_quiz(short_uuid):
	"""Start a quiz: move Waiting submissions to In Progress, broadcast first question."""
	_verify_exam_manager()
	quiz = _get_published_quiz(short_uuid)

	# Update all Waiting submissions to In Progress
	waiting_submissions = frappe.get_all(
		"Quick Quiz Submission",
		filters={"quiz": quiz.name, "status": "Waiting"},
		pluck="name",
	)

	current_time = now()
	for sub_name in waiting_submissions:
		frappe.db.set_value(
			"Quick Quiz Submission",
			sub_name,
			{"status": "In Progress", "started_at": current_time},
			update_modified=False,
		)

	frappe.db.commit()

	# Broadcast first question
	if quiz.questions:
		_broadcast_question(quiz, 0)

	questions = _build_question_list(quiz, include_correct=True)

	return {
		"started": True,
		"participant_count": len(waiting_submissions),
		"questions": questions,
	}


@frappe.whitelist()
def host_next_question(short_uuid, question_idx):
	"""Broadcast the next question to all participants."""
	_verify_exam_manager()
	quiz = _get_published_quiz(short_uuid)

	question_idx = int(question_idx)
	_broadcast_question(quiz, question_idx)

	return {"question_idx": question_idx}


@frappe.whitelist()
def host_show_leaderboard(short_uuid):
	"""Compute and broadcast the current leaderboard."""
	_verify_exam_manager()
	quiz = _get_published_quiz(short_uuid)

	leaderboard = _build_leaderboard(quiz.name, limit=20)

	frappe.publish_realtime(
		"quiz_leaderboard",
		message={"leaderboard": leaderboard},
		room=f"quiz:{quiz.short_uuid}",
	)

	return {"leaderboard": leaderboard}


@frappe.whitelist()
def host_end_quiz(short_uuid):
	"""End a quiz: mark remaining In Progress submissions as Completed, broadcast end."""
	_verify_exam_manager()
	quiz = _get_published_quiz(short_uuid)

	# Mark all In Progress submissions as Completed
	active_submissions = frappe.get_all(
		"Quick Quiz Submission",
		filters={"quiz": quiz.name, "status": "In Progress"},
		pluck="name",
	)

	current_time = now()
	for sub_name in active_submissions:
		sub = frappe.get_doc("Quick Quiz Submission", sub_name)
		sub.status = "Completed"
		sub.completed_at = current_time
		if sub.started_at:
			from frappe.utils import time_diff_in_seconds
			sub.time_taken_seconds = time_diff_in_seconds(current_time, sub.started_at)

		answers = sub.answers or []
		sub.total_questions = len(answers)
		sub.correct_count = sum(1 for a in answers if a.is_correct)
		sub.score = sum(a.points_earned or 0 for a in answers)
		marks = quiz.marks_per_question or 1
		sub.total_points = marks * len(quiz.questions or [])

		sub.save(ignore_permissions=True)

	frappe.db.commit()

	# Broadcast quiz ended
	leaderboard = _build_leaderboard(quiz.name, limit=20)
	frappe.publish_realtime(
		"quiz_ended",
		message={"leaderboard": leaderboard},
		room=f"quiz:{quiz.short_uuid}",
	)

	return {"leaderboard": leaderboard}


@frappe.whitelist()
def host_restart_quiz(short_uuid):
	"""Reset a quiz so it can be hosted again — removes all previous submissions."""
	_verify_exam_manager()
	quiz = _get_published_quiz(short_uuid)

	submissions = frappe.get_all(
		"Quick Quiz Submission",
		filters={"quiz": quiz.name},
		pluck="name",
	)
	for sub_name in submissions:
		frappe.delete_doc("Quick Quiz Submission", sub_name, ignore_permissions=True)

	frappe.db.commit()

	return {"restarted": True}


@frappe.whitelist()
def get_live_participants(short_uuid):
	"""Return list of current participants and answer counts for the latest question."""
	_verify_exam_manager()
	quiz = _get_published_quiz(short_uuid)

	participants = frappe.get_all(
		"Quick Quiz Submission",
		filters={
			"quiz": quiz.name,
			"status": ["in", ["Waiting", "In Progress", "Completed"]],
		},
		fields=["participant_name", "status", "score"],
		order_by="creation asc",
	)

	# Count answers for the most recent question across active submissions
	active_names = frappe.get_all(
		"Quick Quiz Submission",
		filters={
			"quiz": quiz.name,
			"status": ["in", ["In Progress", "Waiting"]],
		},
		pluck="name",
	)

	# Find the highest question_idx that has been answered
	answer_counts = {}
	if active_names:
		answers = frappe.get_all(
			"Quick Quiz Answer",
			filters={"parent": ["in", active_names]},
			fields=["question_idx", "count(name) as cnt"],
			group_by="question_idx",
		)
		answer_counts = {a.question_idx: a.cnt for a in answers}

	return {
		"participants": participants,
		"participant_count": len(participants),
		"answer_counts": answer_counts,
	}
