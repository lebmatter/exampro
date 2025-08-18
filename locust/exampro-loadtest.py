#!/usr/bin/env python3
"""
ExamPro Single-File Load Test Script

Complete load testing workflow in a single file:
1. Setup test infrastructure from data.json
2. Run realistic exam load test using ExamPro APIs
3. Cleanup test data

Usage:
python exampro-loadtest.py --host=http://localhost:8000 --setup --users=10
python exampro-loadtest.py --host=http://localhost:8000 --test --users=10 --spawn-rate=2
python exampro-loadtest.py --host=http://localhost:8000 --cleanup
python exampro-loadtest.py --host=http://localhost:8000 --full --users=10 --spawn-rate=2
"""

import json
import os
import sys
import argparse
import subprocess
import time
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from frappeclient import FrappeClient
except ImportError:
    print("ERROR: frappe-client not found. Install with: pip install frappe-client")
    sys.exit(1)

# Default configuration
DEFAULT_CONFIG = {
    'ADMIN_USER': 'Administrator',
    'ADMIN_PASSWORD': 'admin',
    'VERIFY_SSL': False
}

class LoadTestManager:
    def __init__(self, host: str, admin_user: str = None, admin_password: str = None):
        self.host = host
        self.admin_user = admin_user or DEFAULT_CONFIG['ADMIN_USER']
        self.admin_password = admin_password or DEFAULT_CONFIG['ADMIN_PASSWORD']
        self.client = None
        self.test_id = None
        self.config_file = None
        self.resources = []  # (doctype, name) pairs for cleanup
        
    def connect(self):
        """Connect to Frappe site"""
        print(f"🔗 Connecting to {self.host}...")
        try:
            self.client = FrappeClient(self.host, verify=DEFAULT_CONFIG['VERIFY_SSL'])
            self.client.login(self.admin_user, self.admin_password)
            print(f"✅ Connected as {self.admin_user}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def load_test_data(self) -> Dict:
        """Load test data from data.json"""
        data_file = os.path.join(os.path.dirname(__file__), 'data.json')
        if not os.path.exists(data_file):
            print(f"❌ ERROR: data.json not found at {data_file}")
            sys.exit(1)
        
        with open(data_file, 'r') as f:
            return json.load(f)
    
    def generate_test_id(self) -> str:
        """Generate unique test ID"""
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"loadtest_{suffix}"
    
    def create_doc(self, doctype: str, data: Dict) -> Optional[str]:
        """Create document with error handling"""
        try:
            data['doctype'] = doctype
            doc = self.client.insert(data)
            name = doc.get('name')
            if name:
                self.resources.append((doctype, name))
                print(f"  ✅ Created {doctype}: {name}")
            return name
        except Exception as e:
            print(f"  ❌ Failed to create {doctype}: {e}")
            return None
    
    def setup_infrastructure(self, num_users: int = 10):
        """Setup complete test infrastructure"""
        if not self.connect():
            return False
        
        self.test_id = self.generate_test_id()
        print(f"🚀 Setting up test infrastructure (ID: {self.test_id})...")
        
        data = self.load_test_data()
        
        try:
            # 1. Create question category
            print("1️⃣ Creating question category...")
            category_name = f"LoadTest_Category_{self.test_id}"
            category_data = {"title": category_name}
            if not self.create_doc("Exam Question Category", category_data):
                raise Exception("Failed to create question category")
            
            # 2. Create questions from data.json
            print(f"2️⃣ Creating {len(data['questions'])} exam questions...")
            questions_created = 0
            for i, q in enumerate(data['questions']):
                question_data = {
                    "question": f"{q['question']} (LoadTest-{self.test_id})",
                    "type": "Choices",
                    "category": category_name,
                    "mark": 1,
                    "option_1": q['options'][0],
                    "option_2": q['options'][1],
                    "option_3": q['options'][2],
                    "option_4": q['options'][3],
                    "is_correct_1": 1 if q['correct'] == 0 else 0,
                    "is_correct_2": 1 if q['correct'] == 1 else 0,
                    "is_correct_3": 1 if q['correct'] == 2 else 0,
                    "is_correct_4": 1 if q['correct'] == 3 else 0,
                    "multiple": 0
                }
                if self.create_doc("Exam Question", question_data):
                    questions_created += 1
            
            if questions_created == 0:
                raise Exception("Failed to create any questions")
            print(f"  ✅ Created {questions_created} questions")
            
            # 3. Create exam using data.json config
            print("3️⃣ Creating exam...")
            exam_name = f"LoadTest_Exam_{self.test_id}"
            exam_config = data['exam_config']
            exam_data = {
                "title": f"{exam_config['title']} - {self.test_id}",
                "description": f"{exam_config['description']} (LoadTest-{self.test_id})",
                "duration": exam_config['duration_minutes'],
                "question_type": "Choices",
                "pass_percentage": exam_config['pass_percentage'],
                "randomize_questions": 1 if exam_config['randomize_questions'] else 0,
                "show_result": exam_config['show_result'],
                "max_warning_count": exam_config['max_warning_count'],
                "select_questions": [{
                    "question_category": category_name,
                    "no_of_questions": questions_created,
                    "mark_per_question": 1
                }]
            }
            created_exam = self.create_doc("Exam", exam_data)
            if not created_exam:
                raise Exception("Failed to create exam")
            
            # Verify exam was created and update exam_name to actual created name
            exam_name = created_exam
            print(f"  ✅ Exam created with name: {exam_name}")
            
            # Small delay to ensure exam is committed
            time.sleep(1)
            
            # 4. Create exam schedule using data.json config
            print("4️⃣ Creating exam schedule...")
            schedule_name = f"LoadTest_Schedule_{self.test_id}"
            schedule_config = data['schedule_config']
            start_time = datetime.now() + timedelta(seconds=schedule_config['start_delay_seconds'])
            schedule_data = {
                "name": schedule_name,  # Required for autoname: prompt
                "exam": exam_name,
                "start_date_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "schedule_type": schedule_config['schedule_type']
            }
            created_schedule = self.create_doc("Exam Schedule", schedule_data)
            if not created_schedule:
                raise Exception("Failed to create exam schedule")
            
            # Use actual created schedule name
            schedule_name = created_schedule
            print(f"  ✅ Schedule created with name: {schedule_name}")
            print(f"  📅 Exam starts at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Small delay to ensure schedule is committed
            time.sleep(1)
            
            # 5. Verify exam exists before creating submissions
            print("🔍 Verifying exam exists...")
            try:
                exam_doc = self.client.get_doc("Exam", exam_name)
                print(f"  ✅ Verified exam exists: {exam_name}")
            except Exception as e:
                raise Exception(f"Exam verification failed - exam may not exist: {e}")
            
            # 6. Create test users and submissions using data.json config
            print(f"6️⃣ Creating {num_users} test users and exam submissions...")
            user_config = data['user_config']
            users = []
            
            for i in range(num_users):
                user_suffix = f"{self.test_id}_{i+1:03d}"
                user_email = f"testuser_{user_suffix}@example.com"
                
                # Create user
                user_data = {
                    "email": user_email,
                    "first_name": f"TestUser{i+1:03d}",
                    "last_name": f"LoadTest_{self.test_id}",
                    "new_password": user_config['password'],
                    "enabled": 1,
                    "user_type": "System User",
                    "roles": [{"role": user_config['role']}]
                }
                if self.create_doc("User", user_data):
                    users.append({
                        "email": user_email, 
                        "password": user_config['password'],
                        "name": f"TestUser{i+1:03d}"
                    })
                
                # Create exam submission (no explicit name needed)
                submission_data = {
                    "exam_schedule": schedule_name,
                    "exam": exam_name,
                    "candidate": user_email,
                    "candidate_name": f"TestUser{i+1:03d} LoadTest_{self.test_id}",
                    "status": "Registered"
                }
                
                # Debug: print what we're trying to create
                print(f"    Creating submission for {user_email} with exam: {exam_name}")
                
                submission_name = self.create_doc("Exam Submission", submission_data)
                if submission_name:
                    # Store submission name for load testing
                    users[-1]["submission_name"] = submission_name
                else:
                    print(f"    ⚠️  Failed to create submission for {user_email}")
            
            print(f"  ✅ Created {len(users)} test users with exam submissions")
            
            # 7. Save test configuration
            print("7️⃣ Saving test configuration...")
            test_config = {
                "test_id": self.test_id,
                "host": self.host,
                "exam_name": exam_name,
                "exam_schedule": schedule_name,
                "exam_start_time": start_time.isoformat(),
                "exam_duration_minutes": exam_config['duration_minutes'],
                "num_questions": questions_created,
                "test_users": users,
                "resources": self.resources
            }
            
            self.config_file = f'test-config-{self.test_id}.json'
            with open(self.config_file, 'w') as f:
                json.dump(test_config, f, indent=2)
            
            print(f"✅ Test infrastructure ready!")
            print(f"📁 Config file: {self.config_file}")
            print(f"🔢 Test ID: {self.test_id}")
            print(f"👥 Users: {len(users)}")
            print(f"❓ Questions: {questions_created}")
            print(f"⏰ Exam starts: {start_time.strftime('%H:%M:%S')}")
            return True
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            print("🧹 Attempting cleanup of partial setup...")
            self.cleanup_resources()
            return False
    
    def run_locust_test(self, users: int, spawn_rate: int, run_time: str = "15m", headless: bool = True):
        """Run locust load test using ExamPro APIs"""
        if not self.config_file:
            # Find latest config file
            config_files = [f for f in os.listdir('.') if f.startswith('test-config-') and f.endswith('.json')]
            if not config_files:
                print("❌ No test configuration found. Run setup first.")
                return False
            self.config_file = sorted(config_files, key=lambda x: os.path.getmtime(x))[-1]
            print(f"📁 Using config file: {self.config_file}")
        
        print(f"🎯 Running load test with {users} users, spawn rate {spawn_rate}/s for {run_time}...")
        
        # Create realistic locust file that uses ExamPro APIs
        locust_content = f'''
import json
import random
import time
from datetime import datetime
from locust import HttpUser, task, between

class ExamProUser(HttpUser):
    wait_time = between(1, 3)  # Shorter wait for synchronized exam taking
    
    def on_start(self):
        """Setup user for exam taking"""
        # Load test config
        with open("{self.config_file}") as f:
            self.config = json.load(f)
        
        # Get assigned user
        self.user_data = random.choice(self.config["test_users"])
        self.submission_name = self.user_data.get("submission_name")
        self.questions_answered = 0
        self.current_question_no = 1
        self.total_questions = self.config["num_questions"]
        self.exam_started = False
        self.exam_ended = False
        self.start_exam_called = False
        self.exam_duration_minutes = self.config["exam_duration_minutes"]
        self.exam_start_time = None
        
        # Login as test user
        self.login()
        
        # Wait for exam start time (synchronized)
        self.wait_for_exam_start()
        
        # Start the exam (once only)
        self.start_exam()
    
    def login(self):
        """Login as test user"""
        response = self.client.post("/api/method/login", json={{
            "usr": self.user_data["email"],
            "pwd": self.user_data["password"]
        }}, name="Login")
        
        if response.status_code == 200:
            print(f"✅ Logged in as {{self.user_data['email']}}")
        else:
            print(f"❌ Login failed for {{self.user_data['email']}}")
    
    def wait_for_exam_start(self):
        """Wait for scheduled exam start time - synchronized across all users"""
        exam_start_time = datetime.fromisoformat(self.config['exam_start_time'])
        current_time = datetime.now()
        
        if current_time < exam_start_time:
            wait_seconds = (exam_start_time - current_time).total_seconds()
            if wait_seconds > 0:
                print(f"⏰ Waiting {{wait_seconds:.0f}} seconds for synchronized exam start...")
                # Add small random offset (max 2 seconds) to avoid all hitting server at exact same millisecond
                jitter = random.uniform(0, 2)
                time.sleep(wait_seconds + jitter)
    
    def start_exam(self):
        """Start the exam using ExamPro API - called exactly once"""
        if self.start_exam_called or not self.submission_name:
            return
            
        self.start_exam_called = True
        response = self.client.post("/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.start_exam", 
                                  json={{"exam_submission": self.submission_name}},
                                  name="Start Exam")
        
        if response.status_code == 200:
            self.exam_started = True
            self.exam_start_time = time.time()
            print(f"🚀 Started exam: {{self.submission_name}} at {{datetime.now().strftime('%H:%M:%S')}}")
        else:
            print(f"❌ Failed to start exam: {{response.status_code}}")
    
    def should_end_exam(self):
        """Check if exam should end based on time or completion"""
        if not self.exam_started or self.exam_ended:
            return False
            
        # Check if exam time is over
        if self.exam_start_time:
            elapsed_minutes = (time.time() - self.exam_start_time) / 60
            if elapsed_minutes >= self.exam_duration_minutes:
                return True
        
        # Check if all questions answered
        if self.questions_answered >= self.total_questions:
            return True
            
        return False
    
    @task(4)
    def get_question(self):
        """Get current question using ExamPro API"""
        if not self.exam_started or self.exam_ended or self.current_question_no > self.total_questions:
            return
            
        # Check if exam should end before getting question
        if self.should_end_exam():
            self.end_exam()
            return
            
        response = self.client.post("/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.get_question",
                                  json={{
                                      "exam_submission": self.submission_name,
                                      "qsno": self.current_question_no
                                  }},
                                  name="Get Question")
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get("message"):
                    print(f"📝 Got question {{self.current_question_no}} for {{self.user_data['email']}}")
            except:
                pass
    
    @task(3)
    def submit_answer(self):
        """Submit answer using ExamPro API"""
        if not self.exam_started or self.exam_ended or self.current_question_no > self.total_questions:
            return
            
        # Check if exam should end before submitting answer
        if self.should_end_exam():
            self.end_exam()
            return
        
        # First get question to get its name
        response = self.client.post("/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.get_question",
                                  json={{
                                      "exam_submission": self.submission_name,
                                      "qsno": self.current_question_no
                                  }},
                                  name="Get Question for Submit")
        
        if response.status_code == 200:
            try:
                result = response.json()
                question_data = result.get("message")
                if question_data and question_data.get("name"):
                    question_name = question_data["name"]
                    
                    # Submit random answer
                    answer_choices = ["option_1", "option_2", "option_3", "option_4"]
                    selected_answer = random.choice(answer_choices)
                    
                    submit_response = self.client.post("/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.submit_question_response",
                                                     json={{
                                                         "exam_submission": self.submission_name,
                                                         "qs_name": question_name,
                                                         "answer": selected_answer,
                                                         "markdflater": 0
                                                     }},
                                                     name="Submit Answer")
                    
                    if submit_response.status_code == 200:
                        self.questions_answered += 1
                        self.current_question_no = min(self.current_question_no + 1, self.total_questions)
                        print(f"✅ Submitted answer {{self.questions_answered}}/{{self.total_questions}} for {{self.user_data['email']}}")
                        
                        # Check if this was the last question
                        if self.should_end_exam():
                            self.end_exam()
            except Exception as e:
                print(f"❌ Error submitting answer: {{e}}")
    
    @task(1)
    def check_exam_status(self):
        """Check exam status and handle automatic ending"""
        if not self.exam_started or self.exam_ended:
            return
            
        # Check if exam should end
        if self.should_end_exam():
            self.end_exam()
            return
            
        # Simple status check
        response = self.client.get(f"/api/resource/Exam Submission/{{self.submission_name}}", 
                                 name="Check Status")
    
    def end_exam(self):
        """End the exam using ExamPro API - called exactly once"""
        if not self.exam_started or self.exam_ended:
            return
            
        self.exam_ended = True
        response = self.client.post("/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.end_exam",
                                  json={{"exam_submission": self.submission_name}},
                                  name="End Exam")
        
        if response.status_code == 200:
            elapsed_minutes = (time.time() - self.exam_start_time) / 60 if self.exam_start_time else 0
            print(f"🏁 Ended exam for {{self.user_data['email']}} at {{datetime.now().strftime('%H:%M:%S')}}")
            print(f"   Completed {{self.questions_answered}}/{{self.total_questions}} questions in {{elapsed_minutes:.1f}} minutes")
            self.exam_started = False
            
            # Stop this user from continuing tasks
            self.interrupt()
        else:
            print(f"❌ Failed to end exam: {{response.status_code}}")
    
    def on_stop(self):
        """Cleanup when user stops"""
        if self.exam_started and not self.exam_ended:
            self.end_exam()
'''
        
        with open('locustfile.py', 'w') as f:
            f.write(locust_content)
        
        cmd = ['locust', '--host', self.host]
        if headless:
            cmd.extend(['--users', str(users), '--spawn-rate', str(spawn_rate), 
                       '--run-time', run_time, '--headless'])
        else:
            print(f"🌐 Open http://localhost:8089 for interactive control")
            print(f"📊 Recommended settings: Users={users}, Spawn rate={spawn_rate}")
        
        try:
            print(f"🚀 Starting locust: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True)
            print("✅ Load test completed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Load test failed: {e}")
            return False
        except KeyboardInterrupt:
            print("⚠️  Load test interrupted by user")
            return True
        finally:
            # Clean up locustfile
            if os.path.exists('locustfile.py'):
                os.remove('locustfile.py')
    
    def cleanup_resources(self):
        """Clean up all created test resources"""
        if not self.client:
            if not self.connect():
                return False
        
        if not self.resources:
            # Load from config file
            if self.config_file and os.path.exists(self.config_file):
                with open(self.config_file) as f:
                    config = json.load(f)
                    self.resources = config.get('resources', [])
        
        if not self.resources:
            print("⚠️  No resources to cleanup")
            return True
        
        print(f"🧹 Cleaning up {len(self.resources)} resources...")
        cleaned = 0
        
        # Delete in reverse order for dependencies
        for doctype, name in reversed(self.resources):
            try:
                self.client.delete(doctype, name)
                print(f"  ✅ Deleted {doctype}: {name}")
                cleaned += 1
            except Exception as e:
                print(f"  ⚠️  Failed to delete {doctype} {name}: {e}")
        
        print(f"✅ Cleanup completed: {cleaned}/{len(self.resources)} resources deleted")
        
        # Clean up config file
        if self.config_file and os.path.exists(self.config_file):
            os.remove(self.config_file)
            print(f"📁 Removed config file: {self.config_file}")
        
        # Clean up locustfile if exists
        if os.path.exists('locustfile.py'):
            os.remove('locustfile.py')
            print("📁 Removed locustfile.py")
        
        return True

def main():
    parser = argparse.ArgumentParser(description="ExamPro Single-File Load Test")
    parser.add_argument("--host", required=True, help="Frappe site URL")
    parser.add_argument("--admin-user", help="Admin username (default: Administrator)")
    parser.add_argument("--admin-password", help="Admin password (default: admin)")
    parser.add_argument("--setup", action="store_true", help="Setup test infrastructure")
    parser.add_argument("--test", action="store_true", help="Run load test")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup test data")
    parser.add_argument("--full", action="store_true", help="Run complete workflow (setup + test + cleanup)")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users (default: 10)")
    parser.add_argument("--spawn-rate", type=int, default=2, help="Users to spawn per second (default: 2)")
    parser.add_argument("--run-time", default="15m", help="Test duration (default: 15m)")
    parser.add_argument("--interactive", action="store_true", help="Run locust in interactive mode")
    
    args = parser.parse_args()
    
    if not any([args.setup, args.test, args.cleanup, args.full]):
        print("❌ Specify one of: --setup, --test, --cleanup, --full")
        sys.exit(1)
    
    manager = LoadTestManager(args.host, args.admin_user, args.admin_password)
    
    try:
        if args.full:
            print("🚀 Running complete load test workflow...")
            print("=" * 60)
            
            # Setup
            if not manager.setup_infrastructure(args.users):
                print("❌ Setup failed. Aborting.")
                sys.exit(1)
            
            print("\n⏳ Brief pause before starting load test...")
            time.sleep(5)
            
            # Test
            if not manager.run_locust_test(args.users, args.spawn_rate, args.run_time, not args.interactive):
                print("❌ Load test failed.")
                sys.exit(1)
            
            # Cleanup
            print("\n🧹 Starting cleanup...")
            manager.cleanup_resources()
            print("\n🎉 Complete workflow finished successfully!")
            
        elif args.setup:
            print("🚀 Setting up test infrastructure...")
            if not manager.setup_infrastructure(args.users):
                sys.exit(1)
                
        elif args.test:
            print("🎯 Running load test...")
            if not manager.run_locust_test(args.users, args.spawn_rate, args.run_time, not args.interactive):
                sys.exit(1)
                
        elif args.cleanup:
            print("🧹 Cleaning up test data...")
            manager.cleanup_resources()
            
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()