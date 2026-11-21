# Hireloom MVP

A candidate can search employer career boards, tailor a CV, and track applications. The prototype runs locally and on Vercel, with Supabase accounts on the hosted site.

**Live app:** [https://hireloom-nine.vercel.app](https://hireloom-nine.vercel.app/)

## Run it

1. Install Python 3.10 or newer.
2. Install the dependencies for PDF reading and export with `python -m pip install -r requirements.txt`.
3. Open PowerShell in this folder and run `.\run.ps1` (or `python .\server.py`; it serves `public/` and the same API routes).
4. Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The hosted version is at [hireloom-nine.vercel.app](https://hireloom-nine.vercel.app/).

The local server binds to localhost. With Supabase configured, local and hosted sessions use the same account service. To try browser-only accounts, leave both settings in `public/config.js` empty in your local checkout. Each demo login has its own browser workspace. An existing single-account demo can recover its previous workspace when the saved profile email matches the login.

## Deploy to Vercel

The repository is set up for Vercel (`vercel.json`). Static files live in `public/`, and the three API routes (`/api/search-jobs`, `/api/parse-cv`, `/api/render-cv`) are Python serverless functions in `api/` that reuse the logic in `server.py`.

1. In Vercel choose **Add New → Project** and import this GitHub repository.
2. Keep the framework preset on **Other**. No build command is needed and no environment variables are required; Vercel installs `requirements.txt` for the functions. Job search reads public employer boards without a key.
3. Deploy. Every push to `main` redeploys automatically. This project's deployment is at [https://hireloom-nine.vercel.app](https://hireloom-nine.vercel.app).

Things to know on Vercel: the job-feed cache lives in each warm function instance, so the first search after a quiet period refetches the feeds and can take a few seconds. CV uploads are capped at 1 MB (see Accounts and storage). The Hobby plan is meant for personal, non-commercial projects.

In local demo mode Hireloom keeps the demo account, profile, chats and tracker in each user's browser; it has no server-side account database or password recovery, and a CV sent to the server is parsed in memory and not retained. In Supabase mode accounts, workspaces and each user's latest CV are stored in your Supabase project (see below). Either way, do not upload confidential applicant data or use this MVP for real hiring until it has production authentication, security and privacy reviews.

## Accounts and storage (Supabase)

Hireloom can sign users in and keep their workspace on any device using a free [Supabase](https://supabase.com) project. Until you configure it, the app runs in the local demo mode described above.

1. Create a Supabase project (the free plan is enough).
2. Open **SQL Editor**, paste the contents of `supabase/schema.sql` and run it. It creates the `user_data` table, a private `cvs` storage bucket limited to 1 MB PDF files, Row Level Security rules so each user can only read and change their own data, and a `delete_my_account()` function.
3. Open **Project Settings → API** and copy the project URL and the `anon public` key into `public/config.js`. The anon key is designed to be public; the Row Level Security rules protect the data. Never put the `service_role` key in this repository.
4. Open **Authentication → URL Configuration** and set the Site URL to your deployed address (for this project `https://hireloom-nine.vercel.app`). Under **Redirect URLs** add the same address and `http://127.0.0.1:8765/**` for local testing.
5. Set up custom SMTP under **Authentication → Emails → SMTP Settings**. Supabase will not let you edit email templates until this is on, and its built-in sender only delivers to your own team's addresses and is heavily rate-limited, so reset codes will not reach ordinary users without it. With no custom domain, the simplest option is Gmail: turn on 2-Step Verification, create an App Password at myaccount.google.com/apppasswords, then use host `smtp.gmail.com`, port `465`, your full Gmail address as both username and sender email, and the 16-character app password (no spaces) as the password. Gmail allows about 500 emails a day; for real traffic move to a transactional provider on your own domain (Resend, Brevo and similar).
6. Open **Authentication → Email Templates → Reset Password** and replace the template body with the contents of `supabase/recovery-email-template.html` (paste the file as it is, and set the Subject field above the body to `Your Hireloom password reset code`). This makes the password-reset email carry a one-time code (`{{ .Token }}`) instead of a link; without this step the email still contains Supabase's default reset link and the code screen will have nothing to verify. In **Authentication → Providers → Email** you can also set the code length (6 digits is the default and what the screen expects) and how long a code stays valid.
7. Open **Authentication → Providers → Email**. Decide whether to keep "Confirm email" on (new users must click the confirmation email before logging in) or turn it off for frictionless sign-up while testing.
8. Commit `public/config.js` and redeploy.

What it does:

- **Forgot password (email code):** the login page has a "Forgot password?" link. The user enters their email and Supabase sends a one-time numeric code (no link). They type the code into Hireloom, which verifies it with Supabase; only then does the "Choose a new password" page (8+ characters) appear, and saving it signs them in. The same screen is shown whether or not the address has an account, a wrong or expired code shows an error without signing anyone in, resending is limited to once a minute, and closing the tab after verifying but before saving a password brings the user back to the new-password step instead of logging them in. The email wording is edited under **Authentication → Email Templates**; emails are sent through the SMTP provider from step 5. Local demo accounts cannot be reset because there is no email service.
- **Accounts:** email and password sign-up and login handled by Supabase Auth. Passwords are never stored by Hireloom. Sessions persist on each device and log out only that device.
- **Workspace sync:** profile, chats, saved jobs, tracker, tailored CVs and settings are saved to one row per user a couple of seconds after each change, and loaded at login. Completed replies, result counts and up to 512 KB of listing previews sync across devices. Saved and tracked roles keep separate snapshots. Rerun a prompt to fetch current openings. The latest change wins if two devices are edited at once.
- **CV storage:** after the user confirms a parsed CV, the file is stored privately as `<user id>/cv.pdf`. Each user has one stored CV and a new upload replaces it, which keeps storage small. The 1 MB limit is enforced in the browser, in `server.py` and by the bucket itself. Users can download their stored CV from the Profile page. At up to 1 MB per user the free 1 GB of file storage covers at least 1,000 users, and far more with typical CV sizes.
- **Shared devices:** logging out clears the local copy of the workspace so accounts never mix on one browser.
- **Delete account:** Settings → Privacy removes the login, workspace row and stored CV.

Troubleshooting reset emails: if the app says a code is on its way but nothing arrives, open Supabase **Logs → Auth** and look for the `/recover` entry. A 200 means Supabase accepted the request and the problem is delivery (check Spam and All Mail; confirm the SMTP settings and app password). "Error sending recovery email" means the SMTP login is being rejected, usually a wrong or space-containing app password, 2-Step Verification being off, or a username that differs from the sender address.

Known gaps: no email-change flow, no "change password" form for users who are already logged in, and the Supabase free plan pauses projects after a week without activity and has no automatic backups.

## Company career search

Hireloom searches a generated index of public postings from 300 fixed company career boards. The registry in `data/company_boards.json` contains 135 Greenhouse, 105 Ashby and 60 Lever boards, including India-focused and global employers. No job-search API key is used. Matching runs inside Hireloom and only the employer’s original application link opens when a user chooses **Track and apply**.

The `Refresh company jobs` GitHub Actions workflow rebuilds the index every day from those public employer feeds. It commits the refreshed compressed shards and manifest used by the deployed API, and also replaces the `job-index` release asset. Searches use the bundled shards immediately, so a user request neither waits for the release host nor sends their prompt, profile or CV to 300 companies. `HIRELOOM_JOB_INDEX_URL` can explicitly enable a remote index override; it is disabled by default and has a two-second timeout. Run `python scripts/refresh_job_index.py` to rebuild both index formats manually. Empty or changed-shape feeds are reported as failures, and the refresh keeps the previous index if fewer than 270 sources respond successfully.

An explicit location in chat takes precedence over profile locations. A profile without locations gets the default markets, including India. Listings include the employer's posting date and work mode when supplied. The search request also carries your work-mode preference, so only matching work modes are ranked. The employer controls vacancy availability.

## Included flows

- Search employer listings by role, skills, location and work mode. Open **Saved** to revisit bookmarked roles, including after deleting the original chat.
- Keep prompts and matching responses as ordered turns in the same chat; start a separate chat only with “New search.” Editing a prompt changes that same turn and refreshes its results instead of adding a new prompt; “Refine with a new prompt” is the way to add a follow-up turn.
- A short follow-up such as “only remote ones” or “in Pune” updates the mode or location of the previous search. The chat shows the resulting query. Rerunning a turn uses that turn’s saved query.
- Resolve location from an explicit city/country in the chat first; otherwise match the profile's interested locations and current location. Remote listings are checked against their stated country eligibility.
- Search by voice with selectable English, German, Hindi, or English-Hindi recognition; review and edit the transcript before submitting a search.
- Filter the downloaded listings by work mode, location, skills, and profile preferences without sending the CV or profile to job sites.
- Create an account and log in on any device (Supabase mode), or a local demo account whose password hash stays in this browser (default when Supabase is not configured).
- Edit a candidate profile and preferences; add and remove skills.
- Choose a PDF CV (up to 1 MB; DOCX and other formats are not accepted). Hireloom first asks whether you want it to read the CV: if you say no, nothing is parsed, sent or stored and you fill in your profile by hand. If you say yes, the PDF is parsed (text-based PDFs only) and you review every profile field against the CV, including contact details, career history, education, skills, achievements, certifications, languages and any explicitly stated preferences, then choose what to update. Missing CV values stay unchanged.
- Delete individual saved search chats from the sidebar.
- Review per-job match details, matched skills, gaps, and ATS readiness.
- Edit, approve, or reject a job-specific CV draft built only from profile content.
- Download an approved, ATS-friendly CV as a PDF (single column, selectable text, standard fonts). CVs are created and downloaded only as PDF.
- Choose **Track and apply** to save the role as Opened, then confirm submission and record later status changes in Tracker.
- Save jobs, export local data, change notification preferences, and delete browser data.

## Demo boundaries

The hosted job index is refreshed daily. A company can change its board URL, remove a role between refreshes or temporarily reject a refresh request. Hireloom records unavailable sources in the index metadata, and the employer’s page remains the final source of truth. A successful search can contain zero matches.

Voice transcription uses the browser's speech-recognition service when available. The selected language affects recognition, while common German, Hindi, and Hinglish job-search terms are normalized locally. The browser or its speech provider may process audio; Hireloom does not save voice recordings. Search starts only after the user reviews the transcript and presses Search. Type search remains available in browsers without speech recognition.

Local demo credentials use a salted PBKDF2 hash in browser storage. Match scores and CV parsing use rules. Text extraction requires a PDF with selectable text. The candidate completes the application on the employer’s site and confirms submission in Tracker. Supabase accounts sync the tracker across devices. Local demo accounts keep it in their browser.

Employer board references: [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), and [Ashby Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api). The initial fixed registry was selected from SignalFeed’s public [ATS company directory](https://signalfeed.github.io/jobs/companies-using-greenhouse-lever-ashby/) and is stored in this repository so runtime behavior never depends on that directory.

No package manager or frontend build step is required.

## Regression checks

Run `python -m unittest discover -s tests -v` for employer search and PDF checks. Run `node --test tests/cloud-sync.test.cjs` for save ordering, account ownership and retries. To exercise the UI locally, install Python Playwright and its Chromium browser, then run `python tests/browser_smoke.py`. The browser check uses fixture listings and disposable local accounts.

