import frappe

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