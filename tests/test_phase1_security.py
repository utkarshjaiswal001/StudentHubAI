r"""Focused regression tests for the Phase 1 security fixes.

Run from the project root:
    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

The tests import the Flask app with DATABASE_PATH and UPLOAD_FOLDER pointed at a
throwaway temporary directory, so the real instance database and uploads are
never touched.
"""

import atexit
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = Path(tempfile.mkdtemp(prefix="studenthub-tests-"))
UPLOAD_ROOT = TEMP_ROOT / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_PATH"] = str(TEMP_ROOT / "test.sqlite3")
os.environ["UPLOAD_FOLDER"] = str(UPLOAD_ROOT)
os.environ["SECRET_KEY"] = "phase1-test-secret"
os.environ["OWNER_EMAIL"] = "owner@example.com"
os.environ["OPENAI_API_KEY"] = ""
os.environ["SESSION_COOKIE_SECURE"] = "false"

sys.path.insert(0, str(PROJECT_ROOT))

import app as studenthub  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app = studenthub.app


def tearDownModule():
    shutil.rmtree(TEMP_ROOT, ignore_errors=True)


atexit.register(shutil.rmtree, TEMP_ROOT, ignore_errors=True)


class PhaseOneSecurityTests(unittest.TestCase):
    OWNER_EMAIL = "owner@example.com"
    OWNER_PASSWORD = "owner-password-123"

    def setUp(self):
        app.config.update(TESTING=True, OWNER_EMAIL=self.OWNER_EMAIL)
        with app.app_context():
            db = studenthub.get_db()
            for table in (
                "mentor_messages",
                "mentor_conversations",
                "note_activity",
                "study_notes",
                "suggestions",
                "users",
            ):
                db.execute(f"DELETE FROM {table}")
            cursor = db.execute(
                "INSERT INTO users (name, email, college, branch, year, password_hash, is_owner) "
                "VALUES (?, ?, ?, ?, ?, ?, 1)",
                (
                    "Notes Owner",
                    self.OWNER_EMAIL,
                    "Test College",
                    "Computer Science Engineering",
                    "3rd Year",
                    generate_password_hash(self.OWNER_PASSWORD),
                ),
            )
            db.commit()
            self.owner_id = cursor.lastrowid

        for path in UPLOAD_ROOT.iterdir():
            if path.is_file():
                path.unlink()

    # ------------------------------------------------------------------ helpers
    def register_payload(self, **overrides):
        data = {
            "name": "Test Student",
            "email": "student@example.com",
            "college": "Test College",
            "branch": "Computer Science",
            "year": "1st Year",
            "password": "student-password",
            "confirm_password": "student-password",
        }
        data.update(overrides)
        return data

    def csrf_token(self, client, path="/login"):
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        with client.session_transaction() as session:
            token = session.get("csrf_token")
        self.assertTrue(token)
        return token

    def login(self, client, email=None, password=None, next_value=None):
        email = email or self.OWNER_EMAIL
        password = password or self.OWNER_PASSWORD
        token = self.csrf_token(client)
        query = {"next": next_value} if next_value is not None else None
        return client.post(
            "/login",
            query_string=query,
            data={"email": email, "password": password, "csrf_token": token},
            follow_redirects=False,
        )

    def register(self, client, **overrides):
        data = self.register_payload(**overrides)
        data["csrf_token"] = self.csrf_token(client, "/register")
        return client.post("/register", data=data, follow_redirects=False)

    def seed_note(self, **overrides):
        values = {
            "title": "Phase One Note",
            "branch": "Computer Science Engineering",
            "year": "3rd Year",
            "semester": "Semester 5",
            "subject": "DBMS",
            "stored_filename": "phase1.pdf",
            "original_filename": "phase1.pdf",
        }
        values.update(overrides)
        with app.app_context():
            db = studenthub.get_db()
            cursor = db.execute(
                """INSERT INTO study_notes
                   (title, branch, year, semester, subject, stored_filename,
                    original_filename, uploaded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    values["title"],
                    values["branch"],
                    values["year"],
                    values["semester"],
                    values["subject"],
                    values["stored_filename"],
                    values["original_filename"],
                    self.owner_id,
                ),
            )
            db.commit()
            note_id = cursor.lastrowid
        (UPLOAD_ROOT / values["stored_filename"]).write_bytes(b"%PDF-1.4\n% test\n")
        return note_id

    def count_rows(self, table, where="", params=()):
        with app.app_context():
            query = f"SELECT COUNT(*) FROM {table}"
            if where:
                query += f" WHERE {where}"
            return studenthub.get_db().execute(query, params).fetchone()[0]

    # ----------------------------------------------------- redirect protection
    def test_login_redirect_rejects_unsafe_targets(self):
        unsafe_targets = [
            "////evil.com",
            "http:///evil.com",
            "//evil.com",
            "/\\evil.com",
            "/%5Cevil.com",
            "https://evil.com",
            "javascript:alert(1)",
        ]
        for target in unsafe_targets:
            with self.subTest(target=target):
                client = app.test_client()
                response = self.login(client, next_value=target)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers.get("Location"), "/")

    def test_login_redirect_keeps_safe_local_targets(self):
        for target in ("/notes", "/notes?search=1", "/chatbot"):
            with self.subTest(target=target):
                client = app.test_client()
                response = self.login(client, next_value=target)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers.get("Location"), target)

    def test_preview_return_to_rejects_unsafe_targets(self):
        note_id = self.seed_note()
        client = app.test_client()
        response = client.get(
            f"/notes/{note_id}/preview",
            query_string={"return_to": "////evil.com"},
        )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('href="////evil.com"', body)
        self.assertIn('href="/notes/subjects?', body)

    def test_preview_return_to_keeps_safe_local_path(self):
        note_id = self.seed_note()
        response = app.test_client().get(
            f"/notes/{note_id}/preview",
            query_string={"return_to": "/notes?search=1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/notes?search=1"', response.get_data(as_text=True))

    # --------------------------------------------------------- CSRF protection
    def test_state_changing_routes_reject_missing_csrf(self):
        anonymous_cases = [
            ("/login", {"email": "student@example.com", "password": "student-password"}),
            ("/register", self.register_payload()),
            ("/suggestion", {"category": "other", "suggestion": "no token"}),
            ("/quick-help", {"question": "no token"}),
            ("/quick-help/continue", {"quick_questions": "no token"}),
            ("/logout", {}),
        ]
        for path, data in anonymous_cases:
            with self.subTest(path=path):
                response = app.test_client().post(path, data=data)
                self.assertEqual(response.status_code, 400)

        upload_response = app.test_client().post(
            "/notes/upload",
            data={"title": "No token"},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_response.status_code, 400)
        self.assertEqual(self.count_rows("study_notes"), 0)
        self.assertEqual(self.count_rows("suggestions"), 0)
        self.assertEqual(self.count_rows("users", "email = ?", ("student@example.com",)), 0)

    def test_state_changing_routes_reject_wrong_csrf(self):
        response = app.test_client().post(
            "/suggestion",
            data={"category": "other", "suggestion": "wrong token", "csrf_token": "wrong"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count_rows("suggestions"), 0)

    def test_chatbot_post_requires_csrf(self):
        client = app.test_client()
        self.login(client)
        response = client.post("/chatbot", data={"question": "no token"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count_rows("mentor_conversations"), 0)
        self.assertEqual(self.count_rows("mentor_messages"), 0)

    def test_all_post_forms_include_csrf_token(self):
        anonymous_pages = ["/", "/login", "/register"]
        for path in anonymous_pages:
            with self.subTest(path=path):
                body = app.test_client().get(path).get_data(as_text=True)
                post_forms = len(re.findall(r"<form[^>]*method=\"post\"", body, re.IGNORECASE))
                tokens = body.count('name="csrf_token"')
                self.assertGreater(post_forms, 0)
                self.assertEqual(tokens, post_forms)

        owner_client = app.test_client()
        self.login(owner_client)
        for path in ["/", "/account", "/chatbot", "/notes/upload", "/admin"]:
            with self.subTest(path=path):
                body = owner_client.get(path).get_data(as_text=True)
                post_forms = len(re.findall(r"<form[^>]*method=\"post\"", body, re.IGNORECASE))
                tokens = body.count('name="csrf_token"')
                self.assertGreater(post_forms, 0)
                self.assertEqual(tokens, post_forms)

    def test_logout_is_post_only_and_clears_session(self):
        client = app.test_client()
        self.login(client)
        self.assertEqual(client.get("/logout").status_code, 405)

        response = client.post("/logout")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(client.get("/account").status_code, 200)

        client.get("/account")
        with client.session_transaction() as session:
            token = session["csrf_token"]
        response = client.post("/logout", data={"csrf_token": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get("/account").status_code, 302)

    # ----------------------------------------------------- registration checks
    def test_registration_rejects_invalid_values(self):
        invalid_cases = [
            ("invalid email", {"email": "not-an-email"}),
            ("invalid branch", {"branch": "Anything"}),
            ("invalid year", {"year": "Year 99"}),
            ("short name", {"name": "A"}),
            ("long name", {"name": "N" * 81}),
            ("control chars in name", {"name": "Bad\nName"}),
            ("short college", {"college": "C"}),
            ("long college", {"college": "C" * 121}),
            ("long password", {
                "password": "p" * 129,
                "confirm_password": "p" * 129,
            }),
        ]
        for label, overrides in invalid_cases:
            with self.subTest(case=label):
                email = overrides.get("email", "invalid@example.com")
                client = app.test_client()
                response = self.register(client, **overrides)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    self.count_rows("users", "email = ?", (email,)),
                    0,
                )

    def test_registration_accepts_existing_and_notes_branch_names(self):
        branches = ["Computer Science", "Other", "Computer Science Engineering"]
        for index, branch in enumerate(branches):
            with self.subTest(branch=branch):
                email = f"valid{index}@example.com"
                client = app.test_client()
                response = self.register(client, email=email, branch=branch)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers.get("Location"), "/")
                self.assertEqual(
                    self.count_rows("users", "email = ? AND branch = ?", (email, branch)),
                    1,
                )

    def test_registration_accepts_boundary_lengths(self):
        client = app.test_client()
        response = self.register(
            client,
            name="N" * 80,
            college="C" * 120,
            email="boundary@example.com",
            password="p" * 128,
            confirm_password="p" * 128,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.count_rows("users", "email = ?", ("boundary@example.com",)),
            1,
        )

    # ------------------------------------------------------------ owner guard
    def set_owner_role(self, value):
        with app.app_context():
            db = studenthub.get_db()
            db.execute("UPDATE users SET is_owner = ? WHERE email = ?", (value, self.OWNER_EMAIL))
            db.commit()

    def test_owner_grant_fails_closed_when_owner_email_is_missing(self):
        self.set_owner_role(0)
        runner = app.test_cli_runner()

        for configured in ("", "   "):
            with self.subTest(configured=repr(configured)):
                app.config["OWNER_EMAIL"] = configured
                result = runner.invoke(
                    args=["grant-library-owner", "--email", self.OWNER_EMAIL]
                )
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("OWNER_EMAIL", result.output)
                self.assertEqual(
                    self.count_rows("users", "email = ? AND is_owner = 1", (self.OWNER_EMAIL,)),
                    0,
                )

    def test_owner_grant_rejects_unconfigured_email(self):
        self.set_owner_role(0)
        app.config["OWNER_EMAIL"] = "someone-else@example.com"
        result = app.test_cli_runner().invoke(
            args=["grant-library-owner", "--email", self.OWNER_EMAIL]
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("configured owner", result.output)
        self.assertEqual(
            self.count_rows("users", "email = ? AND is_owner = 1", (self.OWNER_EMAIL,)),
            0,
        )

    def test_owner_grant_works_for_configured_account(self):
        self.set_owner_role(0)
        app.config["OWNER_EMAIL"] = self.OWNER_EMAIL
        result = app.test_cli_runner().invoke(
            args=["grant-library-owner", "--email", self.OWNER_EMAIL]
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            self.count_rows("users", "email = ? AND is_owner = 1", (self.OWNER_EMAIL,)),
            1,
        )

    # ------------------------------------------------------- valid user flows
    def test_normal_user_cannot_access_owner_pages(self):
        client = app.test_client()
        response = self.register(client, email="normal@example.com")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get("/admin").status_code, 403)
        self.assertEqual(client.get("/notes/upload").status_code, 403)

        anonymous = app.test_client()
        self.assertEqual(anonymous.get("/admin").status_code, 302)
        self.assertEqual(anonymous.get("/notes/upload").status_code, 302)

    def test_valid_suggestion_and_quick_help_flows(self):
        client = app.test_client()
        client.get("/")
        with client.session_transaction() as session:
            token = session["csrf_token"]

        suggestion_response = client.post(
            "/suggestion",
            data={"category": "other", "suggestion": "Phase one test", "csrf_token": token},
        )
        self.assertEqual(suggestion_response.status_code, 302)
        self.assertEqual(self.count_rows("suggestions", "message = ?", ("Phase one test",)), 1)

        quick_response = client.post(
            "/quick-help",
            data={"question": "What is DBMS?", "csrf_token": token},
        )
        self.assertEqual(quick_response.status_code, 302)
        with client.session_transaction() as session:
            self.assertEqual(session["home_quick_result"]["intent"], "subject")

    def test_valid_chatbot_and_upload_flows(self):
        owner = app.test_client()
        self.login(owner)

        chatbot_token = self.csrf_token(owner, "/chatbot")
        chatbot_response = owner.post(
            "/chatbot",
            data={"question": "How should I prepare for placements?", "csrf_token": chatbot_token},
        )
        self.assertEqual(chatbot_response.status_code, 302)
        self.assertEqual(self.count_rows("mentor_conversations"), 1)
        self.assertEqual(self.count_rows("mentor_messages"), 1)

        upload_token = self.csrf_token(owner, "/notes/upload")
        upload_response = owner.post(
            "/notes/upload",
            data={
                "csrf_token": upload_token,
                "title": "Uploaded Phase One Note",
                "subject": "DBMS",
                "branch": "Computer Science Engineering",
                "year": "3rd Year",
                "semester": "Semester 5",
                "file": (io.BytesIO(b"%PDF-1.4\n% test\n"), "phase1-upload.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(upload_response.status_code, 302)
        self.assertEqual(
            self.count_rows("study_notes", "title = ?", ("Uploaded Phase One Note",)),
            1,
        )
        self.assertEqual(len(list(UPLOAD_ROOT.iterdir())), 1)


    # --- Notes flow: year -> branch -> semester -> subject, and upload consistency ---

    def upload_note(self, client, **fields):
        data = {
            "csrf_token": self.csrf_token(client, "/notes/upload"),
            "title": "Flow Note",
            "subject": "Maths",
            "branch": "Computer Science Engineering",
            "year": "2nd Year",
            "semester": "Semester 3",
            "file": (io.BytesIO(b"%PDF-1.4\n% test\n"), "flow.pdf"),
        }
        data.update(fields)
        return client.post("/notes/upload", data=data, content_type="multipart/form-data")

    def test_first_year_shows_common_first_plus_branches(self):
        body = app.test_client().get("/notes/branches?year=1st+Year").get_data(as_text=True)
        self.assertIn("Common (1st Year)", body)
        self.assertIn("Electronics &amp; Communication", body)
        self.assertLess(body.index("Common (1st Year)</strong>"), body.index("Computer Science Engineering</strong>"))
        # 1st Year skips the semester step and links straight to subjects.
        self.assertIn("/notes/subjects?", body)
        self.assertNotIn("/notes/semesters?", body)

    def test_first_year_subjects_show_both_semesters(self):
        common = {"branch": "Common (1st Year)", "year": "1st Year"}
        self.seed_note(title="Physics Sem One", semester="Semester 1", stored_filename="p1.pdf", **common)
        self.seed_note(title="Maths Sem Two", semester="Semester 2", stored_filename="m2.pdf", **common)
        client = app.test_client()
        body = client.get("/notes/subjects", query_string=common).get_data(as_text=True)
        self.assertIn("Physics Sem One", body)
        self.assertIn("Maths Sem Two", body)
        self.assertIn("1st Year branches", body)
        response = client.get("/notes/semesters", query_string=common)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/notes/subjects?", response.headers["Location"])

    def test_later_years_hide_common(self):
        body = app.test_client().get("/notes/branches?year=2nd+Year").get_data(as_text=True)
        self.assertNotIn("Common (1st Year)</strong>", body)
        response = app.test_client().get("/notes/semesters?branch=Common+(1st+Year)&year=2nd+Year")
        self.assertEqual(response.status_code, 302)

    def test_semester_page_shows_only_that_years_semesters(self):
        body = app.test_client().get(
            "/notes/semesters", query_string={"branch": "Electronics & Communication", "year": "3rd Year"}
        ).get_data(as_text=True)
        self.assertIn("Semester 5", body)
        self.assertIn("Semester 6", body)
        self.assertNotIn("Semester 4<", body)
        self.assertNotIn("Semester 7<", body)

    def test_subjects_filtered_by_semester(self):
        self.seed_note(title="Sem Five Note", semester="Semester 5", stored_filename="a.pdf")
        self.seed_note(title="Sem Six Note", semester="Semester 6", stored_filename="b.pdf")
        client = app.test_client()
        query = {"branch": "Computer Science Engineering", "year": "3rd Year"}
        body = client.get("/notes/subjects", query_string={**query, "semester": "Semester 5"}).get_data(as_text=True)
        self.assertIn("Sem Five Note", body)
        self.assertNotIn("Sem Six Note", body)
        # Old links without a semester go to the semester chooser.
        response = client.get("/notes/subjects", query_string=query)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/notes/semesters?", response.headers["Location"])

    def test_upload_rejects_inconsistent_assignment(self):
        owner = app.test_client()
        self.login(owner)
        bad = [
            {"year": "2nd Year", "semester": "Semester 5"},
            {"branch": "Common (1st Year)", "year": "2nd Year", "semester": "Semester 3"},
        ]
        for fields in bad:
            with self.subTest(**fields):
                self.assertEqual(self.upload_note(owner, **fields).status_code, 200)
        self.assertEqual(self.count_rows("study_notes"), 0)
        self.assertEqual(list(UPLOAD_ROOT.iterdir()), [])
        ok = self.upload_note(owner, branch="Common (1st Year)", year="1st Year", semester="Semester 2")
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(self.count_rows("study_notes"), 1)

    def test_cli_add_rejects_inconsistent_assignment(self):
        pdf = TEMP_ROOT / "cli-note.pdf"
        pdf.write_bytes(b"%PDF-1.4\n% test\n")
        result = app.test_cli_runner().invoke(args=[
            "library", "add", "--owner-email", self.OWNER_EMAIL, "--title", "CLI",
            "--subject", "Maths", "--branch", "Civil Engineering", "--year", "4th Year",
            "--semester", "Semester 2", "--file", str(pdf),
        ])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("4th Year notes must be in", result.output)
        self.assertEqual(self.count_rows("study_notes"), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
