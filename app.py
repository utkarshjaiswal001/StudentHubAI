import os
import re
import secrets
import sqlite3
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from functools import wraps
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

import click
from flask import (
    Flask,
    abort,
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
# Logins last 7 days, then the student must sign in again.
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
    "SESSION_COOKIE_SECURE", "false"
).strip().lower() in {"1", "true", "yes"}
app.config["DATABASE"] = os.environ.get(
    "DATABASE_PATH", str(Path(app.instance_path) / "studenthub.sqlite3")
)
app.config["UPLOAD_FOLDER"] = os.environ.get(
    "UPLOAD_FOLDER", str(Path(app.instance_path) / "uploads")
)
app.config["OWNER_EMAIL"] = os.environ.get("OWNER_EMAIL", "").strip().lower()
MAX_NOTE_FILE_SIZE = 20 * 1024 * 1024
PPTX_MAX_UNPACKED_SIZE = 100 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_NOTE_FILE_SIZE + 1024 * 1024

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
COMMON_FIRST_YEAR_BRANCH = "Common (1st Year)"
# AKTU B.Tech: each year has two semesters (1st Year -> Semesters 1-2, and so on).
YEAR_SEMESTERS = {
    year: NOTE_SEMESTERS[index * 2:index * 2 + 2]
    for index, year in enumerate(NOTE_YEARS)
}
# 1st-year subjects are common, so students skip the semester step and see
# both semesters' subjects together.
YEARS_WITHOUT_SEMESTER_STEP = {"1st Year"}


def notes_browse_url(branch, year, semester=""):
    """URL for the next browsing step after choosing a branch (and semester)."""
    if year in YEARS_WITHOUT_SEMESTER_STEP:
        return url_for("note_subjects", branch=branch, year=year)
    if semester:
        return url_for("note_subjects", branch=branch, year=year, semester=semester)
    return url_for("note_semesters", branch=branch, year=year)


app.jinja_env.globals["notes_browse_url"] = notes_browse_url


def note_assignment_error(branch, year, semester):
    """Return an error message if branch/year/semester don't fit together, else None."""
    if branch not in NOTE_BRANCHES or year not in NOTE_YEARS or semester not in NOTE_SEMESTERS:
        return "Choose a valid branch, year, and semester."
    if branch == COMMON_FIRST_YEAR_BRANCH and year != "1st Year":
        return "Common (1st Year) notes must be assigned to 1st Year."
    if semester not in YEAR_SEMESTERS[year]:
        allowed = " or ".join(YEAR_SEMESTERS[year])
        return f"{year} notes must be in {allowed}."
    return None


def note_details_error(title, subject, branch, year, semester):
    """Validate note text fields and course assignment; return an error message or None."""
    if not title or len(title) > 120 or not subject or len(subject) > 100:
        return "Enter a title (up to 120 characters) and subject (up to 100 characters)."
    return note_assignment_error(branch, year, semester)


# Student profile branches match the notes library (Common is for notes only).
# "Other" covers branches the library doesn't have yet.
REGISTRATION_BRANCHES = [
    branch for branch in NOTE_BRANCHES if branch != COMMON_FIRST_YEAR_BRANCH
] + ["Other"]
LEGACY_BRANCH_NAMES = {"Computer Science": "Computer Science Engineering"}


def my_notes_url(branch, year):
    """Shortcut to a student's own notes: their branch + year when possible."""
    branch = LEGACY_BRANCH_NAMES.get(branch, branch)
    if year not in NOTE_YEARS:
        return url_for("notes")
    if year == "1st Year" or branch not in NOTE_BRANCHES:
        # 1st year picks Common or their branch; unknown branches pick from the list.
        return url_for("note_branches", year=year)
    return notes_browse_url(branch, year)


def profile_error(name, college, branch, year):
    """Validate editable profile fields; return an error message or None."""
    if not 2 <= len(name) <= 80 or contains_control_characters(name):
        return "Enter a name between 2 and 80 characters."
    if not 2 <= len(college) <= 120 or contains_control_characters(college):
        return "Enter a college name between 2 and 120 characters."
    if branch not in REGISTRATION_BRANCHES:
        return "Choose a valid branch."
    if year not in NOTE_YEARS:
        return "Choose a valid year."
    return None
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SUGGESTED_SUBJECTS = [
    "Python Programming",
    "Data Structures",
    "DBMS",
    "Operating System",
    "Computer Networks",
    "Artificial Intelligence",
    "Machine Learning",
]
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-6.1-sol")
MAX_CONVERSATION_HISTORY = 80
MAX_FAILED_LOGINS = 5
LOGIN_LOCK_MINUTES = 15
# Anti-spam limits (per rolling hour).
MAX_REPORTS_PER_USER_HOUR = 5
MAX_ANONYMOUS_REPORTS_HOUR = 20
MAX_REGISTRATIONS_HOUR = 30


def validate_pptx_stream(stream):
    """Check a PPTX ZIP container without extracting its contents to disk."""
    stream.seek(0)
    try:
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            total_size = sum(entry.file_size for entry in entries)
            slide_names = [
                entry.filename for entry in entries
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", entry.filename)
            ]
            if (
                "[Content_Types].xml" not in names
                or "ppt/presentation.xml" not in names
                or not slide_names
                or len(slide_names) > 100
                or total_size > PPTX_MAX_UNPACKED_SIZE
            ):
                return False
            for entry_name in ("[Content_Types].xml", "ppt/presentation.xml", slide_names[0]):
                entry = archive.getinfo(entry_name)
                if entry.file_size > 2 * 1024 * 1024:
                    return False
                ET.fromstring(archive.read(entry_name))
        return True
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile, ET.ParseError):
        return False
    finally:
        stream.seek(0)


