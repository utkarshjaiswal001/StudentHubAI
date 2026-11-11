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
os.environ["BACKUP_FOLDER"] = str(TEMP_ROOT / "backups")
os.environ["SECRET_KEY"] = "phase1-test-secret"
os.environ["OWNER_EMAIL"] = "owner@example.com"
os.environ["OPENAI_API_KEY"] = ""
os.environ["SESSION_COOKIE_SECURE"] = "false"

sys.path.insert(0, str(PROJECT_ROOT))

import app as studenthub  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402
from markupsafe import escape  # noqa: E402

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
                "login_attempts",
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
            "branch": "Computer Science Engineering",
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

    def test_registration_rejects_common_and_legacy_branch_names(self):
        for index, branch in enumerate(["Common (1st Year)", "Computer Science"]):
            with self.subTest(branch=branch):
                email = f"bad-branch{index}@example.com"
                response = self.register(app.test_client(), email=email, branch=branch)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.count_rows("users", "email = ?", (email,)), 0)

    def test_registration_accepts_existing_and_notes_branch_names(self):
        branches = ["Other", "Computer Science Engineering", "Electronics & Communication"]
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


    # --- Phase 1 security: lockout, quick-help history, headers, session expiry ---

    def test_login_locks_after_five_wrong_passwords(self):
        client = app.test_client()
        for _ in range(5):
            response = self.login(client, password="wrong-password")
            self.assertIn("Email or password is incorrect", response.get_data(as_text=True))
        # Even the right password is refused while locked.
        response = self.login(client)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Too many wrong attempts", response.get_data(as_text=True))
        with client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_login_lock_expires_and_success_resets_counter(self):
        client = app.test_client()
        for _ in range(5):
            self.login(client, password="wrong-password")
        with app.app_context():
            db = studenthub.get_db()
            db.execute("UPDATE login_attempts SET locked_until = '2000-01-01T00:00:00+00:00'")
            db.commit()
        self.assertEqual(self.login(client).status_code, 302)
        self.assertEqual(self.count_rows("login_attempts"), 0)

    def test_quick_help_continue_ignores_browser_sent_answers(self):
        client = app.test_client()
        self.login(client)
        token = self.csrf_token(client, "/")
        client.post("/quick-help", data={"csrf_token": token, "question": "what is dbms"})
        client.post(
            "/quick-help/continue",
            data={
                "csrf_token": token,
                "quick_questions": ["forged question"],
                "quick_answers": ["FAKE ASSISTANT TEXT"],
            },
        )
        self.assertEqual(
            self.count_rows("mentor_messages", "content LIKE ?", ("%FAKE ASSISTANT%",)), 0
        )
        self.assertEqual(
            self.count_rows("mentor_messages", "content = ?", ("what is dbms",)), 1
        )

    def test_security_headers_on_pages(self):
        for path in ("/", "/notes", "/login"):
            with self.subTest(path=path):
                headers = app.test_client().get(path).headers
                self.assertEqual(headers.get("X-Frame-Options"), "SAMEORIGIN")
                self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(headers.get("Referrer-Policy"), "same-origin")

    def test_login_session_expires_after_seven_days(self):
        client = app.test_client()
        response = self.login(client)
        cookie = response.headers.get("Set-Cookie", "")
        self.assertIn("Expires=", cookie)
        self.assertEqual(app.permanent_session_lifetime.days, 7)


    # --- Phase 2 admin tools: edit/delete notes, issue reports, password reset ---

    def student_client(self):
        client = app.test_client()
        self.assertEqual(self.register(client).status_code, 302)
        return client

    def test_admin_tools_blocked_for_students(self):
        note_id = self.seed_note()
        client = self.student_client()
        token = self.csrf_token(client, "/")
        self.assertEqual(client.get(f"/admin/notes/{note_id}/edit").status_code, 403)
        self.assertEqual(client.get(f"/admin/notes/{note_id}/delete").status_code, 403)
        self.assertEqual(client.post(f"/admin/notes/{note_id}/delete", data={"csrf_token": token}).status_code, 403)
        self.assertEqual(client.post("/admin/reports/1/status", data={"csrf_token": token, "status": "closed"}).status_code, 403)
        self.assertEqual(client.post("/admin/students/reset-password", data={"csrf_token": token, "email": self.OWNER_EMAIL}).status_code, 403)
        self.assertEqual(self.count_rows("study_notes"), 1)

    def test_owner_edits_note_and_bad_values_are_rejected(self):
        note_id = self.seed_note()
        owner = app.test_client()
        self.login(owner)
        token = self.csrf_token(owner, f"/admin/notes/{note_id}/edit")
        fields = {"csrf_token": token, "title": "Renamed", "subject": "DBMS",
                  "branch": "Information Technology", "year": "2nd Year", "semester": "Semester 4"}
        bad = owner.post(f"/admin/notes/{note_id}/edit", data={**fields, "semester": "Semester 7"})
        self.assertEqual(bad.status_code, 200)
        self.assertEqual(self.count_rows("study_notes", "title = ?", ("Phase One Note",)), 1)
        good = owner.post(f"/admin/notes/{note_id}/edit", data=fields)
        self.assertEqual(good.status_code, 302)
        self.assertEqual(
            self.count_rows("study_notes", "title = ? AND branch = ? AND semester = ?",
                            ("Renamed", "Information Technology", "Semester 4")), 1)

    def test_owner_deletes_note_and_file_after_confirm(self):
        note_id = self.seed_note()
        owner = app.test_client()
        self.login(owner)
        confirm = owner.get(f"/admin/notes/{note_id}/delete")
        self.assertIn("Yes, delete this note", confirm.get_data(as_text=True))
        self.assertEqual(self.count_rows("study_notes"), 1)  # GET never deletes
        token = self.csrf_token(owner, "/admin")
        self.assertEqual(owner.post(f"/admin/notes/{note_id}/delete", data={"csrf_token": token}).status_code, 302)
        self.assertEqual(self.count_rows("study_notes"), 0)
        self.assertFalse((UPLOAD_ROOT / "phase1.pdf").exists())

    def test_admin_lists_notes_with_search(self):
        self.seed_note(title="Signals Unit 1", subject="Signals", stored_filename="s.pdf")
        self.seed_note(title="DBMS Unit 2", stored_filename="d.pdf")
        owner = app.test_client()
        self.login(owner)
        body = owner.get("/admin?q=Signals").get_data(as_text=True)
        self.assertIn("Signals Unit 1", body)
        self.assertNotIn("DBMS Unit 2", body)

    def test_owner_closes_issue_report(self):
        visitor = app.test_client()
        token = self.csrf_token(visitor, "/")
        visitor.post("/suggestion", data={"csrf_token": token, "suggestion": "Download button broken", "category": "notes"})
        owner = app.test_client()
        self.login(owner)
        self.assertIn("Download button broken", owner.get("/admin").get_data(as_text=True))
        with app.app_context():
            report_id = studenthub.get_db().execute("SELECT id FROM suggestions").fetchone()[0]
        token = self.csrf_token(owner, "/admin")
        owner.post(f"/admin/reports/{report_id}/status", data={"csrf_token": token, "status": "closed"})
        self.assertEqual(self.count_rows("suggestions", "status = 'closed'"), 1)
        self.assertNotIn("Download button broken", owner.get("/admin").get_data(as_text=True))
        self.assertIn("Download button broken", owner.get("/admin?reports=all").get_data(as_text=True))

    def test_owner_resets_student_password(self):
        self.student_client()
        owner = app.test_client()
        self.login(owner)
        token = self.csrf_token(owner, "/admin")
        response = owner.post("/admin/students/reset-password",
                              data={"csrf_token": token, "email": "student@example.com"},
                              follow_redirects=True)
        temporary = re.search(r"Temporary password for Test Student: (\S+) ", response.get_data(as_text=True)).group(1)
        self.assertEqual(self.count_rows("users", "email = ? AND must_change_password = 1", ("student@example.com",)), 1)
        self.assertEqual(self.login(app.test_client(), email="student@example.com", password="student-password").status_code, 200)
        self.assertEqual(self.login(app.test_client(), email="student@example.com", password=temporary).status_code, 302)
        # The owner account can't be reset from here.
        owner.post("/admin/students/reset-password", data={"csrf_token": token, "email": self.OWNER_EMAIL})
        self.assertEqual(self.login(app.test_client()).status_code, 302)

    def test_upload_redirects_to_where_note_appears(self):
        owner = app.test_client()
        self.login(owner)
        response = self.upload_note(owner)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/notes/subjects?", response.headers["Location"])
        self.assertIn("semester=Semester", response.headers["Location"])


    # --- Phase 3 student account: profile, password, delete, My notes ---

    def test_edit_profile(self):
        client = self.student_client()
        token = self.csrf_token(client, "/account/profile")
        bad = client.post("/account/profile", data={"csrf_token": token, "name": "New Name",
                          "college": "GCET", "branch": "Common (1st Year)", "year": "2nd Year"})
        self.assertEqual(bad.status_code, 200)
        good = client.post("/account/profile", data={"csrf_token": token, "name": "New Name",
                           "college": "GCET", "branch": "Civil Engineering", "year": "2nd Year"})
        self.assertEqual(good.status_code, 302)
        self.assertEqual(self.count_rows("users", "name = ? AND branch = ? AND year = ?",
                                         ("New Name", "Civil Engineering", "2nd Year")), 1)
        with client.session_transaction() as session:
            self.assertEqual(session["user_name"], "New Name")

    def test_change_password(self):
        client = self.student_client()
        token = self.csrf_token(client, "/account/password")
        fields = {"csrf_token": token, "current_password": "wrong-one",
                  "new_password": "brand-new-pass", "confirm_password": "brand-new-pass"}
        self.assertEqual(client.post("/account/password", data=fields).status_code, 200)
        fields["current_password"] = "student-password"
        self.assertEqual(client.post("/account/password", data=fields).status_code, 302)
        self.assertEqual(self.login(app.test_client(), email="student@example.com", password="student-password").status_code, 200)
        self.assertEqual(self.login(app.test_client(), email="student@example.com", password="brand-new-pass").status_code, 302)

    def test_reset_password_forces_new_password(self):
        self.student_client()
        with app.app_context():
            db = studenthub.get_db()
            db.execute("UPDATE users SET password_hash = ?, must_change_password = 1 WHERE email = ?",
                       (generate_password_hash("temp-pass-123"), "student@example.com"))
            db.commit()
        client = app.test_client()
        self.login(client, email="student@example.com", password="temp-pass-123")
        for path in ("/notes", "/account", "/chatbot"):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers["Location"].endswith("/account/password"))
        token = self.csrf_token(client, "/account/password")
        client.post("/account/password", data={"csrf_token": token, "current_password": "temp-pass-123",
                    "new_password": "my-own-pass-1", "confirm_password": "my-own-pass-1"})
        self.assertEqual(client.get("/notes").status_code, 200)

    def test_delete_account(self):
        client = self.student_client()
        token = self.csrf_token(client, "/chatbot")
        client.post("/chatbot", data={"csrf_token": token, "question": "hello mentor"})
        self.assertEqual(self.count_rows("mentor_messages"), 1)
        client.post("/account/delete", data={"csrf_token": token, "password": "wrong"})
        self.assertEqual(self.count_rows("users", "email = ?", ("student@example.com",)), 1)
        response = client.post("/account/delete", data={"csrf_token": token, "password": "student-password"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.count_rows("users", "email = ?", ("student@example.com",)), 0)
        self.assertEqual(self.count_rows("mentor_messages"), 0)
        with client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_owner_cannot_delete_account(self):
        owner = app.test_client()
        self.login(owner)
        token = self.csrf_token(owner, "/account")
        owner.post("/account/delete", data={"csrf_token": token, "password": self.OWNER_PASSWORD})
        self.assertEqual(self.count_rows("users", "email = ?", (self.OWNER_EMAIL,)), 1)

    def test_my_notes_shortcut(self):
        # Owner profile: Computer Science Engineering, 3rd Year -> semester chooser.
        owner = app.test_client()
        self.login(owner)
        body = owner.get("/account").get_data(as_text=True)
        self.assertIn("/notes/semesters?branch=Computer+Science+Engineering&amp;year=3rd+Year", body)
        # 1st-year student -> branch list (Common first).
        student = self.student_client()
        self.assertIn("/notes/branches?year=1st+Year", student.get("/account").get_data(as_text=True))

    def test_legacy_branch_name_is_migrated(self):
        with app.app_context():
            db = studenthub.get_db()
            db.execute("UPDATE users SET branch = 'Computer Science' WHERE email = ?", (self.OWNER_EMAIL,))
            db.commit()
        studenthub.init_db()
        self.assertEqual(self.count_rows("users", "branch = 'Computer Science Engineering'"), 1)


    # --- Phase 4 notes extras: subject spelling, search, New badge ---

    def test_upload_reuses_existing_subject_spelling(self):
        self.seed_note(subject="DBMS", year="2nd Year", semester="Semester 3", stored_filename="x.pdf")
        owner = app.test_client()
        self.login(owner)
        self.assertIn('<option value="DBMS">', owner.get("/notes/upload").get_data(as_text=True))
        self.upload_note(owner, subject="dbms")
        self.assertEqual(self.count_rows("study_notes", "subject = 'DBMS'"), 2)
        self.assertEqual(self.count_rows("study_notes", "subject = 'dbms'"), 0)

    def test_subjects_page_search_and_new_badge(self):
        self.seed_note(title="Normalization Notes", subject="DBMS", stored_filename="a.pdf")
        self.seed_note(title="TCP Basics", subject="Computer Networks", stored_filename="b.pdf")
        query = {"branch": "Computer Science Engineering", "year": "3rd Year", "semester": "Semester 5"}
        client = app.test_client()
        body = client.get("/notes/subjects", query_string={**query, "q": "network"}).get_data(as_text=True)
        self.assertIn("TCP Basics", body)
        self.assertNotIn("Normalization Notes", body)
        body = client.get("/notes/subjects", query_string=query).get_data(as_text=True)
        self.assertIn('class="notes-new-badge"', body)
        with app.app_context():
            db = studenthub.get_db()
            db.execute("UPDATE study_notes SET created_at = '2020-01-01 00:00:00'")
            db.commit()
        body = client.get("/notes/subjects", query_string=query).get_data(as_text=True)
        self.assertNotIn('class="notes-new-badge"', body)


    # --- Official AKTU subject list ---

    def test_catalog_covers_every_branch(self):
        branches = [b for b in studenthub.NOTE_BRANCHES if b != "Common (1st Year)"]
        self.assertTrue(studenthub.official_subjects("Common (1st Year)", "1st Year"))
        for branch in branches:
            with self.subTest(branch=branch):
                first_year = studenthub.official_subjects(branch, "1st Year")
                self.assertGreater(len(first_year), len(studenthub.official_subjects("Common (1st Year)", "1st Year")))
                for number in range(3, 8):
                    self.assertTrue(studenthub.official_subjects(branch, "x", f"Semester {number}"))

    def test_subjects_page_lists_official_subjects_for_every_branch(self):
        client = app.test_client()
        for branch in [b for b in studenthub.NOTE_BRANCHES if b != "Common (1st Year)"]:
            with self.subTest(branch=branch):
                query = {"branch": branch, "year": "2nd Year", "semester": "Semester 3"}
                body = client.get("/notes/subjects", query_string=query).get_data(as_text=True)
                self.assertIn("Technical Communication", body)
                self.assertIn("BAS301", body)
                self.assertIn("No notes yet", body)
                semesters = client.get("/notes/semesters", query_string={"branch": branch, "year": "2nd Year"})
                self.assertIn("AKTU subjects", semesters.get_data(as_text=True))

    def test_first_year_branch_page_includes_common_subjects_and_notes(self):
        self.seed_note(title="Shared IKS Note", subject="Introduction to Indian Knowledge System",
                       branch="Common (1st Year)", year="1st Year", semester="Semester 1",
                       stored_filename="iks.pdf")
        client = app.test_client()
        for branch in [b for b in studenthub.NOTE_BRANCHES if b != "Common (1st Year)"]:
            with self.subTest(branch=branch):
                body = client.get("/notes/subjects", query_string={"branch": branch, "year": "1st Year"}).get_data(as_text=True)
                self.assertIn("Shared IKS Note", body)
                self.assertIn("Programming Languages", body)
                stream_subject = studenthub.AKTU_CATALOG["first_year"][branch][0]["name"]
                self.assertIn(escape(stream_subject), body)

    def test_subject_search_finds_official_subjects_by_code(self):
        query = {"branch": "Civil Engineering", "year": "2nd Year", "semester": "Semester 3", "q": "bce301"}
        body = app.test_client().get("/notes/subjects", query_string=query).get_data(as_text=True)
        self.assertIn("Engineering Mechanics", body)
        self.assertNotIn("Technical Communication", body)

    def test_upload_offers_official_subjects_and_uses_official_spelling(self):
        owner = app.test_client()
        self.login(owner)
        page = owner.get("/notes/upload").get_data(as_text=True)
        self.assertIn('id="subject-choices"', page)
        self.assertIn("Mechanical Engineering|3rd Year|Semester 5", page)
        self.assertIn("subject_picker.js", page)
        self.upload_note(owner, subject="technical communication")
        self.assertEqual(self.count_rows("study_notes", "subject = 'Technical Communication'"), 1)
        # Subjects outside the syllabus (e.g. open electives) can still be typed.
        self.upload_note(owner, subject="My Open Elective")
        self.assertEqual(self.count_rows("study_notes", "subject = 'My Open Elective'"), 1)

    def test_every_page_loads_dark_theme_and_switch(self):
        client = app.test_client()
        for path in ["/", "/notes", "/login", "/register", "/nope"]:
            with self.subTest(path=path):
                body = client.get(path).get_data(as_text=True)
                self.assertIn('setAttribute("data-theme"', body)
                self.assertIn("css/dark.css", body)
                self.assertIn("js/theme_toggle.js", body)
                # Theme files load after the old stylesheets so they can override them.
                self.assertLess(body.index("css/style.css"), body.index("css/dark.css"))
                self.assertIn("css/palettes.css", body)
                self.assertIn("css/theme-ui.css", body)

    def test_theme_gallery_shows_every_palette_in_both_modes(self):
        body = app.test_client().get("/themes").get_data(as_text=True)
        palettes = studenthub.THEME_PALETTES
        self.assertGreaterEqual(len(palettes), 6)
        for palette in palettes:
            with self.subTest(palette=palette["id"]):
                self.assertIn(palette["name"], body)
                self.assertIn(f'data-theme="dark" data-palette="{palette["id"]}"', body)
                self.assertIn(f'data-theme="light" data-palette="{palette["id"]}"', body)
                # Each palette has its own colours in palettes.css (Aurora is the default).
                if palette["id"] != "aurora":
                    css = (Path(studenthub.app.root_path) / "static" / "css" / "palettes.css").read_text(encoding="utf-8")
                    self.assertIn(f'[data-palette="{palette["id"]}"]', css)
        # The head script only accepts known palette names.
        self.assertIn('"aurora", "ocean"', body)

    def test_glass_layout_is_offered_and_loaded(self):
        client = app.test_client()
        home = client.get("/").get_data(as_text=True)
        self.assertIn("css/layout-glass.css", home)
        self.assertIn('l==="glass"?"glass":"classic"', home)
        self.assertIn('class="hero-glass-card"', home)
        gallery = client.get("/themes").get_data(as_text=True)
        self.assertIn('data-layout="classic"', gallery)
        self.assertIn('data-layout="glass"', gallery)
        css = (Path(studenthub.app.root_path) / "static" / "css" / "layout-glass.css").read_text(encoding="utf-8")
        self.assertIn('html[data-layout="glass"] .navbar', css)

    def test_shine_effects_can_be_switched_off(self):
        home = app.test_client().get("/").get_data(as_text=True)
        self.assertIn("css/fx-shine.css", home)
        self.assertIn('f==="calm"?"calm":"shine"', home)
        css = (Path(studenthub.app.root_path) / "static" / "css" / "fx-shine.css").read_text(encoding="utf-8")
        # Every effect is behind the Shine switch, so "Calm" turns all of them off.
        for line in css.splitlines():
            if line.startswith("html[") and "fx-sparkle" not in line:
                self.assertIn('data-fx="shine"', line)
        js = (Path(studenthub.app.root_path) / "static" / "js" / "theme_toggle.js").read_text(encoding="utf-8")
        self.assertIn("rail-mode", js)
        self.assertIn("rail-pop", js)

    def test_theme_gallery_offers_light_background_tones(self):
        body = app.test_client().get("/themes").get_data(as_text=True)
        css = (Path(studenthub.app.root_path) / "static" / "css" / "palettes.css").read_text(encoding="utf-8")
        tones = studenthub.THEME_LIGHT_BACKGROUNDS
        self.assertGreaterEqual(len(tones), 5)
        for tone in tones:
            with self.subTest(tone=tone["id"]):
                self.assertIn(f'data-bg="{tone["id"]}"', body)
                self.assertIn(f'Use {tone["name"]}', body)
                if tone["id"] != "auto":
                    self.assertIn(f'[data-theme="light"][data-bg="{tone["id"]}"]', css)
        # The head script only accepts known background names.
        self.assertIn('"cream"', body)


    # --- Core strengthening: error pages, backup/restore, Quick Help, spam limits ---

    def test_friendly_error_pages(self):
        client = app.test_client()
        response = client.get("/this-page-does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Page not found", response.get_data(as_text=True))
        self.assertIn("Go to Home", response.get_data(as_text=True))
        student = self.student_client()
        response = student.get("/admin")
        self.assertEqual(response.status_code, 403)
        self.assertIn("only for the StudentHub admin", response.get_data(as_text=True))
        response = client.post("/login", data={"email": "x@example.com", "password": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("form session expired", response.get_data(as_text=True))
        self.assertEqual(client.get("/logout").status_code, 405)

    def test_server_error_page_hides_details(self):
        def boom():
            raise RuntimeError("secret internal detail")
        original_view = app.view_functions["dashboard"]
        app.view_functions["dashboard"] = boom
        app.testing = False
        try:
            client = self.student_client()
            response = client.get("/dashboard")
        finally:
            app.testing = True
            app.view_functions["dashboard"] = original_view
        self.assertEqual(response.status_code, 500)
        body = response.get_data(as_text=True)
        self.assertIn("Something went wrong on our side", body)
        self.assertNotIn("secret internal detail", body)

    def test_backup_and_restore(self):
        self.seed_note(title="Keep Me")
        runner = app.test_cli_runner()
        result = runner.invoke(args=["backup"])
        self.assertEqual(result.exit_code, 0, result.output)
        backup_zip = Path(re.search(r"Backup saved: (.+\.zip)", result.output).group(1))
        self.assertIn("1 uploaded file", result.output)
        # Lose the data, then restore it.
        with app.app_context():
            db = studenthub.get_db()
            db.execute("DELETE FROM study_notes")
            db.commit()
        (UPLOAD_ROOT / "phase1.pdf").unlink()
        result = runner.invoke(args=["restore", str(backup_zip), "--yes"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.count_rows("study_notes", "title = 'Keep Me'"), 1)
        self.assertTrue((UPLOAD_ROOT / "phase1.pdf").is_file())
        self.assertTrue(any("before-restore" in p.name for p in (TEMP_ROOT / "backups").iterdir()))

    def test_restore_rejects_non_backup_zip(self):
        import zipfile
        bad = TEMP_ROOT / "bad.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr("../evil.txt", "x")
        result = app.test_cli_runner().invoke(args=["restore", str(bad), "--yes"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(self.count_rows("users"), 1)

    def test_quick_help_covers_every_branch(self):
        cases = {
            "explain digital communication": "Communication Systems",
            "what is a flip flop": "Digital Electronics",
            "help with engineering physics": "Engineering Physics",
            "8085 basics": "Microprocessors",
            "network analysis tips": "Network Analysis",
            "explain induction motor": "Electrical Machines",
            "power electronics basics": "Power Electronics",
            "thermodynamics help": "Thermodynamics",
            "how to draw bending moment diagram": "Strength of Materials",
            "surveying tips": "Surveying",
            "soil mechanics": "Geotechnical",
            "software engineering": "Software Engineering",
            "what is dbms": "DBMS",
            # Any other AKTU subject is found from the syllabus list.
            "tell me about cyber security": "BCC301",
            "how to make apps": "I can give quick pointers",
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertIn(expected, studenthub.quick_subject_answer(question))

    def test_issue_report_limit_per_student(self):
        client = self.student_client()
        token = self.csrf_token(client, "/")
        for index in range(studenthub.MAX_REPORTS_PER_USER_HOUR + 2):
            client.post("/suggestion", data={"csrf_token": token, "suggestion": f"report {index}", "category": "other"})
        self.assertEqual(self.count_rows("suggestions"), studenthub.MAX_REPORTS_PER_USER_HOUR)

    def test_registration_limit_per_hour(self):
        original = studenthub.MAX_REGISTRATIONS_HOUR
        studenthub.MAX_REGISTRATIONS_HOUR = 2  # owner (1) + one student
        try:
            self.assertEqual(self.register(app.test_client(), email="one@example.com").status_code, 302)
            response = self.register(app.test_client(), email="two@example.com")
            self.assertEqual(response.status_code, 200)
            self.assertIn("Too many new accounts", response.get_data(as_text=True))
        finally:
            studenthub.MAX_REGISTRATIONS_HOUR = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
