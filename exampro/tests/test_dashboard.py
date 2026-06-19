# Copyright (c) 2024, Labeeb Mattra and Contributors
# See license.txt

from datetime import datetime, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase

from exampro.www.dashboard import _proctor_items, _evaluator_items, get_context
from exampro.www.proctor import get_proctor_upcoming_events
from exampro.www.evaluate import get_evaluator_live_exams


def _create_user(email, roles=None):
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
    else:
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": email.split("@")[0],
                "send_welcome_email": 0,
            }
        )
        user.insert(ignore_permissions=True)
    existing_roles = {r.role for r in user.roles}
    for role_name in roles or []:
        if role_name not in existing_roles:
            user.add_roles(role_name)
    return user


def _create_question_category(title):
    if frappe.db.exists("Exam Question Category", {"title": title}):
        return frappe.get_doc("Exam Question Category", {"title": title})
    doc = frappe.get_doc({"doctype": "Exam Question Category", "title": title})
    doc.insert(ignore_permissions=True)
    return doc


def _create_question(category, mark=1, qtype="Choices"):
    doc = frappe.get_doc(
        {
            "doctype": "Exam Question",
            "question": f"<p>Test question {frappe.generate_hash(length=4)}</p>",
            "type": qtype,
            "category": category,
            "mark": mark,
            "option_1": "A",
            "is_correct_1": 1,
            "option_2": "B",
            "is_correct_2": 0,
            "option_3": "C",
            "is_correct_3": 0,
            "option_4": "D",
            "is_correct_4": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def _create_exam(title, duration=60, category=None, num_questions=1, mark_per_q=1):
    doc = frappe.get_doc(
        {
            "doctype": "Exam",
            "title": title,
            "duration": duration,
            "pass_percentage": 50,
            "question_type": "Choices",
            "description": f"<p>Test exam: {title}</p>",
            "select_questions": [
                {
                    "question_category": category,
                    "no_of_questions": num_questions,
                    "mark_per_question": mark_per_q,
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def _create_schedule(exam, start_dt, duration=None, examiners=None):
    children = []
    for ex in examiners or []:
        children.append(
            {
                "examiner": ex["user"],
                "can_proctor": ex.get("proctor", 0),
                "can_evaluate": ex.get("evaluate", 0),
            }
        )
    sched_name = f"test-sched-{frappe.generate_hash(length=6)}"
    doc = frappe.get_doc(
        {
            "doctype": "Exam Schedule",
            "name": sched_name,
            "exam": exam,
            "start_date_time": start_dt,
            "schedule_type": "Fixed",
            "examiners": children,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    return doc


def _create_submission(schedule, candidate, proctor=None, evaluator=None, status="Registered"):
    doc = frappe.get_doc(
        {
            "doctype": "Exam Submission",
            "exam_schedule": schedule,
            "candidate": candidate,
            "status": status,
        }
    )
    doc.insert(ignore_permissions=True)
    if proctor:
        frappe.db.set_value("Exam Submission", doc.name, "assigned_proctor", proctor)
    if evaluator:
        frappe.db.set_value("Exam Submission", doc.name, "assigned_evaluator", evaluator)
    if status == "Submitted":
        frappe.db.set_value(
            "Exam Submission",
            doc.name,
            {
                "evaluation_status": "Pending",
                "exam_submitted_time": frappe.utils.now_datetime(),
            },
        )
    frappe.db.commit()
    return frappe.get_doc("Exam Submission", doc.name)


class TestDashboardSetup(FrappeTestCase):
    """Shared fixtures for dashboard tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # users
        cls.proctor_user = _create_user(
            "test-proctor@example.com", ["Exam Proctor"]
        )
        cls.evaluator_user = _create_user(
            "test-evaluator@example.com", ["Exam Evaluator"]
        )
        cls.candidate_1 = _create_user("test-cand1@example.com", ["Exam Candidate"])
        cls.candidate_2 = _create_user("test-cand2@example.com", ["Exam Candidate"])
        cls.candidate_3 = _create_user("test-cand3@example.com", ["Exam Candidate"])

        # question bank
        cls.category = _create_question_category("Dashboard Test Category")
        for _ in range(5):
            _create_question(cls.category.name, mark=1)

        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        # clean up test data in reverse dependency order
        for dt in [
            "Exam Submission",
            "Exam Schedule",
            "Exam",
            "Exam Question",
            "Exam Question Category",
        ]:
            names = frappe.get_all(
                dt,
                filters={"owner": "Administrator"},
                pluck="name",
            )
            for n in names:
                try:
                    frappe.delete_doc(dt, n, force=True, ignore_permissions=True)
                except Exception:
                    pass

        for email in [
            "test-proctor@example.com",
            "test-evaluator@example.com",
            "test-cand1@example.com",
            "test-cand2@example.com",
            "test-cand3@example.com",
        ]:
            if frappe.db.exists("User", email):
                frappe.delete_doc("User", email, force=True, ignore_permissions=True)

        frappe.db.commit()
        super().tearDownClass()


class TestProctorUpcoming(TestDashboardSetup):
    """Proctor sees multiple upcoming exams on the dashboard."""

    def test_single_upcoming_event(self):
        tomorrow = frappe.utils.now_datetime() + timedelta(days=1)
        exam = _create_exam(
            "Proctor Single Test",
            category=self.category.name,
            num_questions=1,
        )
        sched = _create_schedule(
            exam.name,
            tomorrow,
            examiners=[{"user": self.proctor_user.name, "proctor": 1}],
        )
        _create_submission(sched.name, self.candidate_1.name, proctor=self.proctor_user.name)

        events = get_proctor_upcoming_events(proctor=self.proctor_user.name)
        matching = [e for e in events if e["schedule_name"] == sched.name]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["candidate_count"], 1)
        self.assertEqual(matching[0]["exam_title"], "Proctor Single Test")

    def test_multiple_upcoming_events(self):
        """Two exams scheduled on different days both show up."""
        now_dt = frappe.utils.now_datetime()
        exam_a = _create_exam("Proctor Multi A", category=self.category.name, num_questions=1)
        exam_b = _create_exam("Proctor Multi B", category=self.category.name, num_questions=1)

        sched_a = _create_schedule(
            exam_a.name,
            now_dt + timedelta(days=2),
            examiners=[{"user": self.proctor_user.name, "proctor": 1}],
        )
        sched_b = _create_schedule(
            exam_b.name,
            now_dt + timedelta(days=5),
            examiners=[{"user": self.proctor_user.name, "proctor": 1}],
        )
        _create_submission(sched_a.name, self.candidate_1.name, proctor=self.proctor_user.name)
        _create_submission(sched_b.name, self.candidate_2.name, proctor=self.proctor_user.name)

        events = get_proctor_upcoming_events(proctor=self.proctor_user.name)
        sched_names = {e["schedule_name"] for e in events}
        self.assertIn(sched_a.name, sched_names)
        self.assertIn(sched_b.name, sched_names)

    def test_upcoming_excludes_past_schedules(self):
        """A schedule in the past does not appear as upcoming."""
        yesterday = frappe.utils.now_datetime() - timedelta(days=1)
        exam = _create_exam("Proctor Past Test", category=self.category.name, num_questions=1)
        sched = _create_schedule(
            exam.name,
            yesterday,
            examiners=[{"user": self.proctor_user.name, "proctor": 1}],
        )
        _create_submission(sched.name, self.candidate_1.name, proctor=self.proctor_user.name)

        events = get_proctor_upcoming_events(proctor=self.proctor_user.name)
        sched_names = {e["schedule_name"] for e in events}
        self.assertNotIn(sched.name, sched_names)

    def test_upcoming_excludes_beyond_7_days(self):
        """A schedule more than 7 days away does not appear."""
        far_future = frappe.utils.now_datetime() + timedelta(days=10)
        exam = _create_exam("Proctor Far Test", category=self.category.name, num_questions=1)
        sched = _create_schedule(
            exam.name,
            far_future,
            examiners=[{"user": self.proctor_user.name, "proctor": 1}],
        )
        _create_submission(sched.name, self.candidate_1.name, proctor=self.proctor_user.name)

        events = get_proctor_upcoming_events(proctor=self.proctor_user.name)
        sched_names = {e["schedule_name"] for e in events}
        self.assertNotIn(sched.name, sched_names)

    def test_proctor_items_builds_upcoming_cards(self):
        """_proctor_items() returns cards in the upcoming list."""
        tomorrow = frappe.utils.now_datetime() + timedelta(days=1)
        exam = _create_exam("Proctor Card Test", category=self.category.name, num_questions=1)
        sched = _create_schedule(
            exam.name,
            tomorrow,
            examiners=[{"user": self.proctor_user.name, "proctor": 1}],
        )
        _create_submission(sched.name, self.candidate_1.name, proctor=self.proctor_user.name)
        _create_submission(sched.name, self.candidate_2.name, proctor=self.proctor_user.name)

        frappe.set_user(self.proctor_user.name)
        try:
            _live, upcoming = _proctor_items()
        finally:
            frappe.set_user("Administrator")

        titles = [c["title"] for c in upcoming]
        self.assertIn("Proctor Card Test", titles)
        card = next(c for c in upcoming if c["title"] == "Proctor Card Test")
        self.assertIn("2 candidates", card["description"])
        self.assertEqual(card["role_label"], "Proctoring")

    def test_cancelled_submissions_excluded_from_count(self):
        """Cancelled/aborted submissions are not counted."""
        tomorrow = frappe.utils.now_datetime() + timedelta(days=1)
        exam = _create_exam("Proctor Cancel Test", category=self.category.name, num_questions=1)
        sched = _create_schedule(
            exam.name,
            tomorrow,
            examiners=[{"user": self.proctor_user.name, "proctor": 1}],
        )
        _create_submission(sched.name, self.candidate_1.name, proctor=self.proctor_user.name)
        _create_submission(
            sched.name,
            self.candidate_2.name,
            proctor=self.proctor_user.name,
            status="Registration Cancelled",
        )

        events = get_proctor_upcoming_events(proctor=self.proctor_user.name)
        matching = [e for e in events if e["schedule_name"] == sched.name]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["candidate_count"], 1)


class TestEvaluatorLive(TestDashboardSetup):
    """Evaluator sees multiple exams with pending evaluations on dashboard."""

    def test_single_pending_evaluation(self):
        past = frappe.utils.now_datetime() - timedelta(hours=2)
        exam = _create_exam("Eval Single Test", category=self.category.name, num_questions=1)
        sched = _create_schedule(
            exam.name,
            past,
            examiners=[{"user": self.evaluator_user.name, "evaluate": 1}],
        )
        _create_submission(
            sched.name,
            self.candidate_1.name,
            evaluator=self.evaluator_user.name,
            status="Submitted",
        )

        results = get_evaluator_live_exams(evaluator=self.evaluator_user.name)
        exam_names = {r.name for r in results}
        self.assertIn(exam.name, exam_names)

    def test_multiple_pending_evaluations_different_exams(self):
        """Two different exams with pending evaluations both appear."""
        past = frappe.utils.now_datetime() - timedelta(hours=2)
        exam_a = _create_exam("Eval Multi A", category=self.category.name, num_questions=1)
        exam_b = _create_exam("Eval Multi B", category=self.category.name, num_questions=1)

        sched_a = _create_schedule(
            exam_a.name,
            past,
            examiners=[{"user": self.evaluator_user.name, "evaluate": 1}],
        )
        sched_b = _create_schedule(
            exam_b.name,
            past - timedelta(hours=1),
            examiners=[{"user": self.evaluator_user.name, "evaluate": 1}],
        )
        _create_submission(
            sched_a.name,
            self.candidate_1.name,
            evaluator=self.evaluator_user.name,
            status="Submitted",
        )
        _create_submission(
            sched_b.name,
            self.candidate_2.name,
            evaluator=self.evaluator_user.name,
            status="Submitted",
        )

        results = get_evaluator_live_exams(evaluator=self.evaluator_user.name)
        exam_names = {r.name for r in results}
        self.assertIn(exam_a.name, exam_names)
        self.assertIn(exam_b.name, exam_names)

    def test_evaluator_items_builds_live_cards(self):
        """_evaluator_items() returns cards in the live list, not upcoming."""
        past = frappe.utils.now_datetime() - timedelta(hours=2)
        exam = _create_exam("Eval Card Test", category=self.category.name, num_questions=1)
        sched = _create_schedule(
            exam.name,
            past,
            examiners=[{"user": self.evaluator_user.name, "evaluate": 1}],
        )
        _create_submission(
            sched.name,
            self.candidate_1.name,
            evaluator=self.evaluator_user.name,
            status="Submitted",
        )
        _create_submission(
            sched.name,
            self.candidate_2.name,
            evaluator=self.evaluator_user.name,
            status="Submitted",
        )

        frappe.set_user(self.evaluator_user.name)
        try:
            live, upcoming = _evaluator_items()
        finally:
            frappe.set_user("Administrator")

        self.assertEqual(len(upcoming), 0, "Evaluator should have no upcoming items")
        titles = [c["title"] for c in live]
        self.assertIn("Eval Card Test", titles)
        card = next(c for c in live if c["title"] == "Eval Card Test")
        self.assertIn("2 submissions", card["description"])
        self.assertEqual(card["role_label"], "Evaluation")
        self.assertEqual(card["start_time_display"], "Ready now")

    def test_evaluator_excludes_expired_evaluations(self):
        """Submissions past the evaluation deadline are excluded."""
        long_ago = frappe.utils.now_datetime() - timedelta(days=30)
        exam = _create_exam("Eval Expired Test", category=self.category.name, num_questions=1)
        sched = _create_schedule(
            exam.name,
            long_ago,
            examiners=[{"user": self.evaluator_user.name, "evaluate": 1}],
        )
        sub = _create_submission(
            sched.name,
            self.candidate_1.name,
            evaluator=self.evaluator_user.name,
            status="Submitted",
        )
        # backdate the submitted time so evaluation window has expired
        frappe.db.set_value(
            "Exam Submission", sub.name, "exam_submitted_time", long_ago
        )
        frappe.db.commit()

        results = get_evaluator_live_exams(evaluator=self.evaluator_user.name)
        sub_ids = {r.submission_id for r in results}
        self.assertNotIn(sub.name, sub_ids)

    def test_multiple_submissions_same_schedule_grouped(self):
        """Multiple submissions for same schedule produce one card."""
        past = frappe.utils.now_datetime() - timedelta(hours=2)
        exam = _create_exam("Eval Group Test", category=self.category.name, num_questions=1)
        sched = _create_schedule(
            exam.name,
            past,
            examiners=[{"user": self.evaluator_user.name, "evaluate": 1}],
        )
        _create_submission(
            sched.name,
            self.candidate_1.name,
            evaluator=self.evaluator_user.name,
            status="Submitted",
        )
        _create_submission(
            sched.name,
            self.candidate_2.name,
            evaluator=self.evaluator_user.name,
            status="Submitted",
        )
        _create_submission(
            sched.name,
            self.candidate_3.name,
            evaluator=self.evaluator_user.name,
            status="Submitted",
        )

        frappe.set_user(self.evaluator_user.name)
        try:
            live, _ = _evaluator_items()
        finally:
            frappe.set_user("Administrator")

        cards_for_sched = [c for c in live if c["title"] == "Eval Group Test"]
        self.assertEqual(len(cards_for_sched), 1, "Should group by schedule into one card")
        self.assertIn("3 submissions", cards_for_sched[0]["description"])


class TestDashboardContext(TestDashboardSetup):
    """get_context() merges proctor + evaluator + candidate items."""

    def test_proctor_upcoming_in_context(self):
        """Proctor upcoming exams appear in context.upcoming_items."""
        tomorrow = frappe.utils.now_datetime() + timedelta(days=1)
        exam = _create_exam("Ctx Proctor Test", category=self.category.name, num_questions=1)
        sched = _create_schedule(
            exam.name,
            tomorrow,
            examiners=[{"user": self.proctor_user.name, "proctor": 1}],
        )
        _create_submission(sched.name, self.candidate_1.name, proctor=self.proctor_user.name)

        frappe.set_user(self.proctor_user.name)
        try:
            ctx = frappe._dict()
            ctx.metatags = {}
            get_context(ctx)
        finally:
            frappe.set_user("Administrator")

        upcoming_titles = [c["title"] for c in ctx.upcoming_items]
        self.assertIn("Ctx Proctor Test", upcoming_titles)
        self.assertGreaterEqual(ctx.upcoming_count, 1)

    def test_evaluator_live_in_context(self):
        """Evaluator live exams appear in context.live_items."""
        past = frappe.utils.now_datetime() - timedelta(hours=2)
        exam = _create_exam("Ctx Eval Test", category=self.category.name, num_questions=1)
        sched = _create_schedule(
            exam.name,
            past,
            examiners=[{"user": self.evaluator_user.name, "evaluate": 1}],
        )
        _create_submission(
            sched.name,
            self.candidate_1.name,
            evaluator=self.evaluator_user.name,
            status="Submitted",
        )

        frappe.set_user(self.evaluator_user.name)
        try:
            ctx = frappe._dict()
            ctx.metatags = {}
            get_context(ctx)
        finally:
            frappe.set_user("Administrator")

        live_titles = [c["title"] for c in ctx.live_items]
        self.assertIn("Ctx Eval Test", live_titles)
        self.assertGreaterEqual(ctx.live_count, 1)

    def test_dual_role_user_sees_both(self):
        """A user with both proctor and evaluator roles sees both."""
        dual_user = _create_user(
            "test-dual@example.com", ["Exam Proctor", "Exam Evaluator"]
        )
        try:
            now_dt = frappe.utils.now_datetime()

            # upcoming proctor exam
            exam_p = _create_exam("Dual Proctor Exam", category=self.category.name, num_questions=1)
            sched_p = _create_schedule(
                exam_p.name,
                now_dt + timedelta(days=1),
                examiners=[{"user": dual_user.name, "proctor": 1}],
            )
            _create_submission(sched_p.name, self.candidate_1.name, proctor=dual_user.name)

            # live evaluator exam
            exam_e = _create_exam("Dual Eval Exam", category=self.category.name, num_questions=1)
            sched_e = _create_schedule(
                exam_e.name,
                now_dt - timedelta(hours=2),
                examiners=[{"user": dual_user.name, "evaluate": 1}],
            )
            _create_submission(
                sched_e.name,
                self.candidate_2.name,
                evaluator=dual_user.name,
                status="Submitted",
            )

            frappe.set_user(dual_user.name)
            try:
                ctx = frappe._dict()
                ctx.metatags = {}
                get_context(ctx)
            finally:
                frappe.set_user("Administrator")

            upcoming_titles = [c["title"] for c in ctx.upcoming_items]
            live_titles = [c["title"] for c in ctx.live_items]
            self.assertIn("Dual Proctor Exam", upcoming_titles)
            self.assertIn("Dual Eval Exam", live_titles)
        finally:
            if frappe.db.exists("User", "test-dual@example.com"):
                frappe.delete_doc("User", "test-dual@example.com", force=True, ignore_permissions=True)
