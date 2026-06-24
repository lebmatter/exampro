"""
Synchronized burst load test for ExamPro.

All candidates start the exam at the same instant and end at approximately
the same time, simulating a real fixed-schedule exam. Created test data
(users, submissions, schedule) is automatically cleaned up after the run.

Usage:
    python run_load_test.py \
        --url https://exam.example.com \
        --admin-user Administrator \
        --admin-password secret \
        --exam "My Exam" \
        --candidates 50
"""

import argparse
import functools
import json
import os
import random
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests

# Unbuffered print so output appears immediately in non-TTY contexts
print = functools.partial(print, flush=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_ok(response):
    if response.status_code != 200:
        return False
    try:
        body = response.json()
    except ValueError:
        return True
    if isinstance(body, dict) and body.get("exc_type"):
        return False
    return True


def _timed_request(session, method, url, **kwargs):
    start = time.perf_counter()
    resp = session.request(method, url, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return resp, elapsed_ms


def _percentile(data, p):
    if not data:
        return 0
    k = (len(data) - 1) * (p / 100)
    f = int(k)
    c = f + 1 if f + 1 < len(data) else f
    d = k - f
    return data[f] + d * (data[c] - data[f])


# ---------------------------------------------------------------------------
# Phase 1: Admin setup
# ---------------------------------------------------------------------------

def _admin_session(url, admin_user, admin_password):
    """Create an authenticated requests.Session for admin API calls."""
    s = requests.Session()
    r = s.post(f"{url}/api/method/login", data={"usr": admin_user, "pwd": admin_password})
    if r.status_code != 200:
        print(f"Admin login failed ({r.status_code}). Aborting.")
        sys.exit(1)
    csrf = s.cookies.get("csrf_token") or s.cookies.get("X-Frappe-CSRF-Token")
    if csrf:
        s.headers["X-Frappe-CSRF-Token"] = csrf
    return s


def setup_test_data(url, admin_user, admin_password, exam_name, num_candidates, candidate_password):
    admin = _admin_session(url, admin_user, admin_password)

    r = admin.get(f"{url}/api/resource/Exam/{exam_name}")
    if r.status_code != 200:
        print(f"Exam '{exam_name}' not found. Aborting.")
        sys.exit(1)
    exam = r.json().get("data", {})
    print(f"Exam found: {exam.get('title', exam_name)}")

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    num_batches = (num_candidates + 49) // 50
    if num_batches > 1:
        setup_buffer = num_batches * 75 + 60
    else:
        setup_buffer = 60
    schedule_start = datetime.now() + timedelta(seconds=setup_buffer)
    schedule_name = f"LoadTest_{session_id}"

    r = admin.post(f"{url}/api/resource/Exam Schedule", json={
        "name": schedule_name,
        "exam": exam_name,
        "start_date_time": schedule_start.strftime("%Y-%m-%d %H:%M:%S"),
        "schedule_type": "Fixed",
    })
    if r.status_code not in (200, 201):
        print(f"Failed to create exam schedule ({r.status_code}): {r.text[:200]}")
        sys.exit(1)
    schedule_name = r.json().get("data", {}).get("name", schedule_name)
    print(f"Schedule created: {schedule_name} (starts at {schedule_start.strftime('%H:%M:%S')})")

    credentials = []
    created_users = []
    # Frappe throttles: max 60 user creations per 60s sliding window.
    # The cooldown must exceed 60s + time-to-create-the-batch so even the
    # LAST user in the previous batch has aged out of the window.
    BATCH_SIZE = 50
    register_url = (
        f"{url}/api/method/exampro.exam_pro.doctype.exam_submission"
        f".exam_submission.register_candidate"
    )
    print(f"Creating {num_candidates} candidates...")
    batch_created = 0
    last_batch_end = 0.0
    for i in range(num_candidates):
        if batch_created >= BATCH_SIZE:
            # Wait until 65s after the LAST creation in this batch
            elapsed = time.time() - last_batch_end
            wait = max(0, 65 - elapsed)
            if wait > 0:
                print(f"  Throttle cooldown: waiting {int(wait)}s...")
                time.sleep(wait)
            batch_created = 0

        email = f"loadrunner{i}_{session_id}@loadtest.example.com"
        user_display = f"Runner{i:04d} LT{session_id[:8]}"

        ok = False
        for attempt in range(3):
            r = admin.post(register_url, json={
                "schedule": schedule_name,
                "user_email": email,
                "user_name": user_display,
            })
            if _api_ok(r):
                ok = True
                break
            if "Throttled" in (r.text or ""):
                print(f"  Throttled at user {i}, waiting 65s...")
                time.sleep(65)
            else:
                print(f"  register_candidate error: {r.text[:200]}")
                break

        if ok:
            created_users.append(email)
            batch_created += 1
            last_batch_end = time.time()
            admin.put(f"{url}/api/resource/User/{email}", json={
                "new_password": candidate_password,
            })
            credentials.append((email, candidate_password))
        else:
            print(f"  Failed to create user {email}")

        if (i + 1) % 50 == 0 or i + 1 == num_candidates:
            print(f"  {i + 1}/{num_candidates} created")

    if not credentials:
        print("No candidates registered successfully. Aborting.")
        sys.exit(1)

    print(f"{len(credentials)} candidates ready")
    return {
        "admin": admin,
        "url": url,
        "schedule_name": schedule_name,
        "schedule_start": schedule_start,
        "credentials": credentials,
        "created_users": created_users,
        "session_id": session_id,
    }


# ---------------------------------------------------------------------------
# Phase 2: Candidate execution
# ---------------------------------------------------------------------------

def run_candidate(url, email, password, barrier_start, barrier_end, think_time, index):
    result = {
        "candidate": email,
        "index": index,
        "login_ms": 0,
        "discover_ms": 0,
        "start_exam_ms": 0,
        "overview_ms": 0,
        "questions": [],
        "end_exam_ms": 0,
        "wall_time_ms": 0,
        "error": None,
    }
    wall_start = time.perf_counter()
    session = requests.Session()
    submission = None
    started = False

    try:
        # Login
        resp, ms = _timed_request(
            session, "POST", f"{url}/api/method/login",
            data={"usr": email, "pwd": password},
        )
        result["login_ms"] = ms
        if not _api_ok(resp):
            result["error"] = f"login failed ({resp.status_code})"
            return result

        csrf = session.cookies.get("csrf_token") or session.cookies.get("X-Frappe-CSRF-Token")
        if csrf:
            session.headers["X-Frappe-CSRF-Token"] = csrf

        # Discover submission
        resp, ms = _timed_request(
            session, "GET", f"{url}/api/method/frappe.client.get_list",
            params={
                "doctype": "Exam Submission",
                "filters": json.dumps([["candidate", "=", email]]),
                "fields": json.dumps(["name"]),
                "limit_page_length": 1,
                "order_by": "creation desc",
            },
        )
        result["discover_ms"] = ms
        if not _api_ok(resp):
            result["error"] = f"discover submission failed ({resp.status_code})"
            return result

        rows = resp.json().get("message", [])
        if not rows:
            result["error"] = "no submission found"
            return result
        submission = rows[0]["name"]

    except Exception as e:
        result["error"] = str(e)
        return result
    finally:
        try:
            barrier_start.wait(timeout=300)
        except threading.BrokenBarrierError:
            if not result["error"]:
                result["error"] = "start barrier broken"

    if result["error"]:
        try:
            barrier_end.wait(timeout=600)
        except threading.BrokenBarrierError:
            pass
        return result

    try:
        # Start exam
        resp, ms = _timed_request(
            session, "POST",
            f"{url}/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.start_exam",
            json={"exam_submission": submission},
        )
        result["start_exam_ms"] = ms
        if not _api_ok(resp):
            result["error"] = f"start_exam failed ({resp.status_code}): {resp.text[:200]}"
            return result
        started = True

        # Exam overview
        resp, ms = _timed_request(
            session, "POST",
            f"{url}/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.exam_overview",
            json={"exam_submission": submission},
        )
        result["overview_ms"] = ms
        total_questions = 1
        if _api_ok(resp):
            msg = resp.json().get("message", {})
            total_questions = int(msg.get("total_questions") or 1)

        # Answer loop
        for qsno in range(1, total_questions + 1):
            q_result = {"qsno": qsno, "get_ms": 0, "submit_ms": 0}

            resp, ms = _timed_request(
                session, "GET",
                f"{url}/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.get_question",
                params={"exam_submission": submission, "qsno": qsno},
            )
            q_result["get_ms"] = ms
            if not _api_ok(resp):
                result["questions"].append(q_result)
                continue

            qs_name = resp.json().get("message", {}).get("name")
            if not qs_name:
                result["questions"].append(q_result)
                continue

            if think_time > 0:
                time.sleep(think_time)

            resp, ms = _timed_request(
                session, "POST",
                f"{url}/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.submit_question_response",
                json={
                    "exam_submission": submission,
                    "qs_name": qs_name,
                    "answer": random.choice(["1", "2", "3", "4"]),
                    "markdflater": 0,
                    "qs_no": qsno,
                },
            )
            q_result["submit_ms"] = ms
            result["questions"].append(q_result)

    except Exception as e:
        result["error"] = str(e)
    finally:
        try:
            barrier_end.wait(timeout=600)
        except threading.BrokenBarrierError:
            pass

        if started and submission:
            try:
                resp, ms = _timed_request(
                    session, "POST",
                    f"{url}/api/method/exampro.exam_pro.doctype.exam_submission.exam_submission.end_exam",
                    json={"exam_submission": submission},
                )
                result["end_exam_ms"] = ms
            except Exception:
                pass

        result["wall_time_ms"] = (time.perf_counter() - wall_start) * 1000
        session.close()

    return result


def run_load_test(setup_data, think_time):
    creds = setup_data["credentials"]
    n = len(creds)
    url = setup_data["url"]

    # Wait for schedule start time
    now = datetime.now()
    wait_seconds = (setup_data["schedule_start"] - now).total_seconds()
    if wait_seconds > 0:
        print(f"Waiting {int(wait_seconds)}s for schedule start time...")
        while True:
            remaining = (setup_data["schedule_start"] - datetime.now()).total_seconds()
            if remaining <= 0:
                break
            print(f"  {int(remaining)}s remaining...", end="\r")
            time.sleep(min(remaining, 5))
        print()

    barrier_start = threading.Barrier(n, timeout=300)
    barrier_end = threading.Barrier(n, timeout=600)
    results = []

    print(f"Launching {n} candidate threads...")
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = {
            pool.submit(
                run_candidate, url, email, pwd,
                barrier_start, barrier_end, think_time, i,
            ): i
            for i, (email, pwd) in enumerate(creds)
        }
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            status = "OK" if not r["error"] else f"FAILED: {r['error'][:60]}"
            print(f"  [{r['index']:>4d}] {r['candidate'][:40]:<40s}  {status}")

    results.sort(key=lambda r: r["index"])
    return results


# ---------------------------------------------------------------------------
# Phase 3: Reporting
# ---------------------------------------------------------------------------

def print_results(results):
    succeeded = [r for r in results if not r["error"]]
    failed = [r for r in results if r["error"]]

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Candidates: {len(results)} ({len(succeeded)} succeeded, {len(failed)} failed)")
    print()

    if not succeeded:
        print("No successful candidates — skipping stats.")
        if failed:
            print("\nErrors:")
            for r in failed:
                print(f"  [{r['index']}] {r['candidate']}: {r['error']}")
        return

    def _collect(key):
        return sorted([r[key] for r in succeeded if r[key] > 0])

    def _collect_questions(key):
        vals = []
        for r in succeeded:
            for q in r["questions"]:
                if q[key] > 0:
                    vals.append(q[key])
        return sorted(vals)

    metrics = {
        "Login": _collect("login_ms"),
        "Start Exam": _collect("start_exam_ms"),
        "Overview": _collect("overview_ms"),
        "Get Question": _collect_questions("get_ms"),
        "Submit Answer": _collect_questions("submit_ms"),
        "End Exam": _collect("end_exam_ms"),
        "Wall Clock": _collect("wall_time_ms"),
    }

    header = f"{'Metric':<16s} {'Min':>8s} {'P50':>8s} {'P90':>8s} {'P95':>8s} {'Max':>8s} {'Avg':>8s} {'Count':>6s}"
    print(header)
    print("-" * len(header))
    for name, data in metrics.items():
        if not data:
            continue
        avg = statistics.mean(data)
        print(
            f"{name:<16s} "
            f"{_percentile(data, 0):>7.0f}ms "
            f"{_percentile(data, 50):>7.0f}ms "
            f"{_percentile(data, 90):>7.0f}ms "
            f"{_percentile(data, 95):>7.0f}ms "
            f"{_percentile(data, 100):>7.0f}ms "
            f"{avg:>7.0f}ms "
            f"{len(data):>5d}"
        )

    if failed:
        print(f"\nErrors ({len(failed)}):")
        for r in failed:
            print(f"  [{r['index']}] {r['candidate']}: {r['error']}")


# ---------------------------------------------------------------------------
# Phase 4: Cleanup
# ---------------------------------------------------------------------------

def cleanup(setup_data):
    admin = setup_data["admin"]
    url = setup_data["url"]
    schedule = setup_data["schedule_name"]
    users = setup_data["created_users"]
    deleted = 0

    print()
    print("Cleaning up test data...")

    # Delete submissions for this schedule
    try:
        r = admin.get(f"{url}/api/resource/Exam Submission", params={
            "filters": json.dumps([["exam_schedule", "=", schedule]]),
            "fields": json.dumps(["name"]),
            "limit_page_length": 0,
        })
        if r.status_code == 200:
            submissions = r.json().get("data", [])
            for sub in submissions:
                admin.delete(f"{url}/api/resource/Exam Submission/{sub['name']}")
                deleted += 1
            if submissions:
                print(f"  Deleted {len(submissions)} submissions")
    except Exception as e:
        print(f"  Failed to delete submissions: {e}")

    # Delete schedule
    try:
        r = admin.delete(f"{url}/api/resource/Exam Schedule/{schedule}")
        if r.status_code == 200 or r.status_code == 202:
            deleted += 1
            print(f"  Deleted schedule: {schedule}")
    except Exception as e:
        print(f"  Failed to delete schedule: {e}")

    # Delete users
    user_deleted = 0
    for email in users:
        try:
            r = admin.delete(f"{url}/api/resource/User/{email}")
            if r.status_code in (200, 202):
                user_deleted += 1
        except Exception:
            pass
    if user_deleted:
        print(f"  Deleted {user_deleted}/{len(users)} users")
        deleted += user_deleted

    print(f"Cleanup done ({deleted} records deleted)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Synchronized burst load test for ExamPro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            '  python run_load_test.py --url https://exam.example.com \\\n'
            '    --admin-user Administrator --admin-password secret \\\n'
            '    --exam "My Exam" --candidates 50 --think-time 0.5\n'
            "\n"
            "For sustained load profiling with gradual ramp-up, use Locust:\n"
            "  locust -f locustfile.py --host=https://exam.example.com \\\n"
            "         --users=50 --spawn-rate=10 --run-time=25m --headless"
        ),
    )
    p.add_argument("--url", "-u", required=True, help="Frappe site URL")
    p.add_argument("--admin-user", "-a", required=True, help="Admin username")
    p.add_argument("--admin-password", "-p", required=True, help="Admin password")
    p.add_argument("--exam", "-e", required=True, help="Name of existing exam")
    p.add_argument("--candidates", "-n", required=True, type=int, help="Number of candidates")
    p.add_argument("--password", default="TestPass123!", help="Candidate password (default: TestPass123!)")
    p.add_argument("--think-time", type=float, default=0.5, help="Seconds between answers (default: 0.5, 0=max throughput)")
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 70)
    print("ExamPro Synchronized Burst Load Test")
    print("=" * 70)
    print(f"Target:     {args.url}")
    print(f"Exam:       {args.exam}")
    print(f"Candidates: {args.candidates}")
    print(f"Think time: {args.think_time}s")
    print()

    setup_data = setup_test_data(
        args.url, args.admin_user, args.admin_password,
        args.exam, args.candidates, args.password,
    )

    try:
        results = run_load_test(setup_data, args.think_time)
        print_results(results)
    finally:
        cleanup(setup_data)


if __name__ == "__main__":
    main()
