"""
ExamPro Load Testing with Locust
Candidate-focused load testing for exam taking experience
"""

import json
import random
import time
from locust import HttpUser, task, between, events
from locust.exception import StopUser
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CandidateUser(HttpUser):
    """
    Simulates a candidate taking an exam in ExamPro
    Workflow: Login -> /my-exams -> /exam -> start_exam -> get_question/submit_question_response (loop) -> end_exam
    """
    wait_time = between(2, 8)  # Wait 2-8 seconds between tasks
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_credentials = None
        self.current_submission = None
        self.exam_started = False
        self.exam_completed = False
        self.question_count = 0
        self.answered_questions = 0
        self.exam_duration_minutes = 30  # Default exam duration

    def on_start(self):
        """Initialize candidate and login"""
        try:
            # Get random candidate credentials from data.json
            self.get_candidate_credentials()
            
            # Login
            if self.login():
                logger.info(f"Candidate {self.user_credentials[0]} logged in successfully")
                # Start the exam workflow
                # self.exam_workflow()
            else:
                logger.error(f"Failed to login candidate {self.user_credentials[0]}")
                raise StopUser()
                
        except Exception as e:
            logger.error(f"Error in candidate initialization: {str(e)}")
            raise StopUser()

    def get_candidate_credentials(self):
        """Get random candidate credentials from data.json"""
        try:
            with open('data.json', 'r') as f:
                data = json.load(f)
            
            candidate_config = data["candidate_config"]
            session_id = data["test_config"]["session_id"]
            num_candidates = data["test_config"]["num_candidates"]
            
            # Generate random candidate index
            candidate_index = random.randint(0, num_candidates - 1)
            
            # Construct email based on the pattern
            email = f"{candidate_config['first_name_prefix'].lower()}{candidate_index}_{session_id}{candidate_config['email_domain']}"
            password = candidate_config["default_password"]
            
            self.user_credentials = (email, password)
            self.exam_duration_minutes = data["test_config"]["exam_duration_minutes"]
            
        except Exception as e:
            logger.error(f"Failed to get candidate credentials: {str(e)}")
            raise

    def login(self) -> bool:
        """Login with candidate credentials"""
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
    def assign_my_exam_data(self):
        """Find the EXACT submission and schedule assigned to this logged-in user from data.json"""
        try:
            email = self.user_credentials[0].lower()
            with open('data.json', 'r') as f:
                data = json.load(f)
            
            exam_submissions = data.get("Exam Submission", {}).get("data", [])
            
            # Find the submission that matches this specific user's email
            my_submission = next((sub for sub in exam_submissions if sub.get("candidate").lower() == email), None)
            
            if my_submission:
                self.current_submission = my_submission["name"]
                self.current_schedule = my_submission["exam_schedule"]
                return True
            else:
                logger.error(f"Could not find submission mapping for {email} in data.json")
                return False
        except Exception as e:
            logger.error(f"Error reading submission from data.json: {e}")
            return False
   
    @task
    def exam_workflow(self):
        """Execute the complete exam workflow for a candidate"""
        if getattr(self, 'exam_completed', False):
            raise StopUser()
        try:
            # Step 1: Access /my-exams
            self.access_my_exams()

            if not self.assign_my_exam_data():
                return
            
            # Step 2: Go to /exam (single page app)
            self.access_exam_page()
            
            # Step 3: Start exam (once per candidate)
            self.start_exam()
            
            # Step 4: Take the exam (get_question and submit_question_response repeatedly)
            if self.exam_started:
                self.take_exam()
            
            # Step 5: End exam (once per candidate)
            if self.exam_started and not self.exam_completed:
                self.end_exam()
                self.exam_completed = True
                logger.info(f"Candidate {self.user_credentials[0]} finished. Stopping user.")
                raise StopUser()
                
        except StopUser:
            # Locust uses exceptions to stop users, so we must let it pass through
            raise
        except Exception as e:
            logger.error(f"Error in exam workflow: {str(e)}")

    def access_my_exams(self):
        """Access the my-exams page"""
        with self.client.get("/my-exams", catch_response=True, name="Access My Exams") as response:
            if response.status_code == 200:
                response.success()
                logger.debug("Successfully accessed my-exams page")
            else:
                response.failure(f"Failed to load my-exams page: {response.status_code}")

    def access_exam_page(self):
        """Access the exam single page application"""
        if hasattr(self, 'current_schedule') and self.current_schedule:
            with self.client.get(f"/exam?schedule={self.current_schedule}", 
                               catch_response=True, name="Access Exam Page") as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Failed to load exam page: {response.status_code}")

    def start_exam(self):
        """Start an exam using the user's assigned submission ID"""
        if not self.current_submission:
            return
            
        try:
            with self.client.post(
                "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.start_exam",
                json={"exam_submission": self.current_submission},
                name="Start Exam API",
                catch_response=True
            ) as response:
                if response.status_code == 200:
                    self.exam_started = True
                    response.success()
                    logger.info(f"Successfully started exam: {self.current_submission}")
                else:
                    # Capture exact Frappe error text for debugging
                    response.failure(f"Failed to start exam 417: {response.text}")
                    
        except Exception as e:
            logger.error(f"Error starting exam: {str(e)}")

    def take_exam(self):
        """Take the exam by getting questions and submitting responses"""
        # Simulate taking the exam for the configured duration
        exam_duration_seconds = self.exam_duration_minutes * 60
        start_time = time.time()
        
        # Initialize question tracking
        self.question_count = 15  # Default number of questions
        current_question = 1
        
        while (time.time() - start_time) < exam_duration_seconds and not self.exam_completed:
            # Get current question
            self.get_question(current_question)
            
            # Simulate thinking time (1-10 seconds)
            time.sleep(random.uniform(1, 10))
            
            # Submit answer for current question
            self.submit_question_response(current_question)
            
            current_question += 1
            self.answered_questions += 1
            
            # If we've answered all questions, mark exam as ready for completion
            if current_question > self.question_count:
                current_question = 1  # Loop back to first question for continuous load
            
            # Add some variation in timing between questions
            time.sleep(random.uniform(0.5, 3))

    # @task(20)  # High frequency task - this is where most traffic goes
    def get_question(self, qsno=None):
        """Get a specific question (API call - high frequency)"""
        if not self.exam_started or not self.current_submission:
            return
        
        if qsno is None:
            qsno = random.randint(1, self.question_count)
        
        try:
            with self.client.get(
                "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.get_question",
                params={
                    "exam_submission": self.current_submission,
                    "qsno": qsno
                },
                name="Get Question API",
                catch_response=True
            ) as response:
            
                if response.status_code == 200:
                    try:
                        data = response.json().get("message", {})
                        self.current_qs_name = data.get("name")
                        response.success()
                        logger.debug(f"Retrieved question {qsno}")
                    except:
                        pass
                elif response.status_code == 417 and ("has ended" in response.text or "submitted" in response.text):
                    self.exam_completed = True
                    response.success()
                else:
                    response.failure(f"Failed to get question {qsno}: {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting question {qsno}: {str(e)}")

    # @task(15)  # High frequency task - this is where most traffic goes  
    def submit_question_response(self, qsno=None):
        """Submit response to a question (API call - high frequency)"""
        if not self.exam_started or not self.current_submission:
            return

        qs_name = getattr(self, 'current_qs_name', None)
        if not qs_name:
            return

        if qsno is None:
            qsno = random.randint(1, self.question_count)
        
        try:
            # Generate a realistic answer
            answer = self.generate_realistic_answer()
            
            with self.client.post(
                "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.submit_question_response",
                json={
                    "exam_submission": self.current_submission,
                    "qs_name": qs_name,  
                    # This needs to be actual question name
                    "answer": answer,
                    "markdflater": 0,
                    "qs_no": qsno
                },
                name="Submit Question Response API",
                catch_response=True
            ) as response:
            
                if response.status_code == 200:
                    response.success()
                    logger.debug(f"Submitted answer for question {qsno}")
                elif response.status_code == 417 and ("has ended" in response.text or "submitted" in response.text):
                    self.exam_completed = True
                    response.success()
                else:
                    response.failure(f"Failed to submit answer for question {qsno}: {response.text}")
                
        except Exception as e:
            logger.error(f"Error submitting answer for question {qsno}: {str(e)}")

    def generate_realistic_answer(self) -> str:
        """Generate realistic answers for different question types"""
        # Simulate different types of answers
        answer_types = [
            "Option A", "Option B", "Option C", "Option D",  # Multiple choice
            "True", "False",  # True/False
            "This is a sample answer for load testing.",  # Short answer
            "Load testing answer with some detail to simulate real usage."
        ]
        return random.choice(answer_types)

    def end_exam(self):
        """End the exam (API call - once per candidate)"""
        if not self.current_submission:
            return
        
        try:
            response = self.client.post(
                "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.end_exam",
                json={"exam_submission": self.current_submission},
                name="End Exam API"
            )
            
            if response.status_code == 200:
                self.exam_completed = True
                logger.info(f"Successfully ended exam for submission: {self.current_submission}")
            else:
                logger.warning(f"Failed to end exam: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error ending exam: {str(e)}")


# Event handlers for test lifecycle
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts"""
    print("🚀 Starting ExamPro Candidate Load Test...")
    print("📊 Simulating candidate exam taking workflow")
    print("🔄 Workflow: Login -> /my-exams -> /exam -> start_exam -> get_question/submit_response (loop) -> end_exam")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops"""
    print("✅ ExamPro Candidate Load Test completed")
    print("📈 Check Locust web UI for detailed performance metrics")

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, 
               context, exception, start_time, url, **kwargs):
    """Log slow requests"""
    if response_time > 5000:  # Log requests slower than 5 seconds
        logger.warning(f"Slow request: {name} took {response_time}ms")


if __name__ == "__main__":
    print("ExamPro Candidate Load Testing with Locust")
    print("==========================================")
    print()
    print("This file should be run with Locust:")
    print("locust -f locustfile.py --host=http://localhost:8000")
    print()
    print("Make sure your data.json has test data!")
