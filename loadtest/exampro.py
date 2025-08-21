"""
Simplified Frappe client wrapper for ExamPro
Clean interface based on frappe-client documentation
"""
from frappeclient import FrappeClient
from typing import Dict, List, Optional, Any
import sys
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr


class ExamproClient:
    def __init__(self, url: str, username: str, password: str):
        self.conn = FrappeClient(url)
        self.conn.login(username, password)

    def call_method(self, method: str, **params) -> Optional[Any]:
        """Call a server method"""
        try:
            return self.conn.post_request({
                'cmd': method,
                **params
            })
        except Exception:
            return None

    def insert(self, doc: Dict) -> Optional[Dict]:
        """Insert a document"""
        try:
            return self.conn.insert(doc)
        except Exception as e:
            print(e)
            print(f"Failed to insert {doc.get('doctype', 'Unknown')} document")
            return None

    def get_doc(self, doctype: str, name: str = "", filters: Dict = None) -> Optional[Dict]:
        """Get a document"""
        try:
            return self.conn.get_doc(doctype, name, filters)
        except Exception:
            identifier = name if name else str(filters) if filters else "document"
            print(f"Failed to get {doctype}: {identifier}")
            return None

    def exists(self, doctype: str, name: str) -> bool:
        """Check if document exists"""
        return self.get_doc(doctype, name) is not None

    # ExamPro convenience methods
    def create_user(self, email: str, first_name: str, last_name: str, 
                   password: str, user_type: str = "Website User") -> Optional[str]:
        """Create a user"""
        if self.exists("User", email):
            print(f"👤 User '{email}' already exists")
            return email
            
        user_data = {
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "new_password": password,
            "user_type": user_type,
            "enabled": 1,
            "send_welcome_email": 0
        }
        
        result = self.insert(user_data)
        return result.get("name") if result else None

    def create_question_category(self, title: str) -> Optional[str]:
        """Create a question category"""
        if self.exists("Exam Question Category", title):
            print(f"📋 Category '{title}' already exists")
            return title
            
        result = self.insert({
            "doctype": "Exam Question Category",
            "title": title
        })
        return result.get("name") if result else None

    def create_question(self, question_text: str, category: str, options: List[str], 
                       correct_index: int, marks: int = 1) -> Optional[str]:
        """Create an exam question"""
        question_data = {
            "doctype": "Exam Question",
            "question": question_text,
            "category": category,
            "mark": marks,
            "type": "Choices",
            "multiple": 0
        }
        
        # Add up to 4 options
        for i, option in enumerate(options[:4]):
            question_data[f"option_{i+1}"] = option
            question_data[f"is_correct_{i+1}"] = 1 if i == correct_index else 0
        
        result = self.insert(question_data)
        return result.get("name") if result else None

    def create_exam(self, title: str, description: str = "", duration: int = 60, 
                   pass_percentage: float = 60.0) -> Optional[str]:
        """Create an exam"""
        exam_data = {
            "doctype": "Exam",
            "title": title,
            "description": description,
            "duration": duration,
            "pass_percentage": pass_percentage,
        }
        
        result = self.insert(exam_data)
        return result.get("name") if result else None

    def create_exam_schedule(self, exam: str, start_time: str, schedule_name: str = None,
                           end_time: str = None, schedule_type: str = "Fixed") -> Optional[str]:
        """Create an exam schedule"""
        from datetime import datetime, timedelta
        
        # If end_time is not provided, calculate it from start_time + 2 hours
        if not end_time:
            start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00') if start_time.endswith('Z') else start_time)
            end_datetime = start_datetime + timedelta(hours=2)
            end_time = end_datetime.isoformat()
        
        # Generate a name if not provided (required for autoname: prompt)
        if not schedule_name:
            # Create a readable name with exam and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            schedule_name = f"{exam}_Schedule_{timestamp}"
        
        schedule_data = {
            "doctype": "Exam Schedule",
            "name": schedule_name,  # Always provide a name
            "exam": exam,
            "start_date_time": start_time,
            "schedule_type": schedule_type
        }
        
        # Add schedule_expire_in_days for flexible schedules
        if schedule_type == "Flexible":
            schedule_data["schedule_expire_in_days"] = 7  # Default 7 days
        
        result = self.insert(schedule_data)
        return result.get("name") if result else None

    def register_user_for_exam(self, schedule_name: str, user_email: str) -> bool:
        """Register a user for an exam schedule by creating an Exam Submission"""
        # Get the exam from the schedule
        schedule = self.get_doc("Exam Schedule", schedule_name)
        if not schedule:
            return False
        
        submission_data = {
            "doctype": "Exam Submission",
            "exam_schedule": schedule_name,
            "exam": schedule.get("exam"),
            "candidate": user_email,
            "status": "Registered"
        }
        
        result = self.insert(submission_data)
        return result is not None

    def add_question_to_exam(self, exam_name: str, question_name: str) -> bool:
        """Add a question to an exam"""
        result = self.insert({
            "doctype": "Exam Added Question",
            "parent": exam_name,
            "parenttype": "Exam",
            "parentfield": "added_questions",
            "exam_question": question_name
        })
        return result is not None

    def get_list(self, doctype: str, fields: List[str] = None, filters: Dict = None, 
                limit_start: int = 0, limit_page_length: int = 0, order_by: str = None) -> Optional[List]:
        """Get list of documents"""
        try:
            return self.conn.get_list(
                doctype=doctype,
                fields=fields or ["*"],
                filters=filters,
                limit_start=limit_start,
                limit_page_length=limit_page_length,
                order_by=order_by
            )
        except Exception:
            print(f"Failed to get list of {doctype}")
            return None

    def update(self, doc: Dict) -> Optional[Dict]:
        """Update a document"""
        try:
            return self.conn.update(doc)
        except Exception:
            doctype = doc.get('doctype', 'Unknown')
            name = doc.get('name', 'Unknown')
            print(f"Failed to update {doctype}: {name}")
            return None

    def delete(self, doctype: str, name: str) -> bool:
        """Delete a document"""
        try:
            # Suppress any print statements from the underlying library
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.conn.delete(doctype, name)
            return True
        except Exception:
            print(f"Failed to delete {doctype}: {name}")
            return False

    def logout(self):
        """Logout from the session"""
        try:
            self.conn.logout()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()