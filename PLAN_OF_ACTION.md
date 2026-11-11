# StudentHub AI — Plan of Action

Last updated: 2026-11-05 · Budget: free only · AI Mentor work: out of scope for now

## Status (2026-11-05)

| Phase | Status |
|---|---|
| 0 Save work | ✅ Done |
| 1 Security | ✅ Done — waiting for your browser check |
| 2 Admin tools | ✅ Done — waiting for your browser check |
| 3 Student account | ✅ Done — waiting for your browser check |
| 4 Notes extras | ✅ 4.1–4.3 done · 4.4 "Coming Soon" cards left for you to decide |
| 5 Go online | ✅ Claude's part done (git cleaned, checklist in DEPLOYMENT.md) · ⏳ your part: push, PythonAnywhere |
| 7 AKTU subjects | ✅ Official subject list (all branches, all years) on Notes pages, upload picker, Quick Help |
| 6 Submission | ✅ Report + slides updated, DEMO_AND_VIVA.md written · Rest handled by you separately |

Tests: 63, all passing.

**Who does what**
- **Claude** makes every change to the project files, writes tests, runs them, and commits.
- **You** only do what needs your own accounts or eyes: checking pages in the browser, logging into GitHub/PythonAnywhere, and giving the go-ahead at each checkpoint.

**How every phase runs**
1. Claude makes the changes.
2. Claude runs all tests (must pass) and tells you what changed in plain words.
3. ✋ **Checkpoint:** you open the site (`Run StudentHub.bat`) and try it.
4. You say OK → Claude commits to git. Not OK → Claude fixes it first.

---

## Phase 0 — Save current work
| Step | Who | Task |
|---|---|---|
| 0.1 | Claude | Commit the finished notes-flow changes (semester step, 1st-year flow, upload checks, tests) |

---

## Phase 1 — Security fixes (update)
| Step | Who | Task |
|---|---|---|
| 1.1 | Claude | Lock login for 15 min after 5 wrong passwords for the same email |
| 1.2 | Claude | Stop fake "AI answers" being saved via Quick Help → Continue (use server-saved history only) |
| 1.3 | Claude | Add browser security headers to every page (blocks hidden-frame tricks) |
| 1.4 | Claude | Make logins expire after 7 days |
| 1.5 | Claude | Tests for 1.1–1.4 |
| ✋ | You | Try: 5 wrong passwords → locked message; normal login still works |

---

## Phase 2 — Admin tools (add)
| Step | Who | Task |
|---|---|---|
| 2.1 | Claude | Admin page: list of all uploaded notes with search |
| 2.2 | Claude | **Edit note** (title, subject, branch, year, semester) |
| 2.3 | Claude | **Delete note** with a confirm step (removes file + record) |
| 2.4 | Claude | After upload → go to the page where that note appears |
| 2.5 | Claude | "File too large" → back to the upload form, not Notes home |
| 2.6 | Claude | Admin page: read and close student issue reports |
| 2.7 | Claude | Admin can reset a student's password to a temporary one |
| 2.8 | Claude | Tests for all of the above (incl. non-owners blocked) |
| ✋ | You | Upload a test PDF, edit it, delete it; open issue reports |

---

## Phase 3 — Student account (add + update)
| Step | Who | Task |
|---|---|---|
| 3.1 | Claude | **Change password** page |
| 3.2 | Claude | **Edit profile** (name, college, branch, year) |
| 3.3 | Claude | **Delete my account** (password confirm; removes their chats and activity) |
| 3.4 | Claude | Registration branches match Notes branches; old accounts still work |
| 3.5 | Claude | **"My notes"** button → opens the student's own year + branch |
| 3.6 | Claude | "Forgot password?" on login → "contact the admin for a reset" |
| 3.7 | Claude | Tests |
| ✋ | You | Register a test student, change password, edit profile, use My notes, delete the test account |

---

## Phase 4 — Notes extras (optional)
| Step | Who | Task |
|---|---|---|
| 4.1 | Claude | Subject suggestions while uploading (avoids "DBMS" vs "Dbms" duplicates) |
| 4.2 | Claude | Search box on the subjects page |
| 4.3 | Claude | "New" badge on notes from the last 7 days |
| 4.4 | Claude | Tidy "Coming Soon" cards (remove or mark as future scope) — you choose which |
| ✋ | You | Quick look in the browser |

---

## Phase 5 — Go online (free, PythonAnywhere)
| Step | Who | Task |
|---|---|---|
| 5.1 | Claude | Final check that `.env`, database, and uploads are excluded from git |
| 5.2 | Claude | Update `DEPLOYMENT.md` with exact steps for your setup |
| 5.3 | You | Push to GitHub (Claude gives the exact command; you log in when asked) |
| 5.4 | You | Create a free PythonAnywhere account |
| 5.5 | You + Claude | Claude gives copy-paste commands; you run them in PythonAnywhere's console |
| 5.6 | You | Register owner account on the live site; Claude gives the owner-grant command |
| 5.7 | You | Test on phone + laptop; note the monthly renewal date |

AI key stays empty on the live site → no bills.

---

## Phase 6 — College submission
| Step | Who | Task |
|---|---|---|
| 6.1 | Claude | Update the report (.docx): new notes flow, security features, tests |
| 6.2 | You | Take screenshots of the live site |
| 6.3 | Claude | Update the presentation (.pptx) with screenshots + "Security features" and "Future scope" slides |
| 6.4 | Claude | Write a 2-minute demo script and likely viva questions with answers |
| ✋ | You | Review report and slides |

---

## Order
Phase 0 → 1 → 2 → 3 → 5 → 6. Phase 4 only if time allows.

## Not doing now
- AI Mentor changes (future scope: free provider).
- Email password reset (free hosting restricts email; admin reset covers it).
