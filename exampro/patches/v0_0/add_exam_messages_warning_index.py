import frappe


def execute():
	"""
	Add a composite index on Exam Messages (exam_submission, warning_type).

	post_exam_message runs a COUNT(*) filtered by both columns on every
	tab-change warning. The existing single-column index on exam_submission
	already narrows the scan, but a covering composite index lets the engine
	answer the count from the index alone.
	"""
	table = "tabExam Messages"
	index_name = "idx_exam_submission_warning_type"

	exists = frappe.db.sql(
		"""
		SELECT 1 FROM information_schema.statistics
		WHERE table_schema = DATABASE()
		  AND table_name = %s
		  AND index_name = %s
		LIMIT 1
		""",
		(table, index_name),
	)
	if exists:
		return

	frappe.db.sql_ddl(
		f"CREATE INDEX `{index_name}` ON `{table}` (`exam_submission`, `warning_type`)"
	)
