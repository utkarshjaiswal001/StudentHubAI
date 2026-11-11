# StudentHub AI — Demo Script and Viva Prep

## Before the demo (5 min)

- Double-click `Run StudentHub.bat` → browser opens http://127.0.0.1:5000
- Have two browser windows: one **normal** (owner account), one **private/incognito** (student).
- Upload 2–3 real notes in advance (e.g. a 1st-year Common subject and a subject from a later year).
- Keep a test student account ready, or register one live.

## 2-minute demo script

| Time | Do this | Say this |
|---|---|---|
| 0:00 | Home page | "StudentHub AI puts AKTU course notes and basic study help in one place." |
| 0:15 | Notes → 3rd Year → any branch → Semester 5 → open a subject | "Students browse Year → Branch → Semester → Subject. Every official AKTU subject is listed with its code, for all six branches. 1st year skips the semester step." |
| 0:35 | Preview a PDF, then Download | "Files open right here; downloads keep the original file." |
| 0:45 | Student window: Account → **My notes** | "My notes jumps straight to the student's own branch and year." |
| 0:55 | Owner window: Admin → Manage notes → Edit a note | "Only the owner can upload, edit, or delete notes. Uploads are checked: the semester must match the year." |
| 1:15 | Admin → Issue reports → Mark closed | "Students report problems; the admin tracks and closes them." |
| 1:25 | Student window: log out, enter a wrong password 5 times | "After 5 wrong passwords the account locks for 15 minutes — this blocks password guessing." |
| 1:40 | Show terminal: run the tests | "67 automated tests check security rules, the notes flow, admin tools, and accounts." |
| 1:55 | — | "Future scope: free AI Mentor replies, email password reset, and searching inside PDFs." |

Test command: `.\.venv\Scripts\python.exe -m unittest discover -s tests`

## Likely viva questions

**Q: What technology did you use and why?**
Python + Flask for the web server (small, easy to learn), SQLite for the database (single file, no server to install), Jinja HTML templates, CSS and a little JavaScript. All free and enough for a college-scale app.

**Q: How are passwords stored?**
Never as plain text. Werkzeug's `generate_password_hash` stores a salted hash; at login `check_password_hash` compares them.

**Q: What is CSRF and how do you prevent it?**
Cross-Site Request Forgery: another website tricking a logged-in user's browser into submitting a form. Every form carries a secret random token stored in the session; the server rejects any POST without the matching token.

**Q: How do you stop password guessing?**
Failed logins are counted per email in a `login_attempts` table. After 5 wrong passwords, login is blocked for 15 minutes. A correct login resets the counter.

**Q: How do you make sure only you can upload notes?**
The `users` table has an `is_owner` flag. Upload/edit/delete routes use an `owner_required` check that reads the flag from the database on every request. Only the email set in `OWNER_EMAIL` can be given that role, and only from the server's command line.

**Q: How do you check uploaded files are safe?**
Only `.pdf` and `.pptx`, max 20 MB. PDFs must start with `%PDF-`; PPTX files are opened as ZIP and checked for real PowerPoint parts. Files get random names and are stored outside the public folder, so nobody can guess or run them.

**Q: How is the database designed?**
Tables: `users`, `study_notes`, `note_activity`, `mentor_conversations`, `mentor_messages`, `suggestions`, `login_attempts`. Foreign keys link records to users; deleting an account also deletes that student's chats and activity (ON DELETE CASCADE).

**Q: Why does 1st year skip the semester step?**
In the new AKTU 1st-year scheme, sections take Physics and Chemistry in different semesters, so a fixed Sem 1 / Sem 2 split would confuse students. They go straight to the subject list: their branch's stream subjects plus the subjects common to every branch. Each file still shows its semester label.

**Q: Where do the subject names come from?**
From the official AKTU syllabus PDFs on aktu.ac.in, for all six branches: 1st year (2026-27 scheme), 2nd year (2023-24), 3rd year (2024-25) and 4th year (2025-26). They are stored in `data/aktu_subjects.json` with their subject codes. Open electives and labs are not listed; the owner can type those under "Other".

**Q: What happens if a student forgets their password?**
They report a login issue; the admin resets it to a temporary password from the Admin page. The student must choose a new password right after signing in. Email reset is future scope because free hosting restricts sending email.

**Q: What is SQL injection and is your app safe?**
Inserting SQL code through form fields. All queries use `?` placeholders, so user input is always treated as data, never as SQL.

**Q: How did you test it?**
67 automated tests using Python's `unittest` and Flask's test client, run against a temporary database. They cover login, registration, CSRF, owner-only access, the notes flow, upload rules, lockout, admin tools, and account settings.

**Q: How will you host it for free?**
PythonAnywhere's free plan. The database and uploads live in the account's storage. The AI key is left empty so there are no costs.

**Q: What does the AI Mentor do?**
Students' questions are saved as conversations. If an AI API key is configured and the student ticks the consent box, the server asks the AI for a reply. Without a key it still saves questions. Free-provider support is future scope.

**Q: How does the theme switcher work?**
Each colour set is a group of CSS variables (main colour, second colour, background, card colour). The page's `<html>` tag carries `data-theme` (dark/light) and `data-palette` (e.g. ocean), and the CSS picks the matching variables. The choice is saved in the browser's localStorage and applied by a tiny script in the page head before anything is drawn, so there is no flash. No server or database work is needed.

**Q: What are the limitations?**
SQLite suits small traffic; free hosting expires monthly and restricts outbound internet; no email reset; AI replies need an API key.
