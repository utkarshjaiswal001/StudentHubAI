# StudentHub AI

StudentHub AI is a Flask application for student accounts, course notes, PDF sharing, saved career-mentor conversations, and issue reports.

## Run locally

From this project directory in PowerShell:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/). Check [http://127.0.0.1:5000/health](http://127.0.0.1:5000/health) for database connectivity. If setting up from scratch, create the virtual environment and install the packages listed in `requirements.txt` first.

## Database and uploaded files

- SQLite is connected automatically when the Flask app starts. The default database is `instance/studenthub.sqlite3`; set `DATABASE_PATH` in a local `.env` file to change it.
- Tables are created and compatible schema updates are applied automatically. Existing accounts, notes metadata, issue reports, activity, and Mentor conversations persist between restarts.
- The notes library is public and read-only to visitors: they can browse, preview, and download its PDFs and PowerPoint files without signing in. Only the account with the database owner role can open **Admin Access** and upload files; visitors and other signed-in accounts cannot upload or edit shared notes. Files are stored under `instance/uploads` by default, outside the public static directory.
- Set `OWNER_EMAIL` in the private `.env` to the one designated owner address. Once that account exists, grant its role from a trusted shell using `grant-library-owner`; the command refuses any address other than the configured owner. The owner can then use **Admin Access** or the Notes page to upload. For shell maintenance, add a PDF or PPTX with:

  ```powershell
  .\.venv\Scripts\python.exe -m flask --app app library add --owner-email "you@example.com" --title "Unit 1 Notes" --subject DBMS --branch "Computer Science Engineering" --year "2nd Year" --semester "Semester 3" --file "C:\path\to\notes.pdf"
  ```

  To grant the configured owner's role after the account exists, use:

  ```powershell
  .\.venv\Scripts\python.exe -m flask --app app grant-library-owner --email "you@example.com"
  ```

  Sign in as the configured owner account to use the Admin Access dashboard. The dashboard shows note upload, AI key/model configuration status, and read-only access to recent saved Mentor conversations. It does not test whether an API key is valid or contact the provider.

  Remove an item and its stored file with `.\.venv\Scripts\python.exe -m flask --app app library remove 12`, replacing `12` with the note ID. These commands require shell access to the project/host; they are not available to website visitors.
- Account registration, each student's own Mentor messages, activity, and issue reports still create their own application records. Visitors cannot edit another account's records or the shared notes library.
- Keep `.env`, the `instance` directory, uploads, and database files private and out of Git. Back up the database and uploads together if you need to preserve the complete notes library.
- The separate database supplied with the Claude reference project uses a different notes schema. Do not point this app at that file without a deliberate data migration.

## Optional AI Mentor replies

Mentor conversations are stored locally even when AI is not configured. The OpenAI SDK is included in `requirements.txt`; real replies still require a private `OPENAI_API_KEY`. Copy `.env.example` to `.env`, add the key, choose an `OPENAI_MODEL` available to your account, and restart Flask. Replies are requested only when the student checks the per-message sharing consent box. Keep `.env` private.

## Main features

- Account registration, sign-in, sign-out, and protected student pages.
- Student account settings: edit profile, change password, delete account, and a **My notes** shortcut to the student's own branch and year.
- Public course notes: Year → Branch → Semester → Subject (1st Year skips the semester step; each branch page also shows the subjects common to every branch). Subject search and "New" badges for recent uploads.
- Official AKTU subject list for all six branches (`data/aktu_subjects.json`, from the syllabus PDFs on aktu.ac.in): every syllabus subject appears with its code, even before notes are uploaded.
- Owner Admin page: upload, edit, and delete notes; read and close student issue reports; reset a student's password (temporary password, must be changed at next sign-in).
- Uploads are checked for a matching year/semester. The owner picks the subject from the AKTU list for that branch and semester, or types one under "Other" (e.g. open electives).
- Themes: 13 colour sets (Aurora, Ocean, Sunset, Forest, Galaxy, Slate, Racing, Mocha Gold, Neon, Silk, Powder Sky, Obsidian, Emerald), each in dark and light, plus soft light-mode backgrounds (Cream, Sand, Sage, Mist, Lavender, Dim) and two layouts: Classic and Glass (floating rounded top bar, frosted cards, pill buttons, icon rail). Pick from the 🎨 button in the top bar or the `/themes` gallery with live previews; the choice is remembered per browser. Default: Aurora dark.
- Quick Help gives study pointers for core subjects of every branch and can say where any AKTU subject sits in the syllabus.
- Notes recommendations and recent activity in the Account Centre.
- Quick Help and searchable saved Mentor conversation history, with up to 80 conversations shown per student.
- Student issue reports and clearly marked Coming Soon roadmap features.

## Security features

- Passwords stored as salted hashes (Werkzeug); never stored in plain text.
- CSRF token on every form; logout is POST-only; safe same-site redirects only.
- Login locks for 15 minutes after 5 wrong passwords for the same email.
- Logins expire after 7 days; security headers (X-Frame-Options, nosniff, Referrer-Policy) on every page.
- Owner-only upload/edit/delete, checked against the database on every request.
- Uploaded files: PDF/PPTX only, 20 MB limit, file-content checks, random stored names outside the public folder.
- Automated tests: `.\.venv\Scripts\python.exe -m unittest discover -s tests` (63 tests).
