# StudentHub AI — single-prompt project recreation brief

Use this file as one complete prompt in an AI coding tool. It describes the current StudentHub AI product, its implemented behavior, the page structure, the data fields, and the visual direction. To recreate the *same* site, give the coding tool this prompt together with the existing project files and visual assets whenever possible; a text prompt alone cannot recover private PDFs, database contents, exact unseen image assets, or unrecorded source history.

## One-line instruction to give a coding agent

> Read `STUDENTHUB_RECREATION_PROMPT.md` completely, inspect the supplied repository and assets, then implement StudentHub AI to match the specification below. Preserve working behavior and existing user data, run the app locally, verify every listed flow, and report the local URL and any features that require external credentials.

---

## Copy/paste build prompt

You are a senior full-stack product engineer. Build **StudentHub AI**, a complete, responsive student study and career guidance website. This is a working web application, not a static mockup. Implement the user interface, routes, forms, persistent data, authentication, file handling, and graceful optional AI integration described below. If an existing repository is provided, inspect it first, preserve its working features and data, and make targeted changes instead of replacing it blindly. Do not claim a feature works unless you implement and verify it.

### 1. Product goal and audience

Create one welcoming platform for university/engineering students to discover shared course notes, get short study help, save longer career mentor conversations, track recently opened notes, and report issues. The interface should make available features usable and clearly label unfinished features **Coming Soon**. Do not create fake AI responses, pretend files exist, or imply that a roadmap card is already functional.

### 2. Technology and project setup

