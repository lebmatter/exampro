"""
ExamPro Load Testing with Locust
Comprehensive load testing for the entire exam taking experience
"""

import json
import random
import time
from loadtest import HttpUser, task, between, events
from locust.exception import StopUser
from typing import List, Dict, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExamTakerUser(HttpUser):
    """
    Simulates a user taking an exam in ExamPro
    """
    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_credentials = None
        self.current_exam_schedule = None
        self.current_submission = None
        self.exam_questions = []
        self.answered_questions = 0
        self.exam_started = False
        self.test_session_data = None

    def on_start(self):
        """Initialize user and login"""
        try:
            # Load test session data
            self.load_test_session_data()
            
            # Get user credentials
            self.get_user_credentials()
            
            # Login
            if self.login():
                logger.info(f"User {self.user_credentials[0]} logged in successfully")
            else:
                logger.error(f"Failed to login user {self.user_credentials[0]}")
                raise StopUser()
                
        except Exception as e:
            logger.error(f"Error in on_start: {str(e)}")
            raise StopUser()

    def load_test_session_data(self):
        """Load test session data"""
        try:
            # Try to find the latest test session file
            import glob
            session_files = glob.glob("test_session_*.json")
            
            if not session_files:
                raise Exception("No test session files found. Run test_data_manager.py setup first.")
            
            # Use the most recent session file
            latest_session = max(session_files)
            
            with open(latest_session, 'r') as f:
                self.test_session_data = json.load(f)
                
            logger.info(f"Loaded test session: {self.test_session_data['session_id']}")
            
        except Exception as e:
            logger.error(f"Failed to load test session data: {str(e)}")
            raise

    def get_user_credentials(self):
        """Get random user credentials for this test user"""
        try:
            users = self.test_session_data["created_records"]["users"]
            candidate_config = self.test_session_data["config"]["candidate_config"]
            session_id = self.test_session_data["session_id"]
            
            if not users:
                raise Exception("No test users available")
            
            # Select a random user
            user_index = random.randint(0, len(users) - 1)
            
            # Construct email based on the pattern used in test data creation
            email = f"{candidate_config['first_name_prefix'].lower()}{user_index}_{session_id}{candidate_config['email_domain']}"
            password = candidate_config["default_password"]
            
            self.user_credentials = (email, password)
            
        except Exception as e:
            logger.error(f"Failed to get user credentials: {str(e)}")
            raise

    def login(self) -> bool:
        """Login with test credentials"""
        try:
            email, password = self.user_credentials
            
            response = self.client.post("/api/method/login", data={
                "usr": email,
                "pwd": password
            }, name="Login")
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Login failed with status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return False

    @task(10)
    def view_my_exams(self):
        """View the my exams page"""
        with self.client.get("/my-exams", catch_response=True, name="View My Exams") as response:
            if response.status_code == 200 and "My Exams" in response.text:
                response.success()
            else:
                response.failure(f"Failed to load my exams page: {response.status_code}")

    @task(3)
    def view_leaderboard(self):
        """View leaderboard page"""
        with self.client.get("/leaderboard", catch_response=True, name="View Leaderboard") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to load leaderboard: {response.status_code}")

    @task(2)
    def view_exam_details(self):
        """View exam details page"""
        try:
            schedules = self.test_session_data["created_records"]["schedules"]
            if schedules:
                schedule = random.choice(schedules)
                with self.client.get(f"/exam?schedule={schedule}", 
                                   catch_response=True, name="View Exam Details") as response:
                    if response.status_code == 200:
                        response.success()
                    else:
                        response.failure(f"Failed to load exam details: {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not view exam details: {str(e)}")

    @task(15)
    def take_exam_flow(self):
        """Complete exam taking flow"""
        try:
            if not self.exam_started:
                self.start_exam()
            
            if self.exam_started and self.exam_questions:
                self.answer_questions()
                
                # Submit exam after answering all questions
                if self.answered_questions >= len(self.exam_questions):
                    self.submit_exam()
                    
        except Exception as e:
            logger.error(f"Error in exam flow: {str(e)}")

    def start_exam(self):
        """Start an exam"""
        try:
            schedules = self.test_session_data["created_records"]["schedules"]
            if not schedules:
                logger.warning("No exam schedules available")
                return
            
            schedule = random.choice(schedules)
            
            response = self.client.post(
                "/api/method/exampro.exam_pro.api.examops.start_exam",
                json={"schedule": schedule},
                name="Start Exam"
            )
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data and "submission" in data["message"]:
                    self.current_submission = data["message"]["submission"]
                    self.current_exam_schedule = schedule
                    self.exam_started = True
                    
                    # Get exam questions
                    self.get_exam_questions()
                    
                    logger.info(f"Started exam with submission: {self.current_submission}")
                else:
                    logger.warning("Unexpected response format from start_exam")
            else:
                logger.warning(f"Failed to start exam: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error starting exam: {str(e)}")

    def get_exam_questions(self):
        """Get questions for the current exam"""
        if not self.current_submission:
            return
        
        try:
            response = self.client.get(
                f"/api/method/exampro.exam_pro.api.examops.get_questions",
                params={"submission": self.current_submission},
                name="Get Exam Questions"
            )
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data and "questions" in data["message"]:
                    self.exam_questions = data["message"]["questions"]
                    self.answered_questions = 0
                    logger.info(f"Retrieved {len(self.exam_questions)} questions")
                else:
                    logger.warning("No questions found in response")
            else:
                logger.warning(f"Failed to get questions: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error getting questions: {str(e)}")

    def answer_questions(self):
        """Answer exam questions"""
        if not self.exam_questions or not self.current_submission:
            return
        
        # Answer 1-3 questions per task call
        questions_to_answer = min(
            random.randint(1, 3), 
            len(self.exam_questions) - self.answered_questions
        )
        
        for i in range(questions_to_answer):
            question_index = self.answered_questions + i
            if question_index >= len(self.exam_questions):
                break
                
            question = self.exam_questions[question_index]
            self.answer_single_question(question, question_index)
            
            # Simulate thinking time
            time.sleep(random.uniform(0.5, 2.0))
        
        self.answered_questions += questions_to_answer

    def answer_single_question(self, question: Dict, index: int):
        """Answer a single question"""
        try:
            # Generate appropriate answer based on question type
            answer = self.generate_answer(question)
            
            response = self.client.post(
                "/api/method/exampro.exam_pro.api.examops.submit_answer",
                json={
                    "submission": self.current_submission,
                    "question": question["name"],
                    "answer": answer
                },
                name="Submit Answer"
            )
            
            if response.status_code == 200:
                logger.debug(f"Answered question {index + 1}/{len(self.exam_questions)}")
            else:
                logger.warning(f"Failed to submit answer for question {index}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error answering question {index}: {str(e)}")

    def generate_answer(self, question: Dict) -> str:
        """Generate a realistic answer for a question"""
        question_type = question.get("type", "Choices")
        
        if question_type == "Choices":
            # For MCQ, select a random option
            options = []
            for i in range(1, 5):
                option_key = f"option_{i}"
                if option_key in question and question[option_key]:
                    options.append(question[option_key])
            
            if options:
                return random.choice(options)
            else:
                return "Option A"  # Fallback
                
        elif question_type == "True/False":
            return random.choice(["True", "False"])
            
        elif question_type == "Short Answer":
            sample_answers = [
                "This is a test answer for load testing purposes.",
                "Sample response generated for automated testing.",
                "Load test answer - checking system performance.",
                "Automated answer for stress testing the exam system."
            ]
            return random.choice(sample_answers)
            
        else:
            return "Default test answer"

    def submit_exam(self):
        """Submit the completed exam"""
        if not self.current_submission:
            return
        
        try:
            response = self.client.post(
                "/api/method/exampro.exam_pro.api.examops.submit_exam",
                json={"submission": self.current_submission},
                name="Submit Exam"
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully submitted exam: {self.current_submission}")
                
                # Reset exam state
                self.reset_exam_state()
                
                # View results after a short delay
                time.sleep(random.uniform(1, 3))
                self.view_exam_results()
                
            else:
                logger.warning(f"Failed to submit exam: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error submitting exam: {str(e)}")

    def view_exam_results(self):
        """View exam results"""
        if not self.current_submission:
            return
        
        try:
            with self.client.get(
                f"/exam/result?submission={self.current_submission}",
                catch_response=True,
                name="View Exam Results"
            ) as response:
                if response.status_code == 200:
                    response.success()
                    logger.debug("Viewed exam results successfully")
                else:
                    response.failure(f"Failed to view results: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error viewing results: {str(e)}")

    def reset_exam_state(self):
        """Reset exam state for next exam"""
        self.current_submission = None
        self.current_exam_schedule = None
        self.exam_questions = []
        self.answered_questions = 0
        self.exam_started = False

    @task(1)
    def check_proctor_page(self):
        """Check proctor page (if user has proctor role)"""
        with self.client.get("/proctor", catch_response=True, name="Check Proctor Page") as response:
            if response.status_code in [200, 403]:  # 403 expected if user is not a proctor
                response.success()
            else:
                response.failure(f"Unexpected proctor page response: {response.status_code}")

    @task(1)
    def check_evaluate_page(self):
        """Check evaluate page (if user has evaluator role)"""
        with self.client.get("/evaluate", catch_response=True, name="Check Evaluate Page") as response:
            if response.status_code in [200, 403]:  # 403 expected if user is not an evaluator
                response.success()
            else:
                response.failure(f"Unexpected evaluate page response: {response.status_code}")


# Event handlers for test lifecycle
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts"""
    print("🚀 Starting ExamPro load test...")
    print("📊 Test will simulate realistic exam taking behavior")
    print("⏱️ Users will login, view exams, take exams, and check results")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops"""
    print("✅ ExamPro load test completed")
    print("📈 Check Locust web UI for detailed performance metrics")

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, 
               context, exception, start_time, url, **kwargs):
    """Log slow requests"""
    if response_time > 5000:  # Log requests slower than 5 seconds
        logger.warning(f"Slow request: {name} took {response_time}ms")

