import os
import secrets
import sqlite3
import uuid
from functools import wraps
from pathlib import Path
from urllib.parse import urljoin, urlparse

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY"
) or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
    "SESSION_COOKIE_SECURE", "false"
).strip().lower() in {"1", "true", "yes"}
app.config["DATABASE"] = os.environ.get(
    "DATABASE_PATH", str(Path(app.instance_path) / "studenthub.sqlite3")
)
app.config["UPLOAD_FOLDER"] = os.environ.get(
    "UPLOAD_FOLDER", str(Path(app.instance_path) / "uploads")
)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

NOTE_BRANCHES = [
    "Common (1st Year)",
    "Computer Science Engineering",
    "Information Technology",
    "Electronics & Communication",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
]
NOTE_YEARS = ["1st Year", "2nd Year", "3rd Year", "4th Year"]
NOTE_SEMESTERS = [f"Semester {number}" for number in range(1, 9)]
SUGGESTED_SUBJECTS = [
    "Python Programming",
    "Data Structures",
    "DBMS",
    "Operating System",
    "Computer Networks",
    "Artificial Intelligence",
    "Machine Learning",
]
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-astra")


def generate_mentor_reply(conversation_id):
    """Generate a reply only when the user has explicitly configured a provider key."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, "AI replies are not configured yet. Your question was saved."

    try:
        from openai import OpenAI
    except ImportError:
        return None, "Install the project requirements to enable AI replies. Your question was saved."

    db = get_db()
    recent_messages = db.execute(
        """SELECT role, content FROM mentor_messages WHERE conversation_id = ?
           ORDER BY id DESC LIMIT 12""",
        (conversation_id,),
    ).fetchall()
    input_messages = [
        {"role": row["role"], "content": row["content"]}
        for row in reversed(recent_messages)
    ]
    try:
        response = OpenAI(api_key=api_key, timeout=30, max_retries=1).responses.create(
            model=OPENAI_MODEL,
            input=input_messages,
            instructions=(
                "You are StudentHub AI's career mentor for engineering students. "
                "Give practical, supportive, accurate guidance. Use clear steps and "
                "ask a focused follow-up question when useful. Do not claim certainty "
                "about placements, salaries, or hiring outcomes."
            ),
            max_output_tokens=600,
            store=False,
        )
        answer = response.output_text.strip()
        if not answer:
            return None, "The AI service returned an empty answer. Your question was saved."
        db.execute(
            "INSERT INTO mentor_messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
            (conversation_id, answer),
        )
        db.commit()
        return answer, None
    except Exception:
        app.logger.exception("StudentHub Mentor provider request failed")
        return None, "The AI service could not answer right now. Your question was saved; please try again."


def get_db():
    if "db" not in g:
        Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        get_db().execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                college TEXT NOT NULL,
                branch TEXT NOT NULL,
                year TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        get_db().execute(
            """CREATE TABLE IF NOT EXISTS study_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                branch TEXT NOT NULL,
                year TEXT NOT NULL,
                semester TEXT NOT NULL,
                subject TEXT NOT NULL,
                stored_filename TEXT NOT NULL UNIQUE,
                original_filename TEXT NOT NULL,
                uploaded_by INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        get_db().execute(
            """CREATE INDEX IF NOT EXISTS idx_study_notes_course
               ON study_notes (branch, year, semester, subject)"""
        )
        get_db().execute(
            """CREATE TABLE IF NOT EXISTS note_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                note_id INTEGER NOT NULL REFERENCES study_notes(id) ON DELETE CASCADE,
                action TEXT NOT NULL CHECK (action IN ('preview', 'download')),
                accessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        get_db().execute(
            """CREATE INDEX IF NOT EXISTS idx_note_activity_user_recent
               ON note_activity (user_id, accessed_at DESC, id DESC)"""
        )
        get_db().execute(
            """CREATE TABLE IF NOT EXISTS mentor_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        get_db().execute(
            """CREATE TABLE IF NOT EXISTS mentor_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES mentor_conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        get_db().execute(
            """CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                message TEXT NOT NULL CHECK (length(message) <= 2000),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        get_db().execute(
            """CREATE INDEX IF NOT EXISTS idx_mentor_conversations_user_recent
               ON mentor_conversations (user_id, updated_at DESC, id DESC)"""
        )
        get_db().execute(
            """CREATE INDEX IF NOT EXISTS idx_mentor_messages_conversation
               ON mentor_messages (conversation_id, id)"""
        )
        get_db().commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            flash("Please log in to access that page.", "info")
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(**kwargs)

    return wrapped_view


def is_safe_local_url(target):
    if not target:
        return False
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in ("http", "https") and host_url.netloc == redirect_url.netloc


def record_note_activity(note_id, action):
    db = get_db()
    db.execute(
        "INSERT INTO note_activity (user_id, note_id, action) VALUES (?, ?, ?)",
        (session["user_id"], note_id, action),
    )
    db.commit()


def create_mentor_conversation(user_id, exchanges):
    exchanges = [
        {"question": item.get("question", "").strip(), "answer": item.get("answer", "").strip()}
        for item in exchanges
        if item.get("question", "").strip()
    ]
    if not exchanges:
        return None
    db = get_db()
    title = " ".join(exchanges[0]["question"].split())[:72]
    cursor = db.execute(
        "INSERT INTO mentor_conversations (user_id, title) VALUES (?, ?)",
        (user_id, title),
    )
    conversation_id = cursor.lastrowid
    for exchange in exchanges:
        db.execute(
            "INSERT INTO mentor_messages (conversation_id, role, content) VALUES (?, 'user', ?)",
            (conversation_id, exchange["question"][:2000]),
        )
        if exchange["answer"]:
            db.execute(
                "INSERT INTO mentor_messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
                (conversation_id, exchange["answer"][:800]),
            )
    db.commit()
    return conversation_id


def quick_subject_answer(question):
    text = question.casefold()
    quick_answers = [
        (("data structure", "dsa"), "A data structure organizes information so a program can use it efficiently. Start with arrays, linked lists, stacks, queues, trees, hash maps, and graphs; compare their time and space costs."),
        (("dbms", "database", "sql"), "A DBMS stores and retrieves structured data. For coursework and interviews, focus on keys, joins, normalization, transactions, ACID properties, and indexes."),
        (("operating system", " os ", " os?"), "An operating system manages processes, memory, files, and devices. A useful study order is processes and threads, scheduling, synchronization, memory management, and deadlocks."),
        (("computer network", "networking", "tcp/ip", " osi "), "Computer networks move data between devices. Start with the OSI and TCP/IP models, IP addressing, DNS, HTTP, TCP versus UDP, routing, and basic subnetting."),
        (("python",), "Python is a general-purpose language with readable syntax. Practise variables, functions, collections, classes, exceptions, file handling, and solving small problems."),
        (("artificial intelligence", "machine learning", " ai ", " ml "), "AI is the broader field of systems that perform tasks associated with intelligence; machine learning is one approach that learns patterns from data. Begin with Python, statistics, data handling, and evaluation."),
        (("placement", "interview preparation"), "For placements, build fundamentals in one programming language, practise data structures and algorithms, revise DBMS, operating systems and networks, and prepare a clear explanation of your projects."),
    ]
    padded = f" {text} "
    for keywords, answer in quick_answers:
        if any(keyword in padded for keyword in keywords):
            return answer
    return "I can give quick pointers on core CS subjects and placement basics. For a longer explanation or a multi-step plan, continue this thread in the full AI Mentor."


def extract_note_subject(question):
    text = " ".join(question.strip().split())
    lower = text.casefold()
    note_words = ("note", "notes", "pdf", "study material", "study materials")
    action_words = ("find", "search", "show", "get", "open", "need", "looking for")
    if not any(word in lower for word in note_words) or not any(word in lower for word in action_words):
        return None
    for prefix in (
        "can you find me ", "please find me ", "find me ", "show me ",
        "search for ", "looking for ", "get me ", "find ", "search ",
        "show ", "get ", "open ", "i need ", "need ", "i want ",
    ):
        if lower.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    lower = text.casefold()
    for suffix in (
        " study materials", " study material", " notes", " note", " pdfs", " pdf",
        " for me", " please",
    ):
        if lower.endswith(suffix):
            text = text[:-len(suffix)].strip()
            lower = text.casefold()
    for prefix in ("notes for ", "notes on ", "notes about ", "for ", "on ", "about ", "the "):
        if lower.startswith(prefix):
            text = text[len(prefix):].strip()
            lower = text.casefold()
    return text.strip(" .,!?") or ""


@app.context_processor
def inject_user_state():
    return {
        "is_logged_in": session.get("user_id") is not None,
        "current_user_name": session.get("user_name"),
        "ai_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
    }


@app.route("/")
def home():
    quick_result = session.pop("home_quick_result", None)
    quick_notes = []
    if quick_result and quick_result.get("note_ids") and session.get("user_id"):
        note_ids = quick_result["note_ids"]
        placeholders = ", ".join("?" for _ in note_ids)
        found = get_db().execute(
            f"""SELECT id, title, subject, branch, year, semester
                FROM study_notes WHERE id IN ({placeholders})""",
            note_ids,
        ).fetchall()
        note_by_id = {note["id"]: note for note in found}
        quick_notes = [note_by_id[note_id] for note_id in note_ids if note_id in note_by_id]
    return render_template(
        "home.html",
        quick_result=quick_result,
        quick_notes=quick_notes,
        quick_history=session.get("home_quick_history", []),
    )


@app.get("/health")
def health_check():
    try:
        get_db().execute("SELECT 1").fetchone()
    except sqlite3.Error:
        app.logger.exception("StudentHub health check failed")
        return {"status": "unavailable"}, 503
    return {"status": "ok"}, 200


@app.route("/suggestion", methods=["POST"])
def submit_suggestion():
    suggestion = request.form.get("suggestion", "").strip()
    if not suggestion:
        flash("Write a suggestion before submitting.", "error")
    elif len(suggestion) > 2000:
        flash("Keep suggestions under 2,000 characters.", "error")
    else:
        get_db().execute(
            "INSERT INTO suggestions (user_id, message) VALUES (?, ?)",
            (session.get("user_id"), suggestion),
        )
        get_db().commit()
        flash("Thanks! Your suggestion was saved.", "success")
    return redirect(url_for("home", _anchor="suggestions"))


@app.route("/quick-help", methods=["POST"])
def quick_help():
    question = request.form.get("question", "").strip()
    if not question:
        flash("Type a short question first.", "error")
        return redirect(url_for("home", _anchor="career-mentor"))
    if len(question) > 2000:
        flash("Keep your question under 2,000 characters.", "error")
        return redirect(url_for("home", _anchor="career-mentor"))

    note_subject = extract_note_subject(question)
    if note_subject is not None:
        if not note_subject:
            answer = "Tell me the subject name too, for example: find DBMS notes."
            session["home_quick_result"] = {
                "question": question, "answer": answer, "intent": "notes",
            }
        elif not session.get("user_id"):
            session["home_quick_result"] = {
                "question": question,
                "answer": "Sign in to search the notes library and open PDFs.",
                "intent": "notes",
                "subject": note_subject,
                "login_url": url_for("login", next=url_for("notes", subject=note_subject)),
            }
        else:
            matching_notes = get_db().execute(
                """SELECT id, title, subject, branch, year, semester
                   FROM study_notes
                   WHERE lower(subject) LIKE lower(?) OR lower(title) LIKE lower(?)
                   ORDER BY created_at DESC, id DESC LIMIT 5""",
                (f"%{note_subject}%", f"%{note_subject}%"),
            ).fetchall()
            session["home_quick_result"] = {
                "question": question,
                "answer": (
                    f"I found {len(matching_notes)} note{'s' if len(matching_notes) != 1 else ''} for {note_subject}."
                    if matching_notes else f"I couldn't find notes matching {note_subject}. Try another subject or browse the Notes library."
                ),
                "intent": "notes",
                "subject": note_subject,
                "note_ids": [note["id"] for note in matching_notes],
            }
        return redirect(url_for("home", _anchor="career-mentor"))

    quick_history = session.get("home_quick_history", [])
    needs_full_mentor = len(question) > 280 or len(quick_history) >= 3 or any(
        phrase in question.casefold()
        for phrase in ("in detail", "step by step", "roadmap", "make me a plan", "compare")
    )
    if needs_full_mentor:
        exchanges = quick_history + [{"question": question, "answer": ""}]
        if session.get("user_id"):
            conversation_id = create_mentor_conversation(session["user_id"], exchanges)
            session.pop("home_quick_history", None)
            return redirect(url_for("chatbot", conversation_id=conversation_id))
        session["pending_home_exchanges"] = exchanges
        return redirect(url_for("login", next=url_for("resume_home_conversation")))

    answer = quick_subject_answer(question)
    quick_history = (quick_history + [{"question": question, "answer": answer}])[-3:]
    session["home_quick_history"] = quick_history
    session["home_quick_result"] = {
        "question": question,
        "answer": answer,
        "intent": "subject",
    }
    return redirect(url_for("home", _anchor="career-mentor"))


@app.route("/quick-help/continue", methods=["POST"])
def continue_quick_help():
    questions = request.form.getlist("quick_questions")[:3]
    answers = request.form.getlist("quick_answers")[:3]
    exchanges = [
        {"question": question[:2000], "answer": answers[index][:800] if index < len(answers) else ""}
        for index, question in enumerate(questions)
        if question.strip()
    ]
    if session.get("user_id"):
        conversation_id = create_mentor_conversation(session["user_id"], exchanges)
        session.pop("home_quick_history", None)
        return redirect(url_for("chatbot", conversation_id=conversation_id) if conversation_id else url_for("chatbot"))
    session["pending_home_exchanges"] = exchanges
    return redirect(url_for("login", next=url_for("resume_home_conversation")))


@app.route("/quick-help/resume")
@login_required
def resume_home_conversation():
    exchanges = session.pop("pending_home_exchanges", [])
    if not exchanges:
        flash("There is no saved quick-help conversation to continue.", "info")
        return redirect(url_for("chatbot"))
    conversation_id = create_mentor_conversation(session["user_id"], exchanges)
    session.pop("home_quick_history", None)
    return redirect(url_for("chatbot", conversation_id=conversation_id))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id") is not None:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, name, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Email or password is incorrect.", "error")
        else:
            pending_exchanges = session.get("pending_home_exchanges")
            session.clear()
            if pending_exchanges:
                session["pending_home_exchanges"] = pending_exchanges
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            next_url = request.args.get("next")
            return redirect(next_url if is_safe_local_url(next_url) else url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id") is not None:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        college = request.form.get("college", "").strip()
        branch = request.form.get("branch", "").strip()
        year = request.form.get("year", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all((name, email, college, branch, year, password, confirm_password)):
            flash("Please complete every field.", "error")
        elif password != confirm_password:
            flash("The passwords do not match.", "error")
        elif len(password) < 8:
            flash("Use a password with at least 8 characters.", "error")
        else:
            db = get_db()
            try:
                cursor = db.execute(
                    """INSERT INTO users (name, email, college, branch, year, password_hash)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (name, email, college, branch, year, generate_password_hash(password)),
                )
                db.commit()
            except sqlite3.IntegrityError:
                flash("An account with that email already exists. Please log in.", "error")
            else:
                pending_exchanges = session.get("pending_home_exchanges")
                session.clear()
                if pending_exchanges:
                    session["pending_home_exchanges"] = pending_exchanges
                session["user_id"] = cursor.lastrowid
                session["user_name"] = name
                flash("Your account is ready. Welcome to StudentHub AI!", "success")
                next_url = request.args.get("next")
                return redirect(next_url if is_safe_local_url(next_url) else url_for("dashboard"))

    return render_template("register.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/account")
@login_required
def account_center():
    db = get_db()
    user = db.execute(
        "SELECT name, email, college, branch, year, created_at FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    recent_notes = db.execute(
        """SELECT n.id, n.title, n.subject, n.branch, n.year, n.semester,
                  a.action, a.accessed_at
           FROM note_activity AS a
           JOIN study_notes AS n ON n.id = a.note_id
           WHERE a.user_id = ?
             AND a.id = (
                 SELECT recent.id FROM note_activity AS recent
                 WHERE recent.user_id = a.user_id AND recent.note_id = a.note_id
                 ORDER BY recent.accessed_at DESC, recent.id DESC LIMIT 1
             )
           ORDER BY a.accessed_at DESC, a.id DESC LIMIT 6""",
        (session["user_id"],),
    ).fetchall()
    conversations = db.execute(
        """SELECT c.id, c.title, c.updated_at,
                  (SELECT m.content FROM mentor_messages AS m
                   WHERE m.conversation_id = c.id
                   ORDER BY m.id DESC LIMIT 1) AS latest_message
           FROM mentor_conversations AS c
           WHERE c.user_id = ?
           ORDER BY c.updated_at DESC, c.id DESC LIMIT 8""",
        (session["user_id"],),
    ).fetchall()
    note_count = db.execute(
        "SELECT COUNT(DISTINCT note_id) FROM note_activity WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()[0]
    return render_template(
        "account.html",
        user=user,
        recent_notes=recent_notes,
        conversations=conversations,
        note_count=note_count,
    )


@app.route("/notes")
@login_required
def notes():
    db = get_db()
    filters = {
        "branch": request.args.get("branch", "").strip(),
        "year": request.args.get("year", "").strip(),
        "semester": request.args.get("semester", "").strip(),
        "subject": request.args.get("subject", "").strip(),
    }
    if filters["year"] not in NOTE_YEARS:
        filters["year"] = ""
    if filters["branch"] not in NOTE_BRANCHES:
        filters["branch"] = ""

    search_requested = bool(
        request.args.get("search")
        or request.args.get("upload")
        or filters["subject"]
        or filters["semester"]
    )
    if filters["branch"] and filters["year"] and not search_requested:
        return redirect(
            url_for("note_subjects", branch=filters["branch"], year=filters["year"])
        )

    if not search_requested and not filters["year"] and not filters["branch"]:
        return render_template(
            "notes_catalog.html",
            note_years=NOTE_YEARS,
        )

    if not search_requested and filters["year"] and not filters["branch"]:
        return redirect(url_for("note_branches", year=filters["year"]))

    if not search_requested and filters["branch"] and not filters["year"]:
        flash("Choose a year before browsing this branch.", "info")
        return redirect(url_for("notes"))

    conditions = []
    values = []
    for field in ("branch", "year", "semester"):
        if filters[field]:
            conditions.append(f"{field} = ?")
            values.append(filters[field])
    if filters["subject"]:
        conditions.append("subject LIKE ?")
        values.append(f"%{filters['subject']}%")
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    available_notes = db.execute(
        f"""SELECT id, title, branch, year, semester, subject, original_filename,
                   created_at
            FROM study_notes {where_clause}
            ORDER BY created_at DESC, id DESC""",
        values,
    ).fetchall()

    # Recommend different subjects in the same course context where possible.
    suggestion_conditions = []
    suggestion_values = []
    for field in ("branch", "year", "semester"):
        if filters[field]:
            suggestion_conditions.append(f"{field} = ?")
            suggestion_values.append(filters[field])
    matched_subjects = {
        note["subject"].casefold() for note in available_notes
    }
    if matched_subjects:
        placeholders = ", ".join("?" for _ in matched_subjects)
        suggestion_conditions.append(f"lower(subject) NOT IN ({placeholders})")
        suggestion_values.extend(sorted(matched_subjects))
    elif filters["subject"]:
        suggestion_conditions.append("subject NOT LIKE ?")
        suggestion_values.append(f"%{filters['subject']}%")
    suggestion_where = (
        f"WHERE {' AND '.join(suggestion_conditions)}"
        if suggestion_conditions
        else ""
    )
    suggested_notes = db.execute(
        f"""SELECT subject, COUNT(*) AS note_count,
                   MAX(created_at) AS latest_upload
            FROM study_notes {suggestion_where}
            GROUP BY lower(subject)
            ORDER BY note_count DESC, latest_upload DESC
            LIMIT 5""",
        suggestion_values,
    ).fetchall()

    suggested_subjects = []
    if not suggested_notes:
        excluded_subjects = matched_subjects
        if filters["subject"]:
            excluded_subjects.add(filters["subject"].casefold())
        suggested_subjects = [
            subject for subject in SUGGESTED_SUBJECTS
            if subject.casefold() not in excluded_subjects
        ][:5]

    return render_template(
        "notes.html",
        notes=available_notes,
        filters=filters,
        note_branches=NOTE_BRANCHES,
        note_years=NOTE_YEARS,
        note_semesters=NOTE_SEMESTERS,
        suggested_notes=suggested_notes,
        suggested_subjects=suggested_subjects,
        show_note_results=True,
    )


@app.route("/notes/branches")
@login_required
def note_branches():
    year = request.args.get("year", "").strip()
    if year not in NOTE_YEARS:
        flash("Choose a valid year to browse branches.", "error")
        return redirect(url_for("notes"))

    branches = [
        branch for branch in NOTE_BRANCHES
        if year == "1st Year" or branch != "Common (1st Year)"
    ]
    rows = get_db().execute(
        """SELECT branch, COUNT(*) AS pdf_count,
                  COUNT(DISTINCT lower(subject)) AS subject_count
           FROM study_notes WHERE year = ? GROUP BY branch""",
        (year,),
    ).fetchall()
    branch_stats = {
        row["branch"]: {
            "pdf_count": row["pdf_count"],
            "subject_count": row["subject_count"],
        }
        for row in rows
    }
    return render_template(
        "note_branches.html",
        year=year,
        branches=branches,
        branch_stats=branch_stats,
    )


@app.route("/notes/subjects")
@login_required
def note_subjects():
    branch = request.args.get("branch", "").strip()
    year = request.args.get("year", "").strip()
    if branch not in NOTE_BRANCHES or year not in NOTE_YEARS:
        flash("Choose a valid year and branch to browse subjects.", "error")
        return redirect(url_for("notes"))

    rows = get_db().execute(
        """SELECT id, title, subject, semester, original_filename, created_at
           FROM study_notes
           WHERE branch = ? AND year = ?
           ORDER BY lower(subject), semester, title""",
        (branch, year),
    ).fetchall()
    subjects_by_name = {}
    for row in rows:
        key = row["subject"].casefold()
        if key not in subjects_by_name:
            subjects_by_name[key] = {"subject": row["subject"], "notes": []}
        subjects_by_name[key]["notes"].append(row)
    subjects = list(subjects_by_name.values())
    return render_template(
        "note_subjects.html",
        branch=branch,
        year=year,
        subjects=subjects,
    )


@app.route("/notes/upload", methods=["POST"])
@login_required
def upload_note():
    uploaded_file = request.files.get("pdf")
    title = request.form.get("title", "").strip()
    branch = request.form.get("branch", "").strip()
    year = request.form.get("year", "").strip()
    semester = request.form.get("semester", "").strip()
    subject = request.form.get("subject", "").strip()
    upload_succeeded = False

    if not uploaded_file or not uploaded_file.filename:
        flash("Choose a PDF file to upload.", "error")
    elif (
        not title
        or not subject
        or len(title) > 120
        or len(subject) > 100
        or branch not in NOTE_BRANCHES
        or year not in NOTE_YEARS
        or semester not in NOTE_SEMESTERS
    ):
        flash("Complete the title and valid course details before uploading.", "error")
    else:
        original_filename = secure_filename(uploaded_file.filename)
        if not original_filename or Path(original_filename).suffix.lower() != ".pdf":
            flash("Only PDF files with a valid file name can be added.", "error")
        else:
            signature = uploaded_file.stream.read(5)
            uploaded_file.stream.seek(0)
            if signature != b"%PDF-":
                flash("This file does not appear to be a valid PDF.", "error")
            else:
                stored_filename = f"{uuid.uuid4().hex}.pdf"
                upload_folder = Path(app.config["UPLOAD_FOLDER"])
                upload_folder.mkdir(parents=True, exist_ok=True)
                destination = upload_folder / stored_filename
                uploaded_file.save(destination)
                try:
                    get_db().execute(
                        """INSERT INTO study_notes
                           (title, branch, year, semester, subject, stored_filename,
                            original_filename, uploaded_by)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            title,
                            branch,
                            year,
                            semester,
                            subject,
                            stored_filename,
                            original_filename,
                            session["user_id"],
                        ),
                    )
                    get_db().commit()
                    upload_succeeded = True
                except sqlite3.Error:
                    destination.unlink(missing_ok=True)
                    raise
                flash("Your PDF was added to the AKTU notes library.", "success")

    if upload_succeeded:
        return redirect(url_for("note_subjects", branch=branch, year=year))
    return redirect(
        url_for(
            "notes",
            upload=1,
            branch=branch if branch in NOTE_BRANCHES else None,
            year=year if year in NOTE_YEARS else None,
        )
    )


@app.route("/notes/<int:note_id>/download")
@login_required
def download_note(note_id):
    note = get_db().execute(
        "SELECT stored_filename, original_filename FROM study_notes WHERE id = ?",
        (note_id,),
    ).fetchone()
    if note is None:
        flash("That notes file could not be found.", "error")
        return redirect(url_for("notes"))

    file_path = Path(app.config["UPLOAD_FOLDER"]) / note["stored_filename"]
    if not file_path.is_file():
        flash("That PDF is currently unavailable.", "error")
        return redirect(url_for("notes"))
    record_note_activity(note_id, "download")
    return send_file(
        file_path,
        as_attachment=True,
        download_name=note["original_filename"],
    )


@app.route("/notes/<int:note_id>/preview")
@login_required
def preview_note(note_id):
    note = get_db().execute(
        "SELECT id, title, subject, branch, year, semester, stored_filename FROM study_notes WHERE id = ?",
        (note_id,),
    ).fetchone()
    if note is None:
        flash("That notes file could not be found.", "error")
        return redirect(url_for("notes"))

    file_path = Path(app.config["UPLOAD_FOLDER"]) / note["stored_filename"]
    if not file_path.is_file():
        flash("That PDF is currently unavailable.", "error")
        return redirect(url_for("notes"))
    record_note_activity(note_id, "preview")
    return_to = request.args.get("return_to", "")
    if is_safe_local_url(return_to):
        back_url = return_to
    elif note["branch"] in NOTE_BRANCHES and note["year"] in NOTE_YEARS:
        back_url = url_for("note_subjects", branch=note["branch"], year=note["year"])
    else:
        back_url = url_for("notes")
    return render_template("note_preview.html", note=note, back_url=back_url)


@app.route("/notes/<int:note_id>/file")
@login_required
def serve_note_preview(note_id):
    note = get_db().execute(
        "SELECT stored_filename, original_filename FROM study_notes WHERE id = ?",
        (note_id,),
    ).fetchone()
    if note is None:
        flash("That notes file could not be found.", "error")
        return redirect(url_for("notes"))

    file_path = Path(app.config["UPLOAD_FOLDER"]) / note["stored_filename"]
    if not file_path.is_file():
        flash("That PDF is currently unavailable.", "error")
        return redirect(url_for("notes"))
    response = send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=note["original_filename"],
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    return response


@app.errorhandler(413)
def upload_too_large(_error):
    flash("PDF files must be smaller than 20 MB.", "error")
    return redirect(url_for("notes"))


@app.route("/chatbot", methods=["GET", "POST"])
@login_required
def chatbot():
    db = get_db()
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        conversation_id = request.form.get("conversation_id", type=int)
        if not question:
            flash("Type a question before saving it to your mentor history.", "error")
            return redirect(url_for("chatbot", conversation_id=conversation_id))
        if len(question) > 2000:
            flash("Keep each mentor message under 2,000 characters.", "error")
            return redirect(url_for("chatbot", conversation_id=conversation_id))

        if conversation_id:
            conversation = db.execute(
                "SELECT id FROM mentor_conversations WHERE id = ? AND user_id = ?",
                (conversation_id, session["user_id"]),
            ).fetchone()
            if conversation is None:
                flash("That mentor conversation could not be found.", "error")
                return redirect(url_for("chatbot"))
            db.execute(
                "UPDATE mentor_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,),
            )
        else:
            title = " ".join(question.split())[:72]
            cursor = db.execute(
                "INSERT INTO mentor_conversations (user_id, title) VALUES (?, ?)",
                (session["user_id"], title),
            )
            conversation_id = cursor.lastrowid

        db.execute(
            "INSERT INTO mentor_messages (conversation_id, role, content) VALUES (?, 'user', ?)",
            (conversation_id, question),
        )
        db.commit()
        if request.form.get("ai_consent") == "yes":
            _, reply_error = generate_mentor_reply(conversation_id)
            if reply_error:
                flash(reply_error, "error")
        elif os.environ.get("OPENAI_API_KEY", "").strip():
            flash("Your question was saved. Select the OpenAI sharing checkbox if you want an AI reply.", "success")
        else:
            flash("Your question was saved. Add an OpenAI API key locally to enable Mentor replies.", "success")
        return redirect(url_for("chatbot", conversation_id=conversation_id))

    conversations = db.execute(
        """SELECT id, title, updated_at FROM mentor_conversations
           WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 20""",
        (session["user_id"],),
    ).fetchall()
    conversation_id = request.args.get("conversation_id", type=int)
    current_conversation = None
    messages = []
    if conversation_id:
        current_conversation = db.execute(
            "SELECT id, title FROM mentor_conversations WHERE id = ? AND user_id = ?",
            (conversation_id, session["user_id"]),
        ).fetchone()
        if current_conversation is None:
            flash("That mentor conversation could not be found.", "error")
            return redirect(url_for("chatbot"))
        messages = db.execute(
            "SELECT role, content, created_at FROM mentor_messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
    return render_template(
        "chatbot.html",
        conversations=conversations,
        current_conversation=current_conversation,
        messages=messages,
        ai_configured=bool(os.environ.get("OPENAI_API_KEY", "").strip()),
    )


init_db()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
