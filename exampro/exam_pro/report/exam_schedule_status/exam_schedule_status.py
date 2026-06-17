# Copyright (c) 2024, Labeeb Mattra and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from exampro.exam_pro.doctype.exam_schedule.exam_schedule import get_schedule_status

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("ID"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Exam Schedule",
            "width": 120
        },
        {
            "label": _("Exam"),
            "fieldname": "exam",
            "fieldtype": "Link",
            "options": "Exam",
            "width": 180
        },
        {
            "label": _("Scheduled Time"),
            "fieldname": "start_date_time",
            "fieldtype": "Datetime",
            "width": 150
        },
        {
            "label": _("Duration (min)"),
            "fieldname": "duration",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        }
    ]

def get_data(filters):
    conditions = []
    values = {}
    
    if filters.get("exam"):
        conditions.append("exam = %(exam)s")
        values["exam"] = filters.get("exam")
    
    if filters.get("from_date") and filters.get("to_date"):
        conditions.append("start_date_time BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters.get("from_date")
        values["to_date"] = filters.get("to_date")
    
    where_clause = " AND ".join(conditions) if conditions else ""
    where_clause = "WHERE " + where_clause if where_clause else ""
    
    data = frappe.db.sql(
        f"""
        SELECT name, exam, start_date_time, duration, schedule_type, schedule_expire_in_days
        FROM `tabExam Schedule`
        {where_clause}
        ORDER BY start_date_time DESC
        """,
        values,
        as_dict=1
    )
    
    for row in data:
        row["status"] = get_schedule_status(row.name)
    
    # Filter by status if specified
    if filters.get("status"):
        data = [row for row in data if row.get("status") == filters.get("status")]
    
    return data
