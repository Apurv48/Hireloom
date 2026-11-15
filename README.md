# Hireloom MVP

A local-first, interactive prototype of the candidate job-search loop from the supplied PRD and wireframes.

## Run it

1. Install Python 3.10 or newer.
2. For PDF parsing, install the optional parser once: `python -m pip install pdfplumber`.
3. Open PowerShell in this folder and run `.\run.ps1` (or `python .\server.py`; it serves `public/` and the same API routes).
4. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).

When run locally, the server binds to localhost. The app starts on the login screen every time, including after logout. Sign-up and password login are local demo features: a random salt and PBKDF2 password hash are stored in this browser; no account server, email verification, or password recovery is connected. Profile, conversations, saved jobs, and applications are also stored in this browser. CV files are uploaded to the Hireloom server for in-memory parsing and are not retained by the app. Use `http://127.0.0.1:8765` locally so browser cryptography is available.

## Deploy to Vercel

The repository is set up for Vercel (`vercel.json`). Static files live in `public/`, and the three API routes (`/api/search-jobs`, `/api/parse-cv`, `/api/render-cv`) are Python serverless functions in `api/` that reuse the logic in `server.py`.

1. In Vercel choose **Add New → Project** and import this GitHub repository.
2. Keep the framework preset on **Other**. No build command is needed and no environment variables are required; Vercel installs `requirements.txt` for the functions. To add on-site and hybrid jobs in India and other countries, set the optional `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` variables (see Job coverage).
3. Deploy. Every push to `main` redeploys automatically.

Things to know on Vercel: the job-feed cache lives in each warm function instance, so the first search after a quiet period refetches the feeds and can take a few seconds. CV uploads are capped at 1 MB (see Accounts and storage). The Hobby plan is meant for personal, non-commercial projects.

In local demo mode Hireloom keeps the demo account, profile, chats and tracker in each user's browser; it has no server-side account database or password recovery, and a CV sent to the server is parsed in memory and not retained. In Supabase mode accounts, workspaces and each user's latest CV are stored in your Supabase project (see below). Either way, do not upload confidential applicant data or use this MVP for real hiring until it has production authentication, security and privacy reviews.

## Accounts and storage (Supabase)

