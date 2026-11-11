"""Subject page: previous year papers, ⭐ saved notes and the syllabus checklist."""
import io
import json
import unittest
from pathlib import Path

from test_phase1_security import UPLOAD_ROOT, PhaseOneSecurityTests, app, studenthub


def setUpModule():
    # The security tests delete their temporary folder when they finish; rebuild it.
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    studenthub.init_db()

DBMS = {
    "branch": "Computer Science Engineering",
    "year": "3rd Year",
    "semester": "Semester 5",
    "subject": "Database Management System",
}
FETCH = {"X-Requested-With": "fetch"}


class StudyToolsTests(PhaseOneSecurityTests):
    """Reuses the security tests' setup and helpers (see load_tests below)."""

    def seed_kind(self, kind="notes", **overrides):
        note_id = self.seed_note(**{"subject": DBMS["subject"], **overrides})
        with app.app_context():
            db = studenthub.get_db()
            db.execute("UPDATE study_notes SET kind = ? WHERE id = ?", (kind, note_id))
            db.commit()
        return note_id

    def progress(self, client, topic, done="1", code="BCS501", headers=FETCH):
        token = self.csrf_token(client, "/")
        return client.post("/syllabus/progress", headers=headers,
                           data={"csrf_token": token, "code": code, "topic": topic, "done": done})

    def test_every_catalog_subject_has_an_official_syllabus(self):
        codes = {s["code"] for subs in studenthub.AKTU_CATALOG["first_year"].values() for s in subs}
        for sems in studenthub.AKTU_CATALOG["semesters"].values():
            for subs in sems.values():
                codes |= {s["code"] for s in subs}
        for code in sorted(codes):
            with self.subTest(code=code):
                syllabus = studenthub.syllabus_for(code)
                self.assertIsNotNone(syllabus)
                self.assertRegex(syllabus["source_url"], r"^https://(fms\.)?aktu\.ac\.in/")
                self.assertGreaterEqual(len(syllabus["units"]), 4)
                for unit in syllabus["units"]:
                    self.assertTrue(unit["topics"])

    def test_subject_page_shows_notes_papers_and_syllabus(self):
        self.seed_kind("notes", title="Normalization Notes", stored_filename="n.pdf")
        self.seed_kind("pyq", title="2023-24 End Sem Paper", stored_filename="p.pdf")
        response = app.test_client().get("/notes/subject", query_string=DBMS)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Normalization Notes", body)
        self.assertIn("2023-24 End Sem Paper", body)
        # The paper is listed under previous year papers, after the notes.
        self.assertLess(body.index("Previous year papers"), body.index("2023-24 End Sem Paper"))
        self.assertLess(body.index("Normalization Notes"), body.index("Previous year papers"))
        first_unit = studenthub.syllabus_for("BCS501")["units"][0]
        self.assertIn(str(escape_text(first_unit["title"])), body)
        self.assertIn("official AKTU syllabus PDF", body)
        # Logged-out visitors can read the syllabus but not tick it.
        self.assertIn("disabled", body)
        self.assertNotIn("subject-save-form", body)
        # The subjects list links to the subject page and marks papers.
        listing = app.test_client().get("/notes/subjects", query_string={k: v for k, v in DBMS.items() if k != "subject"})
        listing_body = listing.get_data(as_text=True)
        self.assertIn("/notes/subject?", listing_body)
        self.assertIn('class="notes-paper-badge"', listing_body)

    def test_subject_page_rejects_unknown_subjects(self):
        client = app.test_client()
        response = client.get("/notes/subject", query_string={**DBMS, "subject": "Not A Real Subject"})
        self.assertEqual(response.status_code, 302)
        response = client.get("/notes/subject", query_string={**DBMS, "branch": "Nope"})
        self.assertEqual(response.status_code, 302)

    def test_syllabus_progress_is_saved_per_student(self):
        client = self.student_client()
        response = self.progress(client, "1.1")
        self.assertEqual(response.status_code, 200)
        total = len(studenthub.syllabus_topic_keys("BCS501"))
        self.assertEqual(response.get_json(), {"done": True, "studied": 1, "total": total})
        # Ticking twice doesn't double count.
        self.assertEqual(self.progress(client, "1.1").get_json()["studied"], 1)
        self.assertEqual(self.progress(client, "1.2").get_json()["studied"], 2)
        body = client.get("/notes/subject", query_string=DBMS).get_data(as_text=True)
        self.assertIn('data-topic="1.1" checked', body)
        account = client.get("/account").get_data(as_text=True)
        self.assertIn("Database Management System", account)
        self.assertIn(f"2 of {total} topics", account)
        self.assertEqual(self.progress(client, "1.1", done="0").get_json()["studied"], 1)
        # Another student starts from zero.
        other = app.test_client()
        self.register(other, email="other@example.com")
        self.assertEqual(self.progress(other, "2.1").get_json()["studied"], 1)

    def test_syllabus_progress_rejects_bad_input(self):
        client = self.student_client()
        self.assertEqual(self.progress(client, "99.1").status_code, 400)
        self.assertEqual(self.progress(client, "1.1", code="FAKE101").status_code, 400)
        no_token = client.post("/syllabus/progress", headers=FETCH,
                               data={"code": "BCS501", "topic": "1.1", "done": "1"})
        self.assertEqual(no_token.status_code, 400)
        anonymous = app.test_client()
        self.assertEqual(self.progress(anonymous, "1.1").status_code, 401)
        self.assertEqual(self.count_rows("topic_progress"), 0)

    def test_students_can_save_notes_to_their_account(self):
        note_id = self.seed_kind("notes", title="Saved Normalization", stored_filename="s.pdf")
        client = self.student_client()
        token = self.csrf_token(client, "/")
        response = client.post(f"/notes/{note_id}/save", headers=FETCH, data={"csrf_token": token})
        self.assertEqual(response.get_json(), {"saved": True})
        account = client.get("/account").get_data(as_text=True)
        self.assertIn("My saved notes", account)
        self.assertIn("Saved Normalization", account)
        page = client.get("/notes/subject", query_string=DBMS).get_data(as_text=True)
        self.assertIn('aria-pressed="true"', page)
        # Without JavaScript the form redirects back to a safe local page only.
        response = client.post(f"/notes/{note_id}/save", data={"csrf_token": token, "next": "//evil.com"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/account"))
        self.assertNotIn("Saved Normalization", client.get("/account").get_data(as_text=True))
        self.assertEqual(client.post("/notes/99999/save", data={"csrf_token": token}).status_code, 404)
        anonymous = app.test_client()
        token = self.csrf_token(anonymous, "/")
        self.assertEqual(anonymous.post(f"/notes/{note_id}/save", headers=FETCH, data={"csrf_token": token}).status_code, 401)

    def test_saved_notes_disappear_with_the_note(self):
        note_id = self.seed_kind("notes", stored_filename="gone.pdf")
        client = self.student_client()
        token = self.csrf_token(client, "/")
        client.post(f"/notes/{note_id}/save", headers=FETCH, data={"csrf_token": token})
        self.assertEqual(self.count_rows("saved_notes"), 1)
        with app.app_context():
            db = studenthub.get_db()
            db.execute("DELETE FROM study_notes WHERE id = ?", (note_id,))
            db.commit()
        self.assertEqual(self.count_rows("saved_notes"), 0)

    def test_owner_uploads_previous_year_papers(self):
        owner = app.test_client()
        self.login(owner)
        response = self.upload_note(owner, title="2022 Paper", kind="pyq")
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            row = studenthub.get_db().execute("SELECT kind FROM study_notes WHERE title = '2022 Paper'").fetchone()
        self.assertEqual(row["kind"], "pyq")
        response = self.upload_note(owner, title="Odd kind", kind="answers",
                                    file=(io.BytesIO(b"%PDF-1.4\n% test\n"), "odd.pdf"))
        self.assertIn("previous year paper", response.get_data(as_text=True))
        self.assertEqual(self.count_rows("study_notes", "title = ?", ("Odd kind",)), 0)
        self.assertIn('name="kind"', owner.get("/notes/upload").get_data(as_text=True))


def escape_text(value):
    from markupsafe import escape
    return escape(value)


def load_tests(loader, tests, pattern):
    # Run only the new tests here; the inherited ones already run in their own file.
    suite = unittest.TestSuite()
    for name in loader.getTestCaseNames(StudyToolsTests):
        if name in StudyToolsTests.__dict__:
            suite.addTest(StudyToolsTests(name))
    return suite
