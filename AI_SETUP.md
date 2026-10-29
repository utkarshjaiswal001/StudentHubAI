# Enable AI Career Mentor replies

The Mentor stores conversations in the local StudentHub database. AI replies are optional and require an OpenAI API key and an internet connection.

1. Open PowerShell in the project folder and activate the environment: `.venv\Scripts\Activate.ps1`.
2. Install the app dependencies with `pip install -r requirements.txt`. When you later choose an AI provider, install that provider's SDK separately; the OpenAI version of this integration needs `pip install openai`.
3. Copy `.env.example` to `.env`. Set a private, random `SECRET_KEY` there to keep login sessions stable across restarts. For example, generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. Keep `.env` private; it is excluded by `.gitignore`.
4. Set `OPENAI_API_KEY` in `.env` to enable AI replies. Set `OPENAI_MODEL` to a model available to your API account if needed, then restart Flask.
5. In AI Career Mentor, select the sharing checkbox before submitting when you want an AI reply. Without selecting it, the message is saved locally and not sent to OpenAI.

When the checkbox is selected, the new message and up to 11 recent messages in that conversation are sent to OpenAI to create the reply. API use may incur charges. The generated reply is then saved in the local conversation history. Home page Quick Help answers remain local and do not call the AI API.

The API key is read from the server environment and is never rendered in the page. If no key is configured, Mentor messages can still be saved and browsed locally.