Hireloom can sign users in and keep their workspace on any device using a free [Supabase](https://supabase.com) project. Until you configure it, the app runs in the local demo mode described above.

1. Create a Supabase project (the free plan is enough).
2. Open **SQL Editor**, paste the contents of `supabase/schema.sql` and run it. It creates the `user_data` table, a private `cvs` storage bucket limited to 1 MB PDF/DOCX files, Row Level Security rules so each user can only read and change their own data, and a `delete_my_account()` function.
3. Open **Project Settings → API** and copy the project URL and the `anon public` key into `public/config.js`. The anon key is designed to be public; the Row Level Security rules protect the data. Never put the `service_role` key in this repository.
4. Open **Authentication → URL Configuration** and set the Site URL to your deployed address. Under **Redirect URLs** add the same address (for example `https://your-app.vercel.app/**`) and `http://127.0.0.1:8765/**` for local testing. Password-reset emails link back to the site the user is on, and Supabase only honours addresses on this list.
5. Open **Authentication → Providers → Email**. Supabase's built-in email sender is heavily rate-limited, so for anything beyond testing either turn off "Confirm email" or add your own SMTP provider.
6. Commit `public/config.js` and redeploy.

What it does:

- **Forgot password:** the login page has a "Forgot password?" link. The user enters their email and receives a reset link; opening it shows a "Choose a new password" page (8+ characters), saves the password in Supabase Auth and signs them in. The same confirmation is shown whether or not the address has an account, and expired or reused links show a message with the option to request a new one. The email text and sender can be edited under **Authentication → Email Templates**; the built-in sender is rate-limited (see step 5), so use your own SMTP provider for real traffic. Local demo accounts cannot be reset because there is no email service.
- **Accounts:** email and password sign-up and login handled by Supabase Auth. Passwords are never stored by Hireloom. Sessions persist on each device and log out only that device.
- **Workspace sync:** profile, chats, saved jobs, tracker, tailored CVs and settings are saved to one row per user a couple of seconds after each change, and loaded at login. Search results are not synced because they come from live feeds; each search re-runs on the device you open it on. The latest change wins if two devices are edited at once.
- **CV storage:** after the user confirms a parsed CV, the file is stored privately as `<user id>/cv.pdf` or `cv.docx`. Each user has one stored CV and a new upload replaces it, which keeps storage small. The 1 MB limit is enforced in the browser, in `server.py` and by the bucket itself. Users can download their stored CV from the Profile page. At up to 1 MB per user the free 1 GB of file storage covers at least 1,000 users, and far more with typical CV sizes.
- **Shared devices:** logging out clears the local copy of the workspace so accounts never mix on one browser.
- **Delete account:** Settings → Privacy removes the login, workspace row and stored CV.

Known gaps: no email-change flow, no "change password" form for users who are already logged in, and the Supabase free plan pauses projects after a week without activity and has no automatic backups.

## Job coverage (India, English-speaking and India-friendly countries)

When a search names no place, Hireloom looks across `DEFAULT_MARKETS`, together with the places in the profile: India, the United States, United Kingdom, Canada, Australia, New Zealand, Ireland, Singapore, South Africa, the Gulf states (UAE, Saudi Arabia, Qatar, Oman, Kuwait, Bahrain), Germany, France, the Netherlands, Japan, Malaysia, Sri Lanka and Nepal. Worldwide remote jobs always match, and listings in India are ranked first when no place is named. A place named in the search (for example "data analyst in Pune" or "jobs in Canada") overrides the defaults. The "India-friendly" part of the list is a judgement call: edit `DEFAULT_MARKETS` in `server.py` and `public/app.js` (keep both in sync) to add or remove countries.

The free remote feeds carry few on-site or hybrid jobs outside Germany. For those, create a free key at [developer.adzuna.com](https://developer.adzuna.com/) and set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` as environment variables (in Vercel: Project Settings → Environment Variables; locally, set them before running `server.py`). Adzuna is then queried per country: India, UK, US, Canada, Australia, Singapore and South Africa by default, or the countries named in the search. Set `ADZUNA_COUNTRIES` (a comma-separated list of the codes in `ADZUNA_COUNTRY_CODES`, for example `in,gb,sg`) to change the defaults. Without keys the Adzuna source is simply skipped. Adzuna listings link to the Adzuna page; please keep the "Jobs by Adzuna" attribution that its terms ask for and check its current rate limits.

## Included flows

- Search live public listings from Arbeitnow, Remotive, Jobicy, Himalayas, Remote OK and (optionally) Adzuna with natural language; results are ranked against the profile in the browser and link to the original listing.
- Keep prompts and matching responses as ordered turns in the same chat; start a separate chat only with “New search.”
- Resolve location from an explicit city/country in the chat first; otherwise match the profile's interested locations and current location. Remote listings are checked against their stated country eligibility.
- Search by voice with selectable English, German, Hindi, or English-Hindi recognition; review and edit the transcript before submitting a search.
- Filter the downloaded listings by work mode, location, skills, and profile preferences without sending the CV or profile to job sites.
- Create an account and log in on any device (Supabase mode), or a local demo account whose password hash stays in this browser (default when Supabase is not configured).
- Edit a candidate profile and preferences; add and remove skills.
- Upload a text-based PDF or DOCX (up to 1 MB), review every profile field against the CV, including contact details, career history, education, skills, achievements, certifications, languages and any explicitly stated preferences, then choose what to update. Missing CV values stay unchanged.
- Delete individual saved search chats from the sidebar.
- Review per-job match details, matched skills, gaps, and ATS readiness.
- Edit, approve, or reject a job-specific CV draft built only from profile content.
- Download an approved, ATS-friendly DOCX CV.
- Record a native demo application or an external handoff, then update its status in the tracker.
- Save jobs, export local data, change notification preferences, and delete browser data.

## Demo boundaries

This is a runnable MVP prototype, not a production hiring service. Live search uses five public feeds (Arbeitnow, Remotive, Jobicy, Himalayas and Remote OK) plus Adzuna when keys are set. Jobicy, Himalayas and Remote OK add remote listings with worldwide or country-specific eligibility, so the remote search is not limited to Europe or Germany. Arbeitnow is Germany-only. Without Adzuna keys, onsite and hybrid roles outside Germany are limited to what the remote feeds happen to list. Feeds are cached in server memory for 30 minutes (Arbeitnow and each Adzuna search), six hours (Remotive and Remote OK), four hours (Jobicy), and 24 hours (Himalayas). A hosted search phrase and location are sent to the Hireloom server for matching; the server downloads public feeds without forwarding the CV, profile or search phrase to the job providers. Listings may be delayed or expire, so confirm availability and eligibility on each source page. If no live feed is available, Hireloom labels its seeded sample listings as examples.

Voice transcription uses the browser's speech-recognition service when available. The selected language affects recognition, while common German, Hindi, and Hinglish job-search terms are normalized locally. The browser or its speech provider may process audio; Hireloom does not save voice recordings. Search starts only after the user reviews the transcript and presses Search. Type search remains available in browsers without speech recognition.

Local demo credentials use a salted PBKDF2 hash in browser storage and have no email verification or recovery. Match scores are deterministic heuristics; CV parsing is a local rules-based draft. Native applications and external handoffs are recorded in the local tracker only and are never sent to employers. Auto-apply remains off and is not implemented. Scanned PDFs are not OCR processed.

Feed documentation: [Arbeitnow API](https://www.arbeitnow.com/blog/job-board-api) · [Arbeitnow terms](https://www.arbeitnow.com/terms/) · [Remotive API](https://github.com/remotive-com/remote-jobs-api) · [Jobicy API](https://jobicy.com/jobs-rss-feed) · [Himalayas API](https://himalayas.app/docs/remote-jobs-api) · [Remote OK API](https://remoteok.com/faq) · [Adzuna API](https://developer.adzuna.com/).

No package manager or frontend build step is required.