def extract_pptx_slide_text(file_path):
    """Return a small, same-site text preview for a PowerPoint presentation."""
    slides = []
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    try:
        with zipfile.ZipFile(file_path) as archive:
            names = sorted(
                (name for name in archive.namelist()
                 if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                key=lambda name: int(re.search(r"slide(\d+)\.xml$", name).group(1)),
            )[:100]
            for name in names:
                info = archive.getinfo(name)
                if info.file_size > 2 * 1024 * 1024:
                    continue
                root = ET.fromstring(archive.read(name))
                text = " ".join(
                    item.text.strip() for item in root.findall(".//a:t", namespace)
                    if item.text and item.text.strip()
                )[:4000]
                number = int(re.search(r"slide(\d+)\.xml$", name).group(1))
                slides.append({"number": number, "text": text})
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError):
        return []
    return slides


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
    student_profile = db.execute(
        """SELECT u.branch, u.year
           FROM mentor_conversations AS c
           JOIN users AS u ON u.id = c.user_id
           WHERE c.id = ?""",
        (conversation_id,),
    ).fetchone()
    profile_context = ""
    if student_profile:
        profile_context = (
            "\nStudent's saved academic profile (share only for this opted-in reply): "
            f"stream/branch: {student_profile['branch']}; study year: {student_profile['year']}."
        )
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
                "You are StudentHub AI's friendly study and career mentor for engineering students. "
                "Hold a natural, useful conversation and answer the question asked; do not force "
                "career advice into ordinary chat. Use clear language, practical examples, and "
                "step-by-step explanations for study questions. When a student asks about career "
                "options, use their saved stream/year and the conversation's stated interests to "
                "compare relevant core-field and adjacent-field paths. For example, for ECE, "
                "consider embedded systems/firmware, VLSI/FPGA, telecom/IoT, and software/IT "
                "paths; explain what each involves, the skills to build, a starter project, and "
                "a realistic next step. Do not assume a student must stay in their stream or "
                "switch to IT, and do not stereotype based on their profile. If key information "
                "such as interests, preferred work, or time available is missing, give useful "
                "initial options and ask one focused follow-up to narrow them. Be honest about "
                "uncertainty, avoid invented course requirements or hiring claims, and never "
                "promise placements, salaries, or outcomes."
                f"{profile_context}"
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
        user_columns = {row["name"] for row in get_db().execute("PRAGMA table_info(users)")}
        if "is_owner" not in user_columns:
            get_db().execute("ALTER TABLE users ADD COLUMN is_owner INTEGER NOT NULL DEFAULT 0")
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
                category TEXT NOT NULL DEFAULT 'other',
                message TEXT NOT NULL CHECK (length(message) <= 2000),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        suggestion_columns = {
            row["name"] for row in get_db().execute("PRAGMA table_info(suggestions)")
        }
        if "category" not in suggestion_columns:
            get_db().execute(
                "ALTER TABLE suggestions ADD COLUMN category TEXT NOT NULL DEFAULT 'other'"
            )
        if "status" not in suggestion_columns:
            get_db().execute(
                "ALTER TABLE suggestions ADD COLUMN status TEXT NOT NULL DEFAULT 'open'"
            )
        user_columns = {row["name"] for row in get_db().execute("PRAGMA table_info(users)")}
        if "must_change_password" not in user_columns:
            get_db().execute(
                "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
            )
        for old_branch, new_branch in LEGACY_BRANCH_NAMES.items():
            get_db().execute(
                "UPDATE users SET branch = ? WHERE branch = ?", (new_branch, old_branch)
            )
        get_db().execute(
            """CREATE TABLE IF NOT EXISTS login_attempts (
                email TEXT PRIMARY KEY COLLATE NOCASE,
                failed_count INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT
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


def owner_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            flash("Please log in with the notes owner account to upload notes.", "info")
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        owner = get_db().execute(
            "SELECT is_owner FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
        if owner is None or not owner["is_owner"]:
            abort(403)
        return view(**kwargs)

    return wrapped_view


def safe_local_path(target):
    """Return a same-site path for redirects, or None for anything unsafe."""
    target = (target or "").strip()
    if not target or not target.startswith("/") or target.startswith("//"):
        return None
    decoded = unquote(target)
    if "\\" in target or "\\" in decoded:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in decoded):
        return None
    try:
        parts = urlsplit(target)
    except ValueError:
        return None
    if parts.scheme or parts.netloc:
        return None
    return urlunsplit(("", "", parts.path, parts.query, parts.fragment))


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def contains_control_characters(value):
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def record_note_activity(note_id, action):
    user_id = session.get("user_id")
    if user_id is None:
        return
    db = get_db()
    db.execute(
        "INSERT INTO note_activity (user_id, note_id, action) VALUES (?, ?, ?)",
        (user_id, note_id, action),
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
        # 1st-year common subjects
        (("engineering physics", "physics"), "Engineering Physics (1st year) usually covers quantum mechanics basics, wave optics (interference, diffraction, polarization), lasers, fibre optics, and electromagnetism. Learn the key derivations and solve numericals unit by unit."),
        (("engineering chemistry", "chemistry"), "Engineering Chemistry covers water treatment, fuels and combustion, polymers, corrosion, electrochemistry, and spectroscopy basics. Make short notes of reactions and practise numericals on hardness and calorific value."),
        (("engineering mathematics", "mathematics", "maths", "math ", "calculus", "matrices", "differential equation"), "Engineering Mathematics builds on calculus, matrices, differential equations, and vector calculus, plus Laplace/Fourier transforms in later semesters. Practise standard problem types from each unit and previous-year papers."),
        (("basic electrical", "beee", "electrical engineering basics"), "Basic Electrical Engineering covers DC circuits (KCL, KVL, network theorems), AC fundamentals and phasors, three-phase systems, transformers, and machines. Practise circuit numericals and phasor diagrams."),
        (("programming for problem solving", "c programming", " pps "), "Programming for Problem Solving (C) covers data types, operators, conditions, loops, functions, arrays, strings, pointers, structures, and file handling. Write and dry-run small programs daily."),
        (("engineering graphics", "engineering drawing", "autocad"), "Engineering Graphics covers projections of points, lines, planes and solids, sections, isometric views, and basic CAD. Practise neat drawings and visualise views step by step."),
        # ECE core subjects
        (("signals and systems", "signal and system", "signals"), "Signals and Systems covers signal classification, LTI systems, convolution, Fourier series and transform, Laplace and Z-transform, and sampling. Practise convolution and transform problems with their properties."),
        (("analog communication", "digital communication", "communication system", "modulation"), "Communication Systems covers AM/FM modulation, noise, sampling and PCM, digital modulation (ASK, FSK, PSK, QAM), and basic information theory. Draw block diagrams and practise bandwidth and SNR numericals."),
        (("digital electronics", "digital logic", "logic gate", "flip flop", "k-map", "kmap"), "Digital Electronics covers number systems, Boolean algebra and K-maps, combinational circuits (adders, multiplexers), flip-flops, counters, and registers. Practise K-map simplification and timing diagrams."),
        (("analog circuit", "analog electronics", "electronic devices", "diode", "transistor", "bjt", "mosfet", "op-amp", "op amp"), "Analog electronics covers diodes, BJTs and MOSFETs (biasing and small-signal models), amplifiers, feedback, oscillators, and op-amp circuits. Practise biasing and gain calculations."),
        (("network analysis", "network theory", "circuit theory", "network synthesis"), "Network Analysis covers mesh and nodal analysis, network theorems, transient response, two-port parameters, and resonance. Practise solving circuits by more than one method to check answers."),
        (("electromagnetic", "emft", "emt ", "transmission line", "antenna"), "Electromagnetic Field Theory covers vector calculus, electrostatics, magnetostatics, Maxwell's equations, wave propagation, transmission lines, and antenna basics. Learn Maxwell's equations in both forms."),
        (("microprocessor", "microcontroller", "8085", "8086", "8051"), "Microprocessors and Microcontrollers cover 8085/8086 architecture, addressing modes, instruction sets, assembly programming, interrupts, and 8051 interfacing. Practise small assembly programs and timing diagrams."),
        (("control system",), "Control Systems covers transfer functions, block diagram reduction, time response, stability (Routh-Hurwitz, root locus), and frequency response (Bode, Nyquist). Practise one example of each method."),
        (("vlsi", "cmos", "verilog", "fpga"), "VLSI Design covers MOS transistor theory, CMOS inverter and logic, fabrication basics, timing and power, and HDL design with Verilog. Write small Verilog modules and simulate them."),
        (("embedded system", "arduino", " iot ", "internet of things"), "Embedded Systems combine a microcontroller, sensors, and firmware. Start with C on a board like Arduino or STM32: GPIO, timers, interrupts, UART/I2C/SPI, then build a small IoT project."),
        # Computer science subjects
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
    return "I can give quick pointers on 1st-year subjects, ECE and CS core subjects, and placement basics. For a longer explanation or a multi-step plan, continue this thread in the full AI Mentor."


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


def utc_now():
    return datetime.now(timezone.utc)


def login_locked_minutes(email):
    """Minutes left on a login lock for this email, or 0 if not locked."""
    row = get_db().execute(
        "SELECT locked_until FROM login_attempts WHERE email = ?", (email,)
    ).fetchone()
    if row is None or not row["locked_until"]:
        return 0
    remaining = datetime.fromisoformat(row["locked_until"]) - utc_now()
    if remaining.total_seconds() <= 0:
        return 0
    return max(1, int(remaining.total_seconds() // 60) + 1)


def record_failed_login(email):
    db = get_db()
    row = db.execute(
        "SELECT failed_count, locked_until FROM login_attempts WHERE email = ?", (email,)
    ).fetchone()
    count = 1
    if row is not None:
        lock_expired = row["locked_until"] and datetime.fromisoformat(row["locked_until"]) <= utc_now()
        count = 1 if lock_expired else row["failed_count"] + 1
    locked_until = None
    if count >= MAX_FAILED_LOGINS:
        locked_until = (utc_now() + timedelta(minutes=LOGIN_LOCK_MINUTES)).isoformat()
    db.execute(
        """INSERT INTO login_attempts (email, failed_count, locked_until) VALUES (?, ?, ?)
           ON CONFLICT(email) DO UPDATE SET failed_count = excluded.failed_count,
                                            locked_until = excluded.locked_until""",
        (email, count, locked_until),
    )
    db.commit()


def clear_failed_logins(email):
    get_db().execute("DELETE FROM login_attempts WHERE email = ?", (email,))
    get_db().commit()


def start_user_session(user_id, user_name, welcome_message):
    """Reset the session for a newly signed-in user (keeps a pending quick-help thread)."""
    pending_exchanges = session.get("pending_home_exchanges")
    session.clear()
    if pending_exchanges:
        session["pending_home_exchanges"] = pending_exchanges
    session.permanent = True
    session["user_id"] = user_id
    session["user_name"] = user_name
    session["welcome_message"] = welcome_message


@app.context_processor
def inject_user_state():
    user_is_owner = False
    if session.get("user_id") is not None:
        owner = get_db().execute(
            "SELECT is_owner FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
        user_is_owner = bool(owner and owner["is_owner"])
    my_notes = None
    if session.get("user_id") is not None:
        profile = get_db().execute(
            "SELECT branch, year FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
        if profile is not None:
            my_notes = my_notes_url(profile["branch"], profile["year"])
    return {
        "my_notes_url": my_notes,
        "is_logged_in": session.get("user_id") is not None,
        "is_owner": user_is_owner,
        "current_user_name": session.get("user_name"),
        "ai_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "csrf_token": get_csrf_token(),
    }


@app.before_request
def require_new_password_after_reset():
    """After an admin reset, the student must pick a new password before anything else."""
    if session.get("user_id") is None or request.endpoint in {
        "change_password", "logout", "static", "health_check",
    }:
        return None
    user = get_db().execute(
        "SELECT must_change_password FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()
    if user is None:
        # The account no longer exists (e.g. deleted); sign the browser out.
        session.clear()
        return redirect(url_for("login"))
    if user["must_change_password"]:
        flash("Your password was reset. Choose a new password to continue.", "info")
        return redirect(url_for("change_password"))
    return None


@app.before_request
def protect_state_changing_requests():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    expected = session.get("csrf_token")
    supplied = request.form.get("csrf_token", "")
    if not expected or not supplied or not secrets.compare_digest(supplied, expected):
        abort(400, "Your form session expired. Please reload the page and try again.")
    return None


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


@app.after_request
def prevent_stale_home_after_login(response):
    # Session-specific navigation must not be restored from a stale browser cache.
    if request.endpoint in {"home", "login", "register"} or session.get("user_id") is not None:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def home():
    quick_result = session.pop("home_quick_result", None)
    quick_notes = []
    if quick_result and quick_result.get("note_ids"):
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
        welcome_message=session.pop("welcome_message", None),
    )


@app.get("/health")
def health_check():
    try:
        get_db().execute("SELECT 1").fetchone()
    except sqlite3.Error:
        app.logger.exception("StudentHub health check failed")
        return {"status": "unavailable"}, 503
    return {"status": "ok"}, 200


def reports_limit_reached(user_id):
    if user_id is not None:
        query, params, limit = (
            "SELECT COUNT(*) FROM suggestions WHERE user_id = ? "
            "AND created_at >= datetime('now', '-1 hour')",
            (user_id,), MAX_REPORTS_PER_USER_HOUR,
        )
    else:
        query, params, limit = (
            "SELECT COUNT(*) FROM suggestions WHERE user_id IS NULL "
            "AND created_at >= datetime('now', '-1 hour')",
            (), MAX_ANONYMOUS_REPORTS_HOUR,
        )
    return get_db().execute(query, params).fetchone()[0] >= limit


def registrations_limit_reached():
    recent = get_db().execute(
        "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 hour')"
    ).fetchone()[0]
    return recent >= MAX_REGISTRATIONS_HOUR


@app.route("/suggestion", methods=["POST"])
def submit_suggestion():
    suggestion = request.form.get("suggestion", "").strip()
    category = request.form.get("category", "other").strip().lower()
    allowed_categories = {"broken_link", "login", "notes", "mentor", "other"}
    if not suggestion:
        flash("Describe the issue before submitting.", "error")
    elif len(suggestion) > 2000:
        flash("Keep your report under 2,000 characters.", "error")
    elif category not in allowed_categories:
        flash("Choose a valid issue category.", "error")
    elif reports_limit_reached(session.get("user_id")):
        flash("Too many reports in the last hour. Please try again later.", "error")
    else:
        get_db().execute(
            "INSERT INTO suggestions (user_id, category, message) VALUES (?, ?, ?)",
            (session.get("user_id"), category, suggestion),
        )
        get_db().commit()
        flash("Thanks—your issue report was submitted.", "success")
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
    # Only use the history the server saved; never trust answers sent by the browser.
    exchanges = session.get("home_quick_history", [])[-3:]
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
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        locked_minutes = login_locked_minutes(email)
        user = None
        if not locked_minutes:
            user = get_db().execute(
                "SELECT id, name, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()

        if locked_minutes:
            flash(
                f"Too many wrong attempts. Try again in {locked_minutes} minute"
                f"{'s' if locked_minutes != 1 else ''}.",
                "error",
            )
        elif user is None or not check_password_hash(user["password_hash"], password):
            if email:
                record_failed_login(email)
            flash("Email or password is incorrect.", "error")
        else:
            clear_failed_logins(email)
            start_user_session(user["id"], user["name"], f"Welcome back, {user['name']}!")
            next_url = safe_local_path(request.args.get("next"))
            if next_url:
                return redirect(next_url)
            return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id") is not None:
        return redirect(url_for("home"))

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
        elif len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
            flash("Enter a valid email address.", "error")
        elif profile_error(name, college, branch, year):
            flash(profile_error(name, college, branch, year), "error")
        elif password != confirm_password:
            flash("The passwords do not match.", "error")
        elif not 8 <= len(password) <= 128:
            flash("Use a password with 8 to 128 characters.", "error")
        elif registrations_limit_reached():
            flash("Too many new accounts right now. Please try again in an hour.", "error")
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
                start_user_session(
                    cursor.lastrowid, name, f"Welcome, {name}! Your account is ready."
                )
                return redirect(url_for("home"))

    return render_template(
        "register.html", student_branches=REGISTRATION_BRANCHES, note_years=NOTE_YEARS
    )


@app.route("/logout", methods=["POST"])
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
           ORDER BY c.updated_at DESC, c.id DESC LIMIT ?""",
        (session["user_id"], MAX_CONVERSATION_HISTORY),
    ).fetchall()
    conversation_count = db.execute(
        "SELECT COUNT(*) FROM mentor_conversations WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()[0]
    note_count = db.execute(
        "SELECT COUNT(DISTINCT note_id) FROM note_activity WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()[0]
    return render_template(
        "account.html",
        user=user,
        recent_notes=recent_notes,
        conversations=conversations,
        conversation_count=conversation_count,
        note_count=note_count,
    )


@app.route("/account/profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    db = get_db()
    user = db.execute(
        "SELECT name, email, college, branch, year FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    form = dict(user)
    if request.method == "POST":
        form.update({
            field: request.form.get(field, "").strip()
            for field in ("name", "college", "branch", "year")
        })
        error = profile_error(form["name"], form["college"], form["branch"], form["year"])
        if error:
            flash(error, "error")
        else:
            db.execute(
                "UPDATE users SET name = ?, college = ?, branch = ?, year = ? WHERE id = ?",
                (form["name"], form["college"], form["branch"], form["year"], session["user_id"]),
            )
            db.commit()
            session["user_name"] = form["name"]
            flash("Your profile was updated.", "success")
            return redirect(url_for("account_center"))
    return render_template(
        "account_settings.html", section="profile", form=form,
        student_branches=REGISTRATION_BRANCHES, note_years=NOTE_YEARS,
    )


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    db = get_db()
    user = db.execute(
        "SELECT email, password_hash, must_change_password FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not check_password_hash(user["password_hash"], current):
            flash("Your current password is incorrect.", "error")
        elif new != confirm:
            flash("The new passwords do not match.", "error")
        elif not 8 <= len(new) <= 128:
            flash("Use a new password with 8 to 128 characters.", "error")
        elif check_password_hash(user["password_hash"], new):
            flash("Choose a password different from your current one.", "error")
        else:
            db.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
                (generate_password_hash(new), session["user_id"]),
            )
            db.commit()
            flash("Your password was changed.", "success")
            return redirect(url_for("account_center"))
    return render_template(
        "account_settings.html", section="password",
        forced=bool(user["must_change_password"]),
    )


@app.route("/account/delete", methods=["GET", "POST"])
@login_required
def delete_account():
    db = get_db()
    user = db.execute(
        "SELECT email, password_hash, is_owner FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    if user["is_owner"]:
        flash("The owner account can't be deleted from the website.", "error")
        return redirect(url_for("account_center"))
    if request.method == "POST":
        if not check_password_hash(user["password_hash"], request.form.get("password", "")):
            flash("Your password is incorrect. Your account was not deleted.", "error")
        else:
            # Chats and activity are removed with the account; issue reports stay anonymous.
            try:
                db.execute("DELETE FROM users WHERE id = ?", (session["user_id"],))
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                flash("This account still owns library notes, so it can't be deleted. Contact the admin.", "error")
                return redirect(url_for("account_center"))
            clear_failed_logins(user["email"])
            session.clear()
            flash("Your account and its saved data were deleted.", "info")
            return redirect(url_for("home"))
    return render_template("account_settings.html", section="delete")


@app.route("/admin")
@owner_required
def admin_access():
    db = get_db()
    stats = {
        "students": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "notes": db.execute("SELECT COUNT(*) FROM study_notes").fetchone()[0],
        "conversations": db.execute("SELECT COUNT(*) FROM mentor_conversations").fetchone()[0],
    }
    conversations = db.execute(
        """SELECT c.id, c.title, c.updated_at, u.name AS student_name,
                  u.branch, u.year,
                  (SELECT m.content FROM mentor_messages AS m
                   WHERE m.conversation_id = c.id
                   ORDER BY m.id DESC LIMIT 1) AS latest_message
           FROM mentor_conversations AS c
           JOIN users AS u ON u.id = c.user_id
           ORDER BY c.updated_at DESC, c.id DESC LIMIT ?""",
        (MAX_CONVERSATION_HISTORY,),
    ).fetchall()
    selected_id = request.args.get("conversation_id", type=int)
    selected_conversation = None
    selected_messages = []
    if selected_id:
        selected_conversation = db.execute(
            """SELECT c.id, c.title, c.updated_at, u.name AS student_name,
                      u.branch, u.year
               FROM mentor_conversations AS c
               JOIN users AS u ON u.id = c.user_id WHERE c.id = ?""",
            (selected_id,),
        ).fetchone()
        if selected_conversation is None:
            abort(404)
        selected_messages = db.execute(
            """SELECT role, content, created_at FROM mentor_messages
               WHERE conversation_id = ? ORDER BY id DESC LIMIT 200""",
            (selected_id,),
        ).fetchall()[::-1]
    note_search = request.args.get("q", "").strip()[:100]
    note_pattern = f"%{note_search}%"
    library_notes = db.execute(
        """SELECT id, title, subject, branch, year, semester, original_filename, created_at
           FROM study_notes
           WHERE ? = '' OR title LIKE ? OR subject LIKE ? OR branch LIKE ?
           ORDER BY created_at DESC, id DESC LIMIT 200""",
        (note_search, note_pattern, note_pattern, note_pattern),
    ).fetchall()
    show_closed = request.args.get("reports") == "all"
    reports = db.execute(
        f"""SELECT s.id, s.category, s.message, s.status, s.created_at,
                   u.name AS student_name, u.email AS student_email
            FROM suggestions AS s LEFT JOIN users AS u ON u.id = s.user_id
            {'' if show_closed else "WHERE s.status = 'open'"}
            ORDER BY s.created_at DESC, s.id DESC LIMIT 100"""
    ).fetchall()
    open_report_count = db.execute(
        "SELECT COUNT(*) FROM suggestions WHERE status = 'open'"
    ).fetchone()[0]
    return render_template(
        "admin.html", stats=stats, conversations=conversations,
        selected_conversation=selected_conversation,
        selected_messages=selected_messages,
        library_notes=library_notes, note_search=note_search,
        reports=reports, show_closed=show_closed,
        open_report_count=open_report_count,
        ai_model=OPENAI_MODEL,
        ai_configured=bool(os.environ.get("OPENAI_API_KEY", "").strip()),
    )


def canonical_subject(subject):
    """Reuse an existing subject's spelling so "dbms" and "DBMS" stay one subject."""
    row = get_db().execute(
        """SELECT subject FROM study_notes WHERE lower(subject) = lower(?)
           GROUP BY subject ORDER BY COUNT(*) DESC LIMIT 1""",
        (subject,),
    ).fetchone()
    return row["subject"] if row else subject


def known_subjects():
    return [
        row["subject"] for row in get_db().execute(
            "SELECT subject FROM study_notes GROUP BY lower(subject) ORDER BY lower(subject)"
        )
    ]


def get_note_or_404(note_id):
    note = get_db().execute(
        """SELECT id, title, subject, branch, year, semester, stored_filename,
                  original_filename, created_at
           FROM study_notes WHERE id = ?""",
        (note_id,),
    ).fetchone()
    if note is None:
        abort(404)
    return note


@app.route("/admin/notes/<int:note_id>/edit", methods=["GET", "POST"])
@owner_required
def edit_note(note_id):
    note = get_note_or_404(note_id)
    form = dict(note)
    if request.method == "POST":
        form.update({
            field: request.form.get(field, "").strip()
            for field in ("title", "subject", "branch", "year", "semester")
        })
        details_error = note_details_error(
            form["title"], form["subject"], form["branch"], form["year"], form["semester"]
        )
        if details_error:
            flash(details_error, "error")
        else:
            db = get_db()
            if form["subject"].casefold() != note["subject"].casefold():
                form["subject"] = canonical_subject(form["subject"])
            db.execute(
                """UPDATE study_notes SET title = ?, subject = ?, branch = ?, year = ?, semester = ?
                   WHERE id = ?""",
                (form["title"], form["subject"], form["branch"], form["year"],
                 form["semester"], note_id),
            )
            db.commit()
            flash(f"Saved changes to “{form['title']}”.", "success")
            return redirect(url_for("admin_access", _anchor="admin-notes"))
    return render_template(
        "note_edit.html",
        note=note,
        form=form,
        known_subjects=known_subjects(),
        note_branches=NOTE_BRANCHES,
        note_years=NOTE_YEARS,
        note_semesters=NOTE_SEMESTERS,
    )


@app.route("/admin/notes/<int:note_id>/delete", methods=["GET", "POST"])
@owner_required
def delete_note(note_id):
    note = get_note_or_404(note_id)
    if request.method == "POST":
        db = get_db()
        db.execute("DELETE FROM study_notes WHERE id = ?", (note_id,))
        db.commit()
        (Path(app.config["UPLOAD_FOLDER"]) / note["stored_filename"]).unlink(missing_ok=True)
        flash(f"Deleted “{note['title']}” from the notes library.", "success")
        return redirect(url_for("admin_access", _anchor="admin-notes"))
    return render_template("note_delete.html", note=note)


@app.route("/admin/reports/<int:report_id>/status", methods=["POST"])
@owner_required
def update_report_status(report_id):
    status = request.form.get("status", "")
    if status not in {"open", "closed"}:
        abort(400)
    db = get_db()
    cursor = db.execute(
        "UPDATE suggestions SET status = ? WHERE id = ?", (status, report_id)
    )
    db.commit()
    if cursor.rowcount == 0:
        abort(404)
    flash("Issue report closed." if status == "closed" else "Issue report reopened.", "success")
    return redirect(url_for("admin_access", _anchor="admin-reports"))


@app.route("/admin/students/reset-password", methods=["POST"])
@owner_required
def reset_student_password():
    email = request.form.get("email", "").strip().lower()
    db = get_db()
    student = db.execute(
        "SELECT id, name, is_owner FROM users WHERE email = ?", (email,)
    ).fetchone()
    if student is None:
        flash("No student account uses that email.", "error")
    elif student["is_owner"]:
        flash("The owner account can't be reset here. Use Change password on your Account page.", "error")
    else:
        temporary_password = secrets.token_urlsafe(9)
        db.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE id = ?",
            (generate_password_hash(temporary_password), student["id"]),
        )
        db.commit()
        clear_failed_logins(email)
        flash(
            f"Temporary password for {student['name']}: {temporary_password} — "
            "share it privately. They must choose a new password after signing in.",
            "success",
        )
    return redirect(url_for("admin_access", _anchor="admin-students"))


@app.route("/notes")
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
        or filters["subject"]
        or filters["semester"]
    )
    if filters["branch"] and filters["year"] and not search_requested:
        return redirect(notes_browse_url(filters["branch"], filters["year"]))

    if not search_requested and not filters["year"] and not filters["branch"]:
        suggested_notes = db.execute(
            """SELECT subject, COUNT(*) AS note_count
               FROM study_notes GROUP BY lower(subject)
               ORDER BY note_count DESC, MAX(created_at) DESC LIMIT 5"""
        ).fetchall()
        suggested_subjects = [
            subject for subject in SUGGESTED_SUBJECTS
            if subject.casefold() not in {row["subject"].casefold() for row in suggested_notes}
        ][:5] if not suggested_notes else []
        return render_template(
            "notes_catalog.html",
            note_years=NOTE_YEARS,
            suggested_notes=suggested_notes,
            suggested_subjects=suggested_subjects,
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
def note_branches():
    year = request.args.get("year", "").strip()
    if year not in NOTE_YEARS:
        flash("Choose a valid year to browse branches.", "error")
        return redirect(url_for("notes"))

    # 1st Year lists Common first, then branch-specific first-year notes.
    # Later years never show the Common first-year option.
    branches = [
        branch for branch in NOTE_BRANCHES
        if year == "1st Year" or branch != COMMON_FIRST_YEAR_BRANCH
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


def valid_branch_for_year(branch, year):
    return (
        branch in NOTE_BRANCHES
        and year in NOTE_YEARS
        and (branch != COMMON_FIRST_YEAR_BRANCH or year == "1st Year")
    )


@app.route("/notes/semesters")
def note_semesters():
    branch = request.args.get("branch", "").strip()
    year = request.args.get("year", "").strip()
    if not valid_branch_for_year(branch, year):
        flash("Choose a valid year and branch to browse semesters.", "error")
        return redirect(url_for("notes"))
    if year in YEARS_WITHOUT_SEMESTER_STEP:
        return redirect(notes_browse_url(branch, year))

    rows = get_db().execute(
        """SELECT semester, COUNT(*) AS pdf_count,
                  COUNT(DISTINCT lower(subject)) AS subject_count
           FROM study_notes WHERE branch = ? AND year = ? GROUP BY semester""",
        (branch, year),
    ).fetchall()
    semester_stats = {
        row["semester"]: {
            "pdf_count": row["pdf_count"],
            "subject_count": row["subject_count"],
        }
        for row in rows
    }
    return render_template(
        "note_semesters.html",
        branch=branch,
        year=year,
        semesters=YEAR_SEMESTERS[year],
        semester_stats=semester_stats,
    )


@app.route("/notes/subjects")
def note_subjects():
    branch = request.args.get("branch", "").strip()
    year = request.args.get("year", "").strip()
    semester = request.args.get("semester", "").strip()
    if not valid_branch_for_year(branch, year):
        flash("Choose a valid year and branch to browse subjects.", "error")
        return redirect(url_for("notes"))
    if year in YEARS_WITHOUT_SEMESTER_STEP:
        semester = ""
    elif semester not in YEAR_SEMESTERS[year]:
        # Links without a semester go to the semester chooser.
        return redirect(url_for("note_semesters", branch=branch, year=year))

    search = request.args.get("q", "").strip()[:100]
    query = """SELECT id, title, subject, semester, original_filename, created_at,
                      created_at >= datetime('now', '-7 days') AS is_new
               FROM study_notes WHERE branch = ? AND year = ?"""
    params = [branch, year]
    if semester:
        query += " AND semester = ?"
        params.append(semester)
    if search:
        query += " AND (subject LIKE ? OR title LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    rows = get_db().execute(
        query + " ORDER BY lower(subject), semester, title", params
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
        semester=semester,
        search=search,
        subjects=subjects,
    )


@app.route("/notes/upload", methods=["GET", "POST"])
@owner_required
def upload_note():
    """Allow only the designated owner account to add course files to the library."""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        branch = request.form.get("branch", "").strip()
        year = request.form.get("year", "").strip()
        semester = request.form.get("semester", "").strip()
        uploaded_file = request.files.get("file")
        details_error = note_details_error(title, subject, branch, year, semester)
        if details_error:
            flash(details_error, "error")
        elif uploaded_file is None or not uploaded_file.filename:
            flash("Choose a PDF or PowerPoint (.pptx) file to upload.", "error")
        else:
            original_filename = secure_filename(uploaded_file.filename)
            extension = Path(original_filename).suffix.lower() if original_filename else ""
            uploaded_size = uploaded_file.stream.seek(0, os.SEEK_END)
            uploaded_file.stream.seek(0)
            file_signature = uploaded_file.stream.read(5)
            uploaded_file.stream.seek(0)
            if extension not in {".pdf", ".pptx"}:
                flash("Choose a PDF or PowerPoint (.pptx) file.", "error")
            elif uploaded_size > MAX_NOTE_FILE_SIZE:
                flash("Files must be smaller than 20 MB.", "error")
            elif extension == ".pdf" and file_signature != b"%PDF-":
                flash("The selected file is not a valid PDF.", "error")
            elif extension == ".pptx" and (
                not file_signature.startswith(b"PK")
                or not validate_pptx_stream(uploaded_file.stream)
            ):
                flash("The selected file is not a valid PowerPoint presentation.", "error")
            else:
                uploaded_file.stream.seek(0)
                stored_filename = f"{uuid.uuid4().hex}{extension}"
                upload_folder = Path(app.config["UPLOAD_FOLDER"])
                upload_folder.mkdir(parents=True, exist_ok=True)
                destination = upload_folder / stored_filename
                uploaded_file.save(destination)
                try:
                    db = get_db()
                    subject = canonical_subject(subject)
                    db.execute(
                        """INSERT INTO study_notes
                           (title, branch, year, semester, subject, stored_filename,
                            original_filename, uploaded_by)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (title, branch, year, semester, subject, stored_filename,
                         original_filename, session["user_id"]),
                    )
                    db.commit()
                except sqlite3.Error:
                    db.rollback()
                    destination.unlink(missing_ok=True)
                    app.logger.exception("Owner note upload could not be saved")
                    flash("The note could not be saved. Please try again.", "error")
                else:
                    flash("Your file is now available in the public notes library.", "success")
                    return redirect(notes_browse_url(branch, year, semester))
    return render_template(
        "upload.html",
        known_subjects=known_subjects(),
        note_branches=NOTE_BRANCHES,
        note_years=NOTE_YEARS,
        note_semesters=NOTE_SEMESTERS,
        year_semesters=YEAR_SEMESTERS,
    )


@app.cli.command("grant-library-owner")
@click.option("--email", required=True, help="Email of an existing account to make the notes owner.")
def grant_library_owner(email):
    """Grant the private notes-owner role from a trusted project shell."""
    email = email.strip().lower()
    configured_owner = app.config.get("OWNER_EMAIL", "").strip().lower()
    if not configured_owner:
        raise click.ClickException("Set OWNER_EMAIL in the environment before granting owner access.")
    if email != configured_owner:
        raise click.ClickException("Only the configured owner account may receive notes-admin access.")
    db = get_db()
    owner = db.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    if owner is None:
        raise click.ClickException("No existing account matches that email.")
    db.execute("UPDATE users SET is_owner = 0")
    db.execute("UPDATE users SET is_owner = 1 WHERE id = ?", (owner["id"],))
    db.commit()
    click.echo("Notes owner access granted to the existing account.")


BACKUP_FOLDER = Path(os.environ.get("BACKUP_FOLDER", str(Path(app.root_path) / "backups")))


def create_backup(label="backup"):
    """Zip a consistent copy of the database plus every uploaded file; return the zip path."""
    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%d-%H%M%S")
    zip_path = BACKUP_FOLDER / f"studenthub-{label}-{stamp}.zip"
    with tempfile.TemporaryDirectory() as work:
        db_copy = Path(work) / "studenthub.sqlite3"
        source = sqlite3.connect(app.config["DATABASE"])
        target = sqlite3.connect(db_copy)
        try:
            source.backup(target)  # safe even while the site is running
        finally:
            target.close()
            source.close()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(db_copy, "studenthub.sqlite3")
            upload_folder = Path(app.config["UPLOAD_FOLDER"])
            if upload_folder.is_dir():
                for file in sorted(upload_folder.iterdir()):
                    if file.is_file():
                        archive.write(file, f"uploads/{file.name}")
    return zip_path


@app.cli.command("backup")
def backup_command():
    """Save the database and all uploaded notes into one zip file."""
    zip_path = create_backup()
    with zipfile.ZipFile(zip_path) as archive:
        files = len([name for name in archive.namelist() if name.startswith("uploads/")])
    click.echo(f"Backup saved: {zip_path} (database + {files} uploaded file{'s' if files != 1 else ''})")


@app.cli.command("restore")
@click.argument("zip_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--yes", is_flag=True, help="Skip the confirmation question.")
def restore_command(zip_file, yes):
    """Replace the database and uploads with a backup (current data is backed up first)."""
    try:
        with zipfile.ZipFile(zip_file) as archive:
            names = archive.namelist()
            if "studenthub.sqlite3" not in names:
                raise click.ClickException("That zip is not a StudentHub backup (no database inside).")
            for name in names:
                if name != "studenthub.sqlite3" and not (
                    name.startswith("uploads/") and "/" not in name[len("uploads/"):]
                    and name[len("uploads/"):] not in {"", ".", ".."}
                ):
                    raise click.ClickException(f"Unexpected file in backup: {name}")
    except zipfile.BadZipFile:
        raise click.ClickException("That file is not a valid zip.")
    if not yes:
        click.confirm(
            "This replaces ALL current accounts, notes and uploads with the backup. Continue?",
            abort=True,
        )
    safety = create_backup("before-restore")
    click.echo(f"Current data saved first: {safety}")
    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    with tempfile.TemporaryDirectory() as work:
        with zipfile.ZipFile(zip_file) as archive:
            archive.extractall(work)
        restored = sqlite3.connect(Path(work) / "studenthub.sqlite3")
        live = sqlite3.connect(app.config["DATABASE"])
        try:
            restored.backup(live)
        finally:
            live.close()
            restored.close()
        if upload_folder.is_dir():
            shutil.rmtree(upload_folder)
        upload_folder.mkdir(parents=True, exist_ok=True)
        restored_uploads = Path(work) / "uploads"
        if restored_uploads.is_dir():
            for file in restored_uploads.iterdir():
                shutil.copy2(file, upload_folder / file.name)
    init_db()  # apply any newer schema changes to the restored database
    click.echo("Restore complete. Restart the website to be safe.")


@app.cli.group("library")
def library_cli():
    """Manage the shared notes library from a trusted owner shell."""


@library_cli.command("add")
@click.option("--owner-email", required=True, help="Existing owner account email for the upload record.")
@click.option("--title", required=True, help="Display title for the PDF.")
@click.option("--subject", required=True, help="Course subject.")
@click.option("--branch", required=True, type=click.Choice(NOTE_BRANCHES, case_sensitive=True))
@click.option("--year", required=True, type=click.Choice(NOTE_YEARS, case_sensitive=True))
@click.option("--semester", required=True, type=click.Choice(NOTE_SEMESTERS, case_sensitive=True))
@click.option("--file", "--pdf", "notes_file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
def add_library_note(owner_email, title, subject, branch, year, semester, notes_file):
    """Add one validated PDF or PPTX to the shared library (owner shell only)."""
    title = title.strip()
    subject = subject.strip()
    if not title or len(title) > 120 or not subject or len(subject) > 100:
        raise click.ClickException("Title (1-120 characters) and subject (1-100 characters) are required.")
    assignment_error = note_assignment_error(branch, year, semester)
    if assignment_error:
        raise click.ClickException(assignment_error)
    extension = notes_file.suffix.lower()
    if extension not in {".pdf", ".pptx"} or notes_file.stat().st_size > MAX_NOTE_FILE_SIZE:
        raise click.ClickException("Choose a PDF or PPTX file smaller than 20 MB.")
    with notes_file.open("rb") as source:
        signature = source.read(5)
        if extension == ".pdf" and signature != b"%PDF-":
            raise click.ClickException("The selected file is not a valid PDF.")
        if extension == ".pptx" and (
            not signature.startswith(b"PK") or not validate_pptx_stream(source)
        ):
            raise click.ClickException("The selected file is not a valid PowerPoint presentation.")

    with app.app_context():
        owner = get_db().execute(
            "SELECT id FROM users WHERE email = ? COLLATE NOCASE",
            (owner_email.strip(),),
        ).fetchone()
        if owner is None:
            raise click.ClickException("Create the owner account first; no account matches --owner-email.")

        original_filename = secure_filename(notes_file.name)
        if not original_filename:
            raise click.ClickException("The PDF filename is invalid.")
        stored_filename = f"{uuid.uuid4().hex}{extension}"
        upload_folder = Path(app.config["UPLOAD_FOLDER"])
        upload_folder.mkdir(parents=True, exist_ok=True)
        destination = upload_folder / stored_filename
        destination.write_bytes(notes_file.read_bytes())
        try:
            cursor = get_db().execute(
                """INSERT INTO study_notes
                   (title, branch, year, semester, subject, stored_filename,
                    original_filename, uploaded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, branch, year, semester, subject, stored_filename,
                 original_filename, owner["id"]),
            )
            get_db().commit()
        except sqlite3.Error:
            destination.unlink(missing_ok=True)
            raise
        click.echo(f"Added notes item {cursor.lastrowid}: {title}")


@library_cli.command("remove")
@click.argument("note_id", type=int)
def remove_library_note(note_id):
    """Remove one notes item and its stored PDF (owner shell only)."""
    with app.app_context():
        note = get_db().execute(
            "SELECT stored_filename, title FROM study_notes WHERE id = ?", (note_id,)
        ).fetchone()
        if note is None:
            raise click.ClickException("No notes item exists with that ID.")
        get_db().execute("DELETE FROM study_notes WHERE id = ?", (note_id,))
        get_db().commit()
        (Path(app.config["UPLOAD_FOLDER"]) / note["stored_filename"]).unlink(missing_ok=True)
        click.echo(f"Removed notes item {note_id}: {note['title']}")


@app.route("/notes/<int:note_id>/download")
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
        flash("That notes file is currently unavailable.", "error")
        return redirect(url_for("notes"))
    record_note_activity(note_id, "download")
    return send_file(
        file_path,
        as_attachment=True,
        download_name=note["original_filename"],
        mimetype=(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            if Path(note["original_filename"]).suffix.lower() == ".pptx"
            else "application/pdf"
        ),
    )


@app.route("/notes/<int:note_id>/preview")
def preview_note(note_id):
    note = get_db().execute(
        "SELECT id, title, subject, branch, year, semester, stored_filename, original_filename FROM study_notes WHERE id = ?",
        (note_id,),
    ).fetchone()
    if note is None:
        flash("That notes file could not be found.", "error")
        return redirect(url_for("notes"))

    file_path = Path(app.config["UPLOAD_FOLDER"]) / note["stored_filename"]
    if not file_path.is_file():
        flash("That notes file is currently unavailable.", "error")
        return redirect(url_for("notes"))
    record_note_activity(note_id, "preview")
    return_to = safe_local_path(request.args.get("return_to"))
    if return_to:
        back_url = return_to
    elif note_assignment_error(note["branch"], note["year"], note["semester"]) is None:
        back_url = notes_browse_url(note["branch"], note["year"], note["semester"])
    elif valid_branch_for_year(note["branch"], note["year"]):
        back_url = notes_browse_url(note["branch"], note["year"])
    else:
        back_url = url_for("notes")
    is_pptx = Path(note["original_filename"]).suffix.lower() == ".pptx"
    pptx_slides = extract_pptx_slide_text(file_path) if is_pptx else []
    return render_template(
        "note_preview.html", note=note, back_url=back_url,
        is_pptx=is_pptx, pptx_slides=pptx_slides,
    )


@app.route("/notes/<int:note_id>/file")
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
        flash("That notes file is currently unavailable.", "error")
        return redirect(url_for("notes"))
    is_pptx = Path(note["original_filename"]).suffix.lower() == ".pptx"
    response = send_file(
        file_path,
        mimetype=(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            if is_pptx else "application/pdf"
        ),
        as_attachment=is_pptx,
        download_name=note["original_filename"],
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    return response


ERROR_PAGES = {
    400: ("Something went wrong with that request", "Please go back, reload the page, and try again."),
    403: ("You don't have access to this page", "This page is only for the StudentHub admin account."),
    404: ("Page not found", "The page or note you're looking for doesn't exist or was removed."),
    405: ("That action isn't allowed here", "Please go back and use the buttons on the page."),
    500: ("Something went wrong on our side", "Please try again in a minute. If it keeps happening, report a problem."),
}


def render_error_page(code, message=None):
    heading, default_message = ERROR_PAGES[code]
    try:
        return render_template(
            "error.html", code=code, heading=heading, message=message or default_message
        ), code
    except Exception:
        # Never fail while showing an error (e.g. if the database is down).
        app.logger.exception("Error page could not be rendered")
        return f"{heading}. {default_message}", code


@app.errorhandler(400)
def bad_request(error):
    # abort(400, "...") passes a friendly message (e.g. an expired form session).
    description = getattr(error, "description", "")
    custom = description if description and not description.startswith("The browser") else None
    return render_error_page(400, custom)


@app.errorhandler(403)
def forbidden(_error):
    return render_error_page(403)


@app.errorhandler(404)
def not_found(_error):
    return render_error_page(404)


@app.errorhandler(405)
def method_not_allowed(_error):
    return render_error_page(405)


@app.errorhandler(500)
def server_error(_error):
    return render_error_page(500)


@app.errorhandler(413)
def upload_too_large(_error):
    flash("Files must be smaller than 20 MB.", "error")
    if request.endpoint == "upload_note":
        return redirect(url_for("upload_note"))
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

    conversation_search = request.args.get("q", "").strip()[:100]
    search_pattern = f"%{conversation_search}%"
    conversations = db.execute(
        """SELECT id, title, updated_at FROM mentor_conversations
           WHERE user_id = ?
             AND (? = '' OR lower(title) LIKE lower(?) OR EXISTS (
                 SELECT 1 FROM mentor_messages AS m
                 WHERE m.conversation_id = mentor_conversations.id
                   AND lower(m.content) LIKE lower(?)
             ))
           ORDER BY updated_at DESC, id DESC LIMIT ?""",
        (session["user_id"], conversation_search, search_pattern, search_pattern,
         MAX_CONVERSATION_HISTORY),
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
        conversation_search=conversation_search,
        current_conversation=current_conversation,
        messages=messages,
        ai_configured=bool(os.environ.get("OPENAI_API_KEY", "").strip()),
    )


init_db()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
