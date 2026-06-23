import hashlib
import hmac

import requests

import frappe
from frappe import _


@frappe.whitelist()
def create_razorpay_order(schedule_name):
	schedule = frappe.get_doc("Exam Schedule", schedule_name)
	exam = frappe.get_doc("Exam", schedule.exam)

	if not exam.is_public:
		frappe.throw(_("This exam is not available for public registration."))
	if not exam.enable_payment:
		frappe.throw(_("Payment is not enabled for this exam."))

	status = schedule.get_status()
	if status == "Completed":
		frappe.throw(_("This exam schedule has already been completed."))

	existing = frappe.db.exists("Exam Submission", {
		"exam_schedule": schedule_name,
		"candidate": frappe.session.user,
		"status": ["not in", ["Registration Cancelled", "Aborted"]],
	})
	if existing:
		frappe.throw(_("You are already registered for this exam schedule."))

	settings = frappe.get_single("Exam Settings")
	key_id = settings.razorpay_key_id
	key_secret = settings.get_password("razorpay_key_secret")

	if not key_id or not key_secret:
		frappe.throw(_("Payment gateway is not configured. Please contact the administrator."))

	amount_paise = int(exam.price * 100)
	currency = "INR"

	response = requests.post(
		"https://api.razorpay.com/v1/orders",
		auth=(key_id, key_secret),
		json={
			"amount": amount_paise,
			"currency": currency,
			"notes": {
				"exam": exam.name,
				"schedule": schedule_name,
				"candidate": frappe.session.user,
			},
		},
		timeout=30,
	)

	if response.status_code != 200:
		frappe.log_error(f"Razorpay order creation failed: {response.text}", "Razorpay Error")
		frappe.throw(_("Failed to create payment order. Please try again."))

	order_data = response.json()

	payment = frappe.new_doc("Exam Payment")
	payment.candidate = frappe.session.user
	payment.exam_schedule = schedule_name
	payment.razorpay_order_id = order_data["id"]
	payment.amount = exam.price
	payment.currency = currency
	payment.status = "Created"
	payment.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"order_id": order_data["id"],
		"amount": amount_paise,
		"currency": currency,
		"key_id": key_id,
		"exam_title": exam.title,
	}


@frappe.whitelist()
def verify_payment(schedule_name, razorpay_order_id, razorpay_payment_id, razorpay_signature):
	payment = frappe.get_doc("Exam Payment", {"razorpay_order_id": razorpay_order_id})

	if payment.candidate != frappe.session.user:
		frappe.throw(_("Payment verification failed: unauthorized."), frappe.AuthenticationError)

	if payment.status == "Paid":
		return {"success": True, "message": _("Payment already verified.")}

	settings = frappe.get_single("Exam Settings")
	key_secret = settings.get_password("razorpay_key_secret")

	message = f"{razorpay_order_id}|{razorpay_payment_id}"
	expected_signature = hmac.new(
		key_secret.encode("utf-8"),
		message.encode("utf-8"),
		hashlib.sha256,
	).hexdigest()

	if not hmac.compare_digest(expected_signature, razorpay_signature):
		payment.status = "Failed"
		payment.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(_("Payment verification failed: invalid signature."))

	schedule = frappe.get_doc("Exam Schedule", schedule_name)
	exam = frappe.get_doc("Exam", schedule.exam)
	if int(payment.amount * 100) != int(exam.price * 100):
		payment.status = "Failed"
		payment.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(_("Payment verification failed: amount mismatch."))

	payment.razorpay_payment_id = razorpay_payment_id
	payment.razorpay_signature = razorpay_signature
	payment.status = "Paid"

	_ensure_candidate_role()

	submission = frappe.new_doc("Exam Submission")
	submission.exam_schedule = schedule_name
	submission.exam = schedule.exam
	submission.candidate = frappe.session.user
	submission.status = "Registered"
	submission.insert(ignore_permissions=True)

	payment.exam_submission = submission.name
	payment.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"success": True,
		"message": _("Payment verified and registration complete."),
		"submission_id": submission.name,
	}


@frappe.whitelist()
def register_for_free(schedule_name):
	schedule = frappe.get_doc("Exam Schedule", schedule_name)
	exam = frappe.get_doc("Exam", schedule.exam)

	if not exam.is_public:
		frappe.throw(_("This exam is not available for public registration."))
	if exam.enable_payment:
		frappe.throw(_("This exam requires payment."))

	status = schedule.get_status()
	if status == "Completed":
		frappe.throw(_("This exam schedule has already been completed."))

	existing = frappe.db.exists("Exam Submission", {
		"exam_schedule": schedule_name,
		"candidate": frappe.session.user,
		"status": ["not in", ["Registration Cancelled", "Aborted"]],
	})
	if existing:
		frappe.throw(_("You are already registered for this exam schedule."))

	_ensure_candidate_role()

	submission = frappe.new_doc("Exam Submission")
	submission.exam_schedule = schedule_name
	submission.exam = schedule.exam
	submission.candidate = frappe.session.user
	submission.status = "Registered"
	submission.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"success": True,
		"message": _("Registration complete."),
		"submission_id": submission.name,
	}


def _ensure_candidate_role():
	user_roles = frappe.get_roles(frappe.session.user)
	if "Exam Candidate" not in user_roles:
		user = frappe.get_doc("User", frappe.session.user)
		user.append("roles", {"role": "Exam Candidate"})
		user.save(ignore_permissions=True)
