"""
ExamPro Load Testing with Locust — candidate exam-taking workload.

Each simulated candidate drives the *same* HTTP traffic a real browser would:
  - login + session establish
  - one start_exam + exam_overview to discover total questions
  - then, for the configured exam duration:
      * answer loop:   GET get_question -> "thinking" sleep -> POST submit_question_response
      * video loop:    POST get_video_upload_url -> POST presigned multipart to S3/R2
      * tracking loop: POST post_tracking_info
  - end_exam once when the duration elapses

The video and tracking loops fake their bytes/numbers — the server can't tell
the difference because it only ever talks HTTP, not to a camera. See README.md.
"""

import io
import json
import os
import random
import time
import uuid

import requests
from locust import HttpUser, events, task
from locust.exception import StopUser

# --------------------------------------------------------------------------
# Module-level configuration (load once, not per request)
# --------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "data.json"), "r") as _f:
    CONFIG = json.load(_f)

TEST_CONFIG = CONFIG["test_config"]
CANDIDATE_CONFIG = CONFIG["candidate_config"]

SESSION_ID = TEST_CONFIG["session_id"]
NUM_CANDIDATES = TEST_CONFIG["num_candidates"]
EXAM_DURATION_SECONDS = int(TEST_CONFIG["exam_duration_minutes"]) * 60

# Cadences (seconds) — match the real browser exam form.
VIDEO_CHUNK_INTERVAL_S = 10
TRACKING_INTERVAL_S = 15
ANSWER_INTERVAL_MIN_S = 25
ANSWER_INTERVAL_MAX_S = 60

# Fake video chunk — ~80 KB of random bytes. S3/R2 policy enforces 1..10 MB
# and content-type=video/webm; the bytes themselves are not validated.
FAKE_VIDEO_CHUNK = os.urandom(80 * 1024)

# Atomic counter used to hand each spawned Locust user a unique candidate
# index, so two users never race for the same submission. Wraps if more
# users are spawned than seeded candidates.
_user_counter = {"n": 0}


def _next_candidate_index() -> int:
    n = _user_counter["n"]
    _user_counter["n"] = n + 1
    return n % NUM_CANDIDATES


def _api_ok(response) -> bool:
    """Frappe sometimes returns 200 with an error envelope. Treat those as failures."""
    if response.status_code != 200:
        return False
    try:
        body = response.json()
    except ValueError:
        return True  # non-JSON 200 (e.g., HTML page) — assume ok
    if isinstance(body, dict) and body.get("exc_type"):
        return False
    return True


# --------------------------------------------------------------------------
# CandidateUser
# --------------------------------------------------------------------------