# Additional user classes for different scenarios

class ExamCreatorUser(HttpUser):
    """
    Simulates an admin/teacher creating and managing exams
    """
    wait_time = between(2, 8)
    weight = 1  # Lower weight than exam takers
    
    def on_start(self):
        """Login as admin"""
        response = self.client.post("/api/method/login", data={
            "usr": "Administrator",
            "pwd": "admin"
        })
        
        if response.status_code != 200:
            raise StopUser()

    @task(3)
    def view_exam_dashboard(self):
        """View exam management dashboard"""
        with self.client.get("/app", catch_response=True, name="Admin Dashboard") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to load dashboard: {response.status_code}")

    @task(2)
    def manage_exams(self):
        """View and manage exams"""
        with self.client.get("/app/exam", catch_response=True, name="Manage Exams") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to load exam management: {response.status_code}")

    @task(1)
    def view_submissions(self):
        """View exam submissions"""
        with self.client.get("/app/exam-submission", catch_response=True, name="View Submissions") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to load submissions: {response.status_code}")


class ProctorUser(HttpUser):
    """
    Simulates a proctor monitoring exams
    """
    wait_time = between(5, 15)
    weight = 1  # Much lower weight than exam takers
    
    def on_start(self):
        """Login as proctor"""
        # This would need proctor credentials
        # For now, skip if no proctor users available
        pass

    @task(5)
    def monitor_exams(self):
        """Monitor ongoing exams"""
        with self.client.get("/proctor", catch_response=True, name="Monitor Exams") as response:
            if response.status_code in [200, 403]:
                response.success()
            else:
                response.failure(f"Proctor monitoring failed: {response.status_code}")

    @task(2)
    def view_flagged_sessions(self):
        """View flagged exam sessions"""
        with self.client.get("/proctor?view=flagged", catch_response=True, name="View Flagged Sessions") as response:
            if response.status_code in [200, 403]:
                response.success()
            else:
                response.failure(f"Failed to view flagged sessions: {response.status_code}")


if __name__ == "__main__":
    print("ExamPro Load Testing with Locust")
    print("================================")
    print()
    print("This file should be run with Locust:")
    print("locust -f locustfile.py --host=http://localhost:8000")
    print()
    print("Make sure to run test_data_manager.py setup first!")
