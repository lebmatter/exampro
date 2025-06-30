from frappe import _

def get_data():
    return {
        "color": "#4DB6AC",
        "icon": "book",
        "type": "module",
        "label": _("Exam Pro"),
        "onboard_present": 1,
        "desk_sections": [
            {
                "label": "Dashboard",
                "links": [
                    {
                        "label": "Exam Dashboard",
                        "type": "page",
                        "name": "exam-dashboard",
                        "description": "View exam statistics and metrics"
                    }
                ]
            },
            {
                "label": "Configuration",
                "links": [
                    {
                        "label": "Exams",
                        "type": "doctype",
                        "name": "Exam",
                        "description": "Create and manage exams"
                    },
                    {
                        "label": "Exam Schedule",
                        "type": "doctype",
                        "name": "Exam Schedule",
                        "description": "Schedule exams for candidates"
                    },
                    {
                        "label": "Exam Batch",
                        "type": "doctype",
                        "name": "Exam Batch",
                        "description": "Create and manage exam batches"
                    }
                ]
            },
            {
                "label": "Reports",
                "links": [
                    {
                        "label": "Exam Submissions",
                        "type": "doctype",
                        "name": "Exam Submission",
                        "description": "View all exam submissions"
                    }
                ]
            }
        ]
    }
