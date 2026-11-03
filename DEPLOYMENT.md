# Free Flask deployment for StudentHub AI

## Recommended for a small demo: PythonAnywhere Beginner

The app can run on PythonAnywhere's free Flask-capable web app. Its home filesystem persists, so the SQLite database and uploaded PDFs can remain under your account's home directory. The free tier is deliberately limited: it currently provides one web app, one worker, 512 MiB of storage, restricted outbound internet access, and a one-month expiry for the web app. Plan to renew/keep the free app active and keep backups. [Free account limits](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/) · [Pricing](https://www.pythonanywhere.com/pricing/)

## Set it up

1. Push the StudentHub project files to the GitHub repository. Keep `.env`, the local `instance` folder, SQLite files, and uploaded PDFs out of GitHub.
2. Create a PythonAnywhere Beginner account and open a Bash console. Clone the repository and install its requirements in a Python 3.13 virtual environment:

   ```bash
   cd ~
   git clone https://github.com/utkarshjaiswal001/StudentHubAI.git
   cd StudentHubAI
   mkvirtualenv studenthub --python=python3.13
   pip install -r requirements.txt
   mkdir -p ~/studenthub-data/uploads
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. In the PythonAnywhere Web tab, add a **Manual configuration** web app for Python 3.13. Set the source and working directory to `/home/YOUR_USERNAME/StudentHubAI` and select the `studenthub` virtualenv. Replace `YOUR_USERNAME` below with your PythonAnywhere username.
4. Edit the WSGI file linked from the Web tab. Keep the generated header comments, remove the example application section, and add this Flask configuration before importing the app. Paste the random value printed in step 2 in place of `GENERATED_RANDOM_VALUE`:

   ```python
   import os
   import sys

   project_home = "/home/YOUR_USERNAME/StudentHubAI"
   sys.path.insert(0, project_home)

   os.environ["SECRET_KEY"] = "GENERATED_RANDOM_VALUE"
   os.environ["DATABASE_PATH"] = "/home/YOUR_USERNAME/studenthub-data/studenthub.sqlite3"
   os.environ["UPLOAD_FOLDER"] = "/home/YOUR_USERNAME/studenthub-data/uploads"
   os.environ["SESSION_COOKIE_SECURE"] = "true"
   os.environ["OWNER_EMAIL"] = "YOUR_OWNER_ACCOUNT_EMAIL"

   from app import app as application
   ```

   `OWNER_EMAIL` must match an existing account's email before you run `grant-library-owner`; the command now refuses to grant the owner role when this variable is missing. Register that account through the website first.

5. Click **Reload** on the Web tab, then visit `https://YOUR_USERNAME.pythonanywhere.com/`. Open `/health` to confirm Flask can reach its database, then try registration, login/logout, and the Notes pages.

## Keeping code and data in sync

- To deploy a code update, open a Bash console and run `cd ~/StudentHubAI && git pull`, then click **Reload** in the Web tab.
- Accounts, mentor conversations, note metadata, and PDFs are stored under `~/studenthub-data`. They persist independently of Git pulls.
- Your local `instance` data does not automatically copy to PythonAnywhere. Keep the site initially empty, or plan an intentional private migration of both the local SQLite database and PDFs.
- Back up `~/studenthub-data` before important changes. The free tier's 512 MiB includes your code, virtual environment, database, and PDFs.

## Important limits for a live demo

PythonAnywhere's free app can expire after one month, has one worker, and restricts outbound internet. That is enough for a small class demo with the current local notes and SQLite features, but it is not a reliability guarantee for a public production service. AI provider calls are deferred and may be blocked by the free tier's outbound-network rules. Check its current terms and limits before relying on the URL for a scheduled presentation.

For comparison, Render's free web service sleeps when idle and discards local SQLite data and uploads on restart/redeploy; its free Postgres also expires after 30 days. It is therefore not the no-cost, persistent option for this app. [Render free-tier limits](https://render.com/docs/free)
