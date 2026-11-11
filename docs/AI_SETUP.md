# Enable the StudentHub AI Career Mentor

The full Mentor already saves each student's conversations in the local SQLite database. Its OpenAI Responses API connection is optional and deliberately sends nothing to an AI provider unless the student selects the sharing checkbox on that message.

## Local setup

1. Install the project dependencies in the virtual environment: `pip install -r requirements.txt`. This includes the OpenAI Python SDK.
2. Copy `.env.example` to `.env` if you have not already done so. Set a private `OPENAI_API_KEY` in `.env`; never paste it into chat, HTML, JavaScript, source control, or a public issue.
3. Set `OPENAI_MODEL` to a model enabled for your API project. The current default is `gpt-6.1-sol`, selected as a balance of capability and cost. Model availability and pricing can change; review the [official model catalog](https://developers.openai.com/api/docs/models) and [pricing](https://developers.openai.com/api/docs/pricing).
4. Restart the Flask server. The Mentor page should indicate that AI replies are available.
5. Send a test message with the consent box unchecked: it should be saved locally without generating a reply. Then send a second test message with consent checked: its reply should appear in that saved conversation.

The API is billed separately from a ChatGPT subscription. Set a usage budget/alerts for the API project. Only after per-message consent, the server sends the current message, up to 11 recent messages, and the student's saved branch/year. It does not send the student's email or college. The request uses `store=False`; messages and replies are still saved in StudentHub's own database. OpenAI's API data controls currently describe abuse-monitoring logs retained for up to 30 days by default, subject to legal/safety exceptions; do not promise users immediate upstream deletion or zero retention. See the official [API data controls](https://developers.openai.com/api/docs/guides/your-data).

## Study-help behavior and next improvement

The full Mentor is designed for natural back-and-forth conversation. When a student asks about careers, its instructions use their saved branch/year and the conversation's stated interests to outline both core-field and adjacent paths. For an ECE student, for example, it can compare embedded/firmware, VLSI/FPGA, telecom/IoT, and software/IT, then give relevant skills, a starter project, and a next step. It shouldn't push everyone into the same path; it should answer normally, offer an initial set of choices, then ask one focused question if the student's interests are still unclear. Study answers should use clear explanations, worked examples, revision plans, and practice questions. Home-page Quick Help is still a small deterministic helper for a few common subjects and note searches; it is not an AI response. For answers grounded in actual notes PDFs, add document text extraction plus retrieval and cite the note title/page; the current Mentor does not read PDFs.

The app saves the student's message before requesting the provider. If the provider is unavailable or returns an error, the saved message remains in the conversation and the user sees an error message.
