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
- The notes library is public and read-only to visitors: they can browse, preview, and download its PDFs without signing in. Only the account configured by `OWNER_EMAIL` can open the website's **Upload study notes** page; visitors and other signed-in accounts cannot upload or edit shared notes. PDFs are stored under `instance/uploads` by default, outside the public static directory.
- `OWNER_EMAIL` in the private `.env` can bootstrap the initial notes-owner role for an existing account. That account can upload from the profile menu or Notes page. For trusted shell maintenance, add a PDF with:

  ```powershell
  .\.venv\Scripts\python.exe -m flask --app app library add --owner-email "you@example.com" --title "Unit 1 Notes" --subject DBMS --branch "Computer Science Engineering" --year "2nd Year" --semester "Semester 3" --pdf "C:\path\to\notes.pdf"
  ```

  To assign the owner role to a different existing account from a trusted shell, use:

  ```powershell
  .\.venv\Scripts\python.exe -m flask --app app grant-library-owner --email "you@example.com"
  ```

  Then sign in as that account. This grants the role to one account only.

  Remove an item and its stored PDF with `.\.venv\Scripts\python.exe -m flask --app app library remove 12`, replacing `12` with the note ID. These commands require shell access to the project/host; they are not available to website visitors.
- Account registration, each student's own Mentor messages, activity, and issue reports still create their own application records. Visitors cannot edit another account's records or the shared notes library.
- Keep `.env`, the `instance` directory, uploads, and database files private and out of Git. Back up the database and uploads together if you need to preserve the complete notes library.
- The separate database supplied with the Claude reference project uses a different notes schema. Do not point this app at that file without a deliberate data migration.

## Optional AI Mentor replies

Mentor conversations are stored locally even when AI is not configured. The OpenAI SDK is included in `requirements.txt`; real replies still require a private `OPENAI_API_KEY`. Copy `.env.example` to `.env`, add the key, choose an `OPENAI_MODEL` available to your account, and restart Flask. Replies are requested only when the student checks the per-message sharing consent box. Keep `.env` private.

## Main features

- Account registration, sign-in, sign-out, and protected student pages.
- Public course notes by year, branch, semester, and subject, with owner-managed PDFs, previews, and downloads.
- Notes recommendations and recent activity in the Account Centre.
- Quick Help and searchable saved Mentor conversation history, with up to 80 conversations shown per student.
- Student issue reports and clearly marked Coming Soon roadmap features.