class CandidateUser(HttpUser):
    """
    Simulates one candidate taking the exam end-to-end. Uses a single @task
    that's a time-driven dispatcher rather than relying on Locust's wait
    distribution — we need precise 10s/15s/30s cadences per loop.
    """

    # wait_time intentionally minimal: the dispatcher does its own pacing.
    def wait_time(self):
        return 0.5

    # ----- lifecycle -------------------------------------------------------

    def on_start(self):
        self.candidate_index = _next_candidate_index()
        self.email = (
            f"{CANDIDATE_CONFIG['first_name_prefix'].lower()}"
            f"{self.candidate_index}_{SESSION_ID}"
            f"{CANDIDATE_CONFIG['email_domain']}"
        )
        self.password = CANDIDATE_CONFIG["default_password"]

        self.submission = None
        self.total_questions = 0
        self.exam_proctoring = False
        self.exam_ended = False
        self.qsno = 1

        # Separate Session for S3/R2 uploads so Frappe cookies never leak to
        # the storage host.
        self._s3_session = requests.Session()

        if not self._login():
            raise StopUser()

        if not self._discover_submission():
            raise StopUser()

        if not self._start_exam():
            raise StopUser()

        self._fetch_exam_overview()

        now = time.time()
        self.deadline = now + EXAM_DURATION_SECONDS
        self.next_video = now + VIDEO_CHUNK_INTERVAL_S if self.exam_proctoring else float("inf")
        self.next_tracking = now + TRACKING_INTERVAL_S if self.exam_proctoring else float("inf")
        self.next_answer = now + random.uniform(2, 6)

    def on_stop(self):
        try:
            self._s3_session.close()
        except Exception:
            pass

    # ----- login + setup ---------------------------------------------------

    def _login(self) -> bool:
        with self.client.post(
            "/api/method/login",
            data={"usr": self.email, "pwd": self.password},
            name="01 login",
            catch_response=True,
        ) as r:
            if not _api_ok(r):
                r.failure(f"login failed: {r.status_code} {r.text[:200]}")
                return False
            r.success()

        # Pick up Frappe's CSRF token if the site sets it as a cookie, so
        # later whitelisted POSTs work on sites with CSRF enforcement on.
        csrf = self.client.cookies.get("csrf_token") or self.client.cookies.get("X-Frappe-CSRF-Token")
        if csrf:
            self.client.headers["X-Frappe-CSRF-Token"] = csrf
        return True

    def _discover_submission(self) -> bool:
        """Find this candidate's own Exam Submission via the standard list API."""
        with self.client.get(
            "/api/method/frappe.client.get_list",
            params={
                "doctype": "Exam Submission",
                "filters": json.dumps([["candidate", "=", self.email]]),
                "fields": json.dumps(["name", "exam", "exam_schedule", "status"]),
                "limit_page_length": 1,
                "order_by": "creation desc",
            },
            name="02 list submissions",
            catch_response=True,
        ) as r:
            if not _api_ok(r):
                r.failure(f"list submissions: {r.status_code} {r.text[:200]}")
                return False
            rows = r.json().get("message", [])
            if not rows:
                r.failure(f"no submission for candidate {self.email}")
                return False
            self.submission = rows[0]["name"]
            self.exam = rows[0]["exam"]
            r.success()
            return True

    def _start_exam(self) -> bool:
        with self.client.post(
            "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.start_exam",
            json={"exam_submission": self.submission},
            name="03 start_exam",
            catch_response=True,
        ) as r:
            if not _api_ok(r):
                # Already-started returns True via the server, that's fine.
                r.failure(f"start_exam: {r.status_code} {r.text[:200]}")
                return False
            r.success()
            return True

    def _fetch_exam_overview(self):
        with self.client.post(
            "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.exam_overview",
            json={"exam_submission": self.submission},
            name="04 exam_overview",
            catch_response=True,
        ) as r:
            if not _api_ok(r):
                r.failure(f"exam_overview: {r.status_code} {r.text[:200]}")
                self.total_questions = 1
                return
            msg = r.json().get("message", {})
            self.total_questions = int(msg.get("total_questions") or 1)
            r.success()

        # Cheap probe to find out whether proctoring is enabled — we only run
        # the video/tracking loops if it is.
        with self.client.get(
            "/api/method/frappe.client.get_value",
            params={
                "doctype": "Exam",
                "filters": json.dumps({"name": self.exam}),
                "fieldname": json.dumps(["enable_video_proctoring"]),
            },
            name="05 exam proctoring flag",
            catch_response=True,
        ) as r:
            if _api_ok(r):
                msg = r.json().get("message") or {}
                self.exam_proctoring = bool(msg.get("enable_video_proctoring"))
                r.success()
            else:
                r.failure(f"get_value Exam: {r.status_code} {r.text[:200]}")

    # ----- driving loops ---------------------------------------------------

    @task
    def tick(self):
        if self.exam_ended:
            raise StopUser()

        now = time.time()
        if now >= self.deadline:
            self._end_exam()
            return

        if now >= self.next_video:
            self._video_chunk_cycle()
            self.next_video = now + VIDEO_CHUNK_INTERVAL_S

        if now >= self.next_tracking:
            self._post_tracking()
            self.next_tracking = now + TRACKING_INTERVAL_S

        if now >= self.next_answer:
            self._answer_one_question()
            self.next_answer = now + random.uniform(ANSWER_INTERVAL_MIN_S, ANSWER_INTERVAL_MAX_S)

    # ----- answer flow -----------------------------------------------------

    def _answer_one_question(self):
        qsno = self.qsno
        qs_name = self._get_question(qsno)
        if not qs_name:
            return
        # "thinking" time
        time.sleep(random.uniform(2, 6))
        self._submit_answer(qsno, qs_name)
        self.qsno = (qsno % max(self.total_questions, 1)) + 1

    def _get_question(self, qsno):
        with self.client.get(
            "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.get_question",
            params={"exam_submission": self.submission, "qsno": qsno},
            name="10 get_question",
            catch_response=True,
        ) as r:
            if not _api_ok(r):
                r.failure(f"get_question: {r.status_code} {r.text[:200]}")
                return None
            msg = r.json().get("message", {})
            r.success()
            # `name` is the real Exam Question docname — needed by submit.
            return msg.get("name")

    def _submit_answer(self, qsno, qs_name):
        # Realistic-ish answer: for multiple choice the server expects
        # "1"/"2"/"3"/"4"; harmless garbage for user-input questions.
        answer = random.choice(["1", "2", "3", "4"])
        with self.client.post(
            "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.submit_question_response",
            json={
                "exam_submission": self.submission,
                "qs_name": qs_name,
                "answer": answer,
                "markdflater": 0,
                "qs_no": qsno,
            },
            name="11 submit_question_response",
            catch_response=True,
        ) as r:
            if not _api_ok(r):
                r.failure(f"submit_question_response: {r.status_code} {r.text[:200]}")
            else:
                r.success()

    # ----- proctoring loops ------------------------------------------------

    def _post_tracking(self):
        payload = {
            "exam_submission": self.submission,
            "faceCountChanges": random.randint(0, 2),
            "totalAwayTime": round(random.uniform(0, 1.5), 3),
            "totalDistractedTime": round(random.uniform(0, 1.0), 3),
            "retinaLocations": [
                {
                    "x": round(random.uniform(-1, 1), 3),
                    "y": round(random.uniform(-1, 1), 3),
                    "t": int(time.time() * 1000),
                }
                for _ in range(random.randint(5, 15))
            ],
        }
        with self.client.post(
            "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.post_tracking_info",
            json={"info": json.dumps(payload)},
            name="20 post_tracking_info",
            catch_response=True,
        ) as r:
            if not _api_ok(r):
                r.failure(f"post_tracking_info: {r.status_code} {r.text[:200]}")
            else:
                r.success()

    def _video_chunk_cycle(self):
        presigned = self._mint_video_upload_url()
        if not presigned:
            return
        self._put_video_chunk(presigned)

    def _mint_video_upload_url(self):
        with self.client.post(
            "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.get_video_upload_url",
            json={
                "exam_submission": self.submission,
                "chunk_size": len(FAKE_VIDEO_CHUNK),
            },
            name="30 get_video_upload_url",
            catch_response=True,
        ) as r:
            if not _api_ok(r):
                # Rate-limit hits become "expected" failures during burst — record
                # but don't spam the failure column.
                txt = (r.text or "")[:200]
                if "TooManyRequests" in txt or "too frequently" in txt:
                    r.success()
                    return None
                r.failure(f"get_video_upload_url: {r.status_code} {txt}")
                return None
            msg = r.json().get("message")
            r.success()
            return msg if isinstance(msg, dict) else None

    def _put_video_chunk(self, presigned):
        url = presigned.get("url")
        if not url:
            return
        headers = dict(presigned.get("headers") or {"Content-Type": "video/webm"})

        start = time.perf_counter()
        exc = None
        status = 0
        length = 0
        try:
            resp = self._s3_session.put(
                url, data=FAKE_VIDEO_CHUNK, headers=headers, timeout=30
            )
            status = resp.status_code
            length = len(resp.content or b"")
            if status >= 300:
                exc = Exception(f"s3 status {status}: {resp.text[:200]}")
        except Exception as e:
            exc = e
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Fire into Locust's stats so the S3 leg shows up alongside Frappe calls.
        events.request.fire(
            request_type="PUT",
            name="31 s3 video PUT",
            response_time=elapsed_ms,
            response_length=length,
            response=None,
            context={},
            exception=exc,
        )

    # ----- end -------------------------------------------------------------

    def _end_exam(self):
        if self.exam_ended:
            return
        self.exam_ended = True
        with self.client.post(
            "/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.end_exam",
            json={"exam_submission": self.submission},
            name="40 end_exam",
            catch_response=True,
        ) as r:
            if not _api_ok(r):
                r.failure(f"end_exam: {r.status_code} {r.text[:200]}")
            else:
                r.success()


# --------------------------------------------------------------------------
# Lifecycle banners
# --------------------------------------------------------------------------


@events.test_start.add_listener
def _on_test_start(environment, **kwargs):
    print(
        f"Starting ExamPro candidate load test — session={SESSION_ID}, "
        f"seeded candidates={NUM_CANDIDATES}, exam duration={EXAM_DURATION_SECONDS}s"
    )


@events.test_stop.add_listener
def _on_test_stop(environment, **kwargs):
    print("ExamPro candidate load test stopped.")


if __name__ == "__main__":
    print(
        "Run with Locust:\n"
        "  locust -f locustfile.py --host=https://exam.example.com \\\n"
        "         --users=500 --spawn-rate=20 --run-time=25m --headless"
    )