- Use Python 3 and Flask with server-rendered Jinja HTML, SQLite persistence, and plain CSS/JavaScript. Keep the app straightforward to run locally with one command (`python app.py`, or the repository's documented equivalent) and provide a health endpoint.
- Keep dependencies small: Flask and python-dotenv are required. The OpenAI SDK is optional and only needed when the owner configures an API key.
- Suggested structure: `app.py`; `templates/` for pages and shared partials; `static/css/` and `static/js/` for styles and behavior; `instance/` or a configured data path for SQLite; a private uploads directory for PDFs; `.env.example`, `requirements.txt`, and concise setup documentation.
- Configure secret key, database path, upload path, secure-cookie setting, and AI model through environment variables. Never commit `.env`, credentials, local databases, uploaded documents, or virtual environments. Include a safe `.gitignore`.
- Provide `GET /health` that checks app/database readiness and returns a clear healthy or unavailable response.

### 3. Brand, layout, and visual system

- Product name and wordmark: **StudentHub AI**. Audience: students. Voice: clear, encouraging, practical, not corporate or childish.
- Use the established classic StudentHub palette as the default: vivid violet/purple primary (approximately `#6d5dfc`, darker `#5545d8`), cyan secondary (`#00b8d9`), pink accent (`#ff5ca8`), deep navy text (`#1f2340`), muted slate text, very pale lavender page backgrounds, and white/light surfaces with soft borders and shadows. The optional midnight/cobalt/lime colors (`#030407`, `#1558C9`, `#D4FF24`) are an alternate experiment, not the default. Keep the classic palette unless explicitly asked to switch.
- Landing hero: large purple-to-blue gradient field, centered student badge, oversized StudentHub AI heading, bold two-line benefit headline, short description, and two calls to action. Add subtle decorative circles. Continue into a rounded light showcase panel headed “Everything you need” / “Your student journey, all in one place.”
- Avoid a second, competing post-login homepage. Registration/login returns the user to the same home page with the same main structure and personalized navigation.
- Use consistent shared navigation, spacing, rounded cards, clear section headings, gentle shadows, visible hover/focus states, readable contrast, and responsive layouts. On narrow screens, collapse navigation behind an accessible menu button; stack columns/cards and keep forms usable without horizontal scrolling.
- Do not add intrusive greeting banners. After successful login/registration, show a small bottom-right greeting toast with a close button and automatic dismissal after 10 seconds; either dismissal method removes it. The signed-in user's name belongs in the profile menu, not as a large hero replacement.
- On the home page, the signed-in user's name opens a compact dropdown with **Account Centre**, **Report an issue**, and **Logout**. Signed-out navigation shows **Login** and **Register**. Use the same signed-in profile control on all authenticated pages. Do not show a stale signed-out menu after browser back/refresh; use appropriate no-store headers for session-specific pages.

### 4. Pages, sections, and navigation

Implement these URLs or equivalent named routes with the same behavior:

1. **Home `/`** — shared public/signed-in landing page. Navigation anchors: Home, Services, How It Works, AI Mentor, Suggestions. Hero CTAs scroll to services and mentor. The services showcase has seven cards:
   - College Notes — available, opens the public read-only Notes library; browsing, previewing, and downloading do not require sign-in.
   - AI Career Mentor — available, opens saved Mentor (requires sign-in).
   - Placement Guidance — available through Mentor; make that destination explicit.
   - AI Resume Analyzer — Coming Soon.
   - Interview Preparation — Coming Soon.
   - Internship Opportunities — Coming Soon.
   - Coding Practice — Coming Soon.
   Provide short, interesting descriptions; avoid duplicating the same feature in multiple sections. Clicking an unavailable feature should clearly say it is coming soon; do not route it to an unrelated working feature.
2. **How It Works** section — concise five-step student journey: Register → Explore → Study → Ask AI → Prepare. Give each step one helpful sentence.
3. **AI Mentor / Quick Help** section on home — introduction and suggested prompt chips (career path, data science roadmap, placement preparation, Python interview questions), a short-question form, answer area, and “continue in full Mentor” behavior. Quick help may use deterministic local answers for supported core-subject questions and search actual notes for note requests. It must not claim to use AI. Keep at most three short exchanges in the temporary quick-help session history. Longer, step-by-step, roadmap, comparison, or continued chats should be transferred into the full Mentor after sign-in, preserving the typed question/context.
4. **Suggestions** section on home — issue-report form with category and description. Categories: broken link, login, notes, mentor, other. Save reports to the database for later admin review; public/admin viewing is outside scope unless requested. Show success/error feedback.
5. **Login `/login`** — email and password; clear validation and feedback; link to registration. Successful login returns to `/` and updates navigation to the person's name. Honor a safe, local intended destination where applicable, particularly a pending quick-help continuation, without allowing external redirects.
6. **Registration `/register`** — required fields: full name, email, college name, branch (Computer Science, Information Technology, Electronics & Communication, Electrical Engineering, Mechanical Engineering, Civil Engineering, Other), year (1st–4th Year), password, confirm password. Validate required values, email format, confirmation, duplicate email, and sensible lengths. Hash passwords; never store plaintext. After registration, return to the same home page and personalize the menu.
7. **Dashboard `/dashboard`** — concise signed-in overview with links/cards to College Notes and AI Career Mentor. Clearly label future resume analysis as Coming Soon rather than implying it works.
8. **Notes catalog `/notes`** — public first step of an AKTU-style, owner-curated, read-only notes library: choose academic year (1st, 2nd, 3rd, 4th); place a “Notes to explore” recommendations box alongside it. Prefer subjects actually in the library; otherwise use a small curated list of relevant subjects. Do not show visitors upload or edit controls.
9. **Notes branches `/notes/branches?year=…`** — public page listing valid branches for selected year, with counts of subjects/PDFs when available. Common first-year branch may appear for first year only. Provide a clear back-to-years link.
10. **Notes subjects `/notes/subjects?branch=…&year=…`** — public page grouping PDFs by subject; expandable subject groups show note title, semester, filename, Preview and Download actions. Show a useful empty state when no PDFs exist. Preserve browsing context when returning from preview.
11. **Notes search `/notes`** — searchable public filters: year, branch, semester (Semester 1–8), subject text. Results show metadata and preview/download. Keep a persistent right-side suggestions box recommending other subjects, preferring actual library data and excluding the current result subject where possible.
12. **Owner-only notes maintenance** — only the single designated owner account can open `/admin` and `/notes/upload`; show Admin Access in that owner's profile menu and Notes page. Reject non-owner accounts with HTTP 403. Accept validated PDF and PPTX uploads up to 20 MB, store outside public static paths, and delete a stored file if metadata insertion fails. PPTX preview extracts readable slide text on-site and retains a download link for original formatting. Keep CLI add/remove commands available for trusted shell maintenance. Visitors must never receive a route that modifies shared notes or stored files.
13. **Notes preview `/notes/<id>/preview`** — public same-site page; display title, subject, branch, year, semester; use an inline viewer for PDFs and a text preview for PPTX, with download action and safe local back link. Record preview/download activity only for signed-in students. Never expose arbitrary filesystem paths. Serve files from the same site's `/notes/<id>/file` route.
14. **Full AI Career Mentor `/chatbot`** — signed-in conversation workspace with left history panel and search, “New chat”, selected conversation, message list, question compose box, and saved history. Limit visible history to 80 conversations per user and support search over conversation titles and message content. Each message max 2,000 characters. Verify conversation ownership on every read/write. Keep conversations in SQLite. AI replies are optional: if an OpenAI API key is configured, show a consent checkbox and send the current message plus at most 11 recent messages only after the user opts in. If unavailable or not consented, save the user's message locally and state accurately that no AI reply was generated. Never expose API keys in HTML or logs. Handle provider errors without losing the saved user message.
15. **Account Centre `/account`** — signed-in profile (name, email, college, branch, year, join date); counts for distinct notes visited and total saved Mentor conversations; latest six note activity records; up to 80 saved conversations with latest message preview and open links. Explain AI sharing/configuration accurately.
16. **Owner Admin Access `/admin`** — protect using a database owner role granted only from a trusted shell to the one configured owner account. Show upload access, AI API-key/model configuration status without claiming to verify provider availability, student/account/notes/conversation counts, and a read-only list of recent Mentor threads. Allow the owner to open a thread and review its saved messages; disclose this review access in the Mentor UI. Do not show email addresses or add editing/deletion controls for conversations.
17. **Logout `/logout`** — clear authenticated session and return to home with feedback. Protect account, dashboard, Mentor, and Admin routes; notes browsing and preview remain public/read-only. Unauthenticated attempts go to sign-in, then return to the safe requested feature after successful authentication.

### 5. Data model

Use parameterized SQL and schema setup/migrations. A practical schema includes:

- `users`: integer id; name; unique normalized email; college; branch; year; password hash; created timestamp.
- `study_notes`: id; title; branch; year; semester; subject; generated stored filename; sanitized original filename; uploader user id; created timestamp.
- `note_activity`: id; user id; note id; action (`preview` or `download`); timestamp. Use it for distinct notes visited and each note's latest activity.
- `mentor_conversations`: id; user id; title; created/updated timestamps.
- `mentor_messages`: id; conversation id; role (`user` or `assistant`); content; timestamp.
- `suggestions`: id; nullable user id; category; message; created timestamp.

Use foreign keys/indexes where appropriate. Preserve existing records when adding schema fields. Store uploaded file bytes on disk in a private upload directory and only their metadata in SQLite. The project owner may seed a small number of sample note records only when actual sample PDFs are included; otherwise show empty states instead of broken sample links.

### 6. Authentication, state, and safety behavior

- Use Flask server-side signed sessions with a strong configurable secret; secure cookie flags in production; HTTP-only and SameSite=Lax.
- Use Werkzeug password hashing/checking. Normalize email before lookup and enforce uniqueness in the database.
- Clear stale flash/toast state as it is consumed. Login/register changes the navbar immediately and survives refresh/back navigation without rendering an old anonymous navbar.
- Implement an authentication decorator for account, dashboard, and Mentor routes. Keep Notes catalog, search, branches, subjects, preview, and file delivery public/read-only. Track note activity only for signed-in students; validate ownership for Mentor conversations. Signed-in students can create their own chats, activity, and issue reports, but neither signed-in nor anonymous visitors can modify the shared Notes catalog or files. Only the single designated owner can use the protected Admin Access and upload pages or trusted `flask library` terminal commands. Allow validated PDF and PPTX uploads, and show an on-site text preview for PPTX. Validate request inputs server-side, not only in browser markup.
- Validate intended redirects as same-origin local paths. Escape user content via template autoescaping. Limit upload request size. Avoid exposing stack traces, secrets, or local paths to users.
- Do not send user questions to an external provider without an explicit per-message opt-in. Clearly explain when the optional external request happens.

### 7. Accessibility and interaction details

- Semantic landmarks/headings, labels associated with every input, useful alt/accessible names, keyboard-accessible dropdown and mobile navigation, visible focus, `aria-live`/status messaging for results and errors, and reduced-motion support.
- Cards that navigate must be real links. Non-navigating Coming Soon cards must not masquerade as buttons. Avoid nested interactive elements.
- All controls should work with keyboard and touch. Toast close button has an accessible label. Confirm no layout overflow at phone, tablet, and desktop widths.

### 8. Completion requirements

Before reporting completion, inspect the supplied code/assets and compare implementation to this specification. Start the site with the documented local command and provide its exact localhost URL. Verify, at minimum: health endpoint; anonymous home; registration and duplicate handling; login/logout and navbar after refresh/back; protected-route redirect/return; anonymous Notes filters, recommendations, branch/subject browsing, PDF and PPTX preview/download; non-owner denial; owner upload validation and Admin Access conversation review; signed-in-only activity tracking; owner-only Mentor history, search, 80-item cap, optional consent behavior, and profile-aware replies; suggestion submission; responsive navigation and layout. Use temporary test data/files and remove them afterward. Report any setup requiring a private API key, and do not claim real AI replies work until verified with configured credentials.

Do not stop after generating a plan or mockup. Implement the whole requested app, resolve errors found during verification, document the one-command local start, and summarize changed files and verified flows. If a supplied source repository already contains an equivalent feature, preserve it and adapt the spec to the actual source instead of creating a conflicting second implementation.

---

## Use it

In a coding assistant with this repository open, paste the one-line instruction above. If the assistant cannot read project files by reference, paste the **Copy/paste build prompt** section itself as the single prompt. For best fidelity, include the repository and its images/fonts/sample PDFs; the prompt captures functionality and design intent, but private data and binary assets must be supplied separately.
