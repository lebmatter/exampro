"""
Test Data Manager for ExamPro Load Testing
Handles creation and cleanup of test data for load testing scenarios
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loadtest.exampro import ExamproClient


class TestDataManager:
    def __init__(self, config_file: str = "data.json"):
        """Initialize test data manager"""
        self.config_file = config_file
        self.config = self._load_config()
        self.client = None
        self.test_session_id = self.config["test_config"]["session_id"]
        self.created_records = {
            "users": [],
            "categories": [],
            "questions": [],
            "exams": [],
            "schedules": [],
            "submissions": []
        }

    def _load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Configuration file {self.config_file} not found")
            raise
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {self.config_file}: {str(e)}")
            raise

    def connect(self) -> bool:
        """Connect to Frappe backend"""
        frappe_config = self.config["frappe_config"]
        
        print(f"🔗 Connecting to {frappe_config['site_url']}...")
        self.client = ExamproClient(
            url=frappe_config["site_url"],
            username=frappe_config["admin_username"],
            password=frappe_config["admin_password"]
        )
        
        if self.client:
            print(f"✅ Connected successfully")
            return True
        else:
            print(f"❌ Failed to connect")
            return False

    def _delete_existing_data(self):
        """
        Independent function to delete existing data in the correct order.
        Deletion order: exam submission entry, exam schedule, exam, exam question, exam question category, users
        """
        print(f"🧹 Deleting existing data for session: {self.test_session_id}")
        
        # Define deletion order: exam submission -> exam schedule -> exam -> exam question -> exam question category -> users
        deletion_order = [
            "Exam Submission",
            "Exam Schedule", 
            "Exam",
            "Exam Question Category",
            "User"
        ]
        
        total_deleted = 0
        
        for doctype in deletion_order:
            deleted_count = 0
            
            # Get doctype config from data.json
            if doctype not in self.config:
                print(f"  ⚠️  No configuration found for {doctype}")
                continue
                
            doctype_config = self.config[doctype]
            search_field = doctype_config["search_field"]
            
            # Search for records using LIKE on the search field
            try:
                # For most doctypes, we need both the search field and name field
                fields_to_get = ["name"]
                if search_field != "name":
                    fields_to_get.append(search_field)
                
                records = self.client.get_list(
                    doctype,
                    fields=fields_to_get,
                    filters={search_field: ["like", f"%{self.test_session_id}%"]}
                )
                
                if records:
                    print(f"  🗑️  Deleting {len(records)} {doctype} records...")
                    
                    for record in records:
                        record_name = record["name"]
                        search_value = record.get(search_field, "N/A") if search_field != "name" else record_name
                        try:
                            # Check if document exists before attempting to delete
                            doc = self.client.get_doc(doctype, record_name)
                            if doc:
                                if self.client.delete(doctype, record_name):
                                    deleted_count += 1
                                    print(f"    🗑️  Deleted {doctype}: {record_name} ({search_field}: {search_value})")
                                else:
                                    print(f"    ⚠️  Could not delete {doctype}: {record_name}")
                            else:
                                print(f"    📝 Document not found, skipping {doctype}: {record_name}")
                        except Exception as e:
                            # Continue with other records even if one fails
                            print(f"    ⚠️  Error deleting {doctype} {record_name}: {str(e)}")
                    
                    print(f"    ✅ Deleted {deleted_count}/{len(records)} {doctype} records")
                
            except Exception as e:
                print(f"  ⚠️  Could not search {doctype}: {str(e)}")
                continue
            
            total_deleted += deleted_count
        
        if total_deleted > 0:
            print(f"✅ Successfully deleted {total_deleted} records")
        else:
            print(f"📝 No records found to delete")
        
        return total_deleted

    def _cleanup_existing_session_data(self):
        """Clean up existing data for the current session if it exists"""
        print(f"🧹 Cleaning up any existing data for session: {self.test_session_id}")
        
        # Use the independent delete function to search and delete by session
        self._delete_existing_data()

    def _cleanup_from_session_file(self):
        """This method is no longer needed - kept for compatibility"""
        pass

    def setup_test_data(self) -> bool:
        """Setup all test data required for load testing"""
        if not self.connect():
            return False

        print(f"🚀 Setting up test data (Session: {self.test_session_id})")
        
        # Check for existing session data and clean it up first
        self._cleanup_existing_session_data()
        
        try:
            # 1. Create test users/candidates
            self._create_test_users()
            
            # 2. Create question categories
            self._create_question_categories()
            
            # 3. Create questions
            self._create_questions()
            
            # 4. Create exams
            self._create_exams()
            
            # 5. Create exam schedules
            self._create_exam_schedules()
            
            # 6. Register users for exams
            self._register_users_for_exams()
    
            
            print(f"✅ Test data setup completed successfully!")
            print(f"📊 Created: {len(self.created_records['users'])} users, "
                  f"{len(self.created_records['questions'])} questions, "
                  f"{len(self.created_records['exams'])} exams")
            
            return True
            
        except Exception as e:
            print(f"❌ Test data setup failed: {str(e)}")
            return False

    def _create_test_users(self):
        """Create test users for load testing"""
        num_candidates = self.config["test_config"]["num_candidates"]
        candidate_config = self.config["candidate_config"]
        
        print(f"👥 Creating {num_candidates} test users...")
        
        for i in range(num_candidates):
            email = f"{candidate_config['first_name_prefix'].lower()}{i}_{self.test_session_id}{candidate_config['email_domain']}"
            first_name = f"{candidate_config['first_name_prefix']}{i:03d}"
            last_name = f"{candidate_config['last_name_prefix']}{self.test_session_id[:8]}"
            
            user_name = self.client.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=candidate_config["default_password"],
                user_type=candidate_config["user_type"]
            )
            
            if user_name:
                self.created_records["users"].append(user_name)
                if i % 10 == 0:
                    print(f"  ✅ Created {i+1}/{num_candidates} users...")
            else:
                print(f"  ❌ Failed to create user {i}")

        print(f"✅ Created {len(self.created_records['users'])} users")

    def _create_question_categories(self):
        """Create question categories"""
        print("📂 Creating question categories...")
        
        # Get categories from data.json configuration
        categories = self.config["Exam Question Category"]["data"]
        
        for category_title in categories:
            category_name = self.client.create_question_category(category_title)
            if category_name:
                self.created_records["categories"].append(category_name)
                print(f"  ✅ Created category: {category_title}")

    def _create_questions(self):
        """Create exam questions"""
        questions_data = self.config["questions"]
        total_questions_needed = len(questions_data)  # Use exact number of questions in data.json
        
        print(f"❓ Creating {total_questions_needed} questions...")
        
        if not self.created_records["categories"]:
            print("❌ No categories available for questions")
            return
        
        for i, base_question in enumerate(questions_data):
            question_text = f"{base_question['question']} (LoadTest-{i+1}-{self.test_session_id[:8]})"
            
            # Distribute questions across all available categories
            category = self.created_records["categories"][i % len(self.created_records["categories"])]
            
            question_name = self.client.create_question(
                question_text=question_text,
                category=category,
                options=base_question["options"],
                correct_index=base_question["correct"],
                marks=random.randint(1, 5)
            )
            
            if question_name:
                self.created_records["questions"].append(question_name)
                if i % 10 == 0:
                    print(f"  ✅ Created {i+1}/{total_questions_needed} questions...")

        print(f"✅ Created {len(self.created_records['questions'])} questions")

    def _create_exams(self):
        """Create exam templates"""
        exam_templates = self.config["exam_templates"]
        num_exams = self.config["test_config"]["num_exams"]
        
        print(f"📝 Creating {num_exams} exams...")
        
        for i in range(num_exams):
            template = exam_templates[i % len(exam_templates)]
            
            exam_title = f"{template['title']} - {i+1} ({self.test_session_id[:8]})"
            exam_description = f"{template['description']} - Session: {self.test_session_id}"
            
            exam_name = self.client.create_exam(
                title=exam_title,
                description=exam_description,
                duration=template["duration"],
                pass_percentage=template["pass_percentage"]
            )
            
            if exam_name:
                self.created_records["exams"].append(exam_name)
                
                # Add questions to exam
                self._add_questions_to_exam(exam_name)
                
                print(f"  ✅ Created exam: {exam_title}")

        print(f"✅ Created {len(self.created_records['exams'])} exams")

    def _add_questions_to_exam(self, exam_name: str):
        """Add questions to an exam"""
        total_available_questions = len(self.config["questions"])
        
        if len(self.created_records["questions"]) < total_available_questions:
            print(f"  ⚠️ Not enough questions available for exam {exam_name}")
            return
        
        # Use all available questions for the exam (since we only have exactly what we need)
        selected_questions = self.created_records["questions"]
        
        for question_name in selected_questions:
            self.client.add_question_to_exam(exam_name, question_name)

    def _create_exam_schedules(self):
        """Create exam schedules"""
        print("📅 Creating exam schedules...")
        
        for exam_name in self.created_records["exams"]:
            # Create schedule starting 1 minute from now
            start_time = datetime.now() + timedelta(minutes=1)
            end_time = start_time + timedelta(hours=2)  # 2-hour window
            
            schedule_name = self.client.create_exam_schedule(
                exam=exam_name,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat()
            )
            
            if schedule_name:
                self.created_records["schedules"].append(schedule_name)
                print(f"  ✅ Created schedule for exam: {exam_name}")

    def _register_users_for_exams(self):
        """Register users for exam schedules"""
        print("🎫 Registering users for exams...")
        
        if not self.created_records["schedules"] or not self.created_records["users"]:
            print("❌ No schedules or users available for registration")
            return
        
        registrations_created = 0
        
        for schedule_name in self.created_records["schedules"]:
            # Register all users for each schedule
            for user_name in self.created_records["users"]:
                if self.client.register_user_for_exam(schedule_name, user_name):
                    registrations_created += 1
                    
        print(f"✅ Created {registrations_created} exam registrations")


    def cleanup_test_data(self, session_id: Optional[str] = None):
        """Cleanup test data"""
        if session_id:
            # Temporarily change session ID for cleanup
            original_session_id = self.test_session_id
            self.test_session_id = session_id
        
        print(f"🧹 Cleaning up test data from session: {self.test_session_id}")
        
        if not self.client and not self.connect():
            print("❌ Could not connect for cleanup")
            return False
        
        # Use the independent delete function to search and delete by session
        total_deleted = self._delete_existing_data()
        
        print(f"✅ Cleanup completed. Deleted {total_deleted} records")
        
        # Restore original session ID if it was changed
        if session_id:
            self.test_session_id = original_session_id
            
        return True

    def list_test_sessions(self):
        """List available test sessions - No longer needed since we don't use session files"""
        print("📋 Session files are no longer used. Use data.json configuration instead.")
        return []

    def get_test_credentials(self) -> List[Tuple[str, str]]:
        """Get list of test user credentials for load testing"""
        if not self.created_records["users"]:
            print("❌ No test users available")
            return []
        
        candidate_config = self.config["candidate_config"]
        credentials = []
        
        for i, user_name in enumerate(self.created_records["users"]):
            email = f"{candidate_config['first_name_prefix'].lower()}{i}_{self.test_session_id}{candidate_config['email_domain']}"
            password = candidate_config["default_password"]
            credentials.append((email, password))
        
        return credentials

    def get_exam_schedules(self) -> List[str]:
        """Get list of available exam schedules"""
        return self.created_records["schedules"].copy()


if __name__ == "__main__":
    import sys
    
    manager = TestDataManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "setup":
            manager.setup_test_data()
        elif command == "cleanup":
            if len(sys.argv) > 2:
                manager.cleanup_test_data(sys.argv[2])
            else:
                manager.cleanup_test_data()
        elif command == "list":
            manager.list_test_sessions()
        else:
            print("Usage: python test_data_manager.py [setup|cleanup|list] [session_id]")
    else:
        print("Usage: python test_data_manager.py [setup|cleanup|list] [session_id]")
