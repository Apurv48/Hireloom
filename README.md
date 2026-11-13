# Hireloom MVP

A local-first, interactive prototype of the candidate job-search loop from the supplied PRD and wireframes.

## Run it

1. Install Python 3.10 or newer.
2. For PDF parsing, install the optional parser once: `python -m pip install pdfplumber`.
3. Open PowerShell in this folder and run `.\run.ps1` (or `python .\server.py`).
4. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).

The server binds to localhost. The app starts on the login screen every time, including after logout. Sign-up and password login are local demo features: a random salt and PBKDF2 password hash are stored in this browser; no account server, email verification, or password recovery is connected. Profile, conversations, saved jobs, and applications are also stored in this browser. CVs are parsed in memory by the local server and are not written to disk. Use `http://127.0.0.1:8765` so browser cryptography is available.

## Included flows

- Search live public listings from Arbeitnow, Remotive, Jobicy, Himalayas and Remote OK with natural language; results are ranked against the profile in the browser and link to the original listing.
- Keep prompts and matching responses as ordered turns in the same chat; start a separate chat only with “New search.”
- Resolve location from an explicit city/country in the chat first; otherwise match the profile's interested locations and current location. Remote listings are checked against their stated country eligibility.
- Search by voice with selectable English, German, Hindi, or English-Hindi recognition; review and edit the transcript before submitting a search.
- Filter the downloaded listings by work mode, location, skills, and profile preferences without sending the CV or profile to job sites.
- Create a local demo account and log in with a password; passwords are hashed before browser storage.
- Edit a candidate profile and preferences; add and remove skills.
- Upload a PDF or DOCX (up to 5 MB), review and edit extracted identity, contact, location, career, education and skills fields, then update the profile.
- Delete individual saved search chats from the sidebar.
- Review per-job match details, matched skills, gaps, and ATS readiness.
- Edit, approve, or reject a job-specific CV draft built only from profile content.
- Download an approved, ATS-friendly DOCX CV.
- Record a native demo application or an external handoff, then update its status in the tracker.
- Save jobs, export local data, change notification preferences, and delete browser data.

## Demo boundaries

This is a runnable MVP prototype, not a connected production service. Live search uses five public feeds: Arbeitnow, Remotive, Jobicy, Himalayas and Remote OK. Jobicy, Himalayas and Remote OK add remote listings with worldwide or country-specific eligibility, so the remote search is not limited to Europe or Germany. These sources do not provide a complete worldwide index of onsite and hybrid roles; those remain limited to listings available in the other feeds. Feeds are cached locally for 30 minutes (Arbeitnow), six hours (Remotive and Remote OK), four hours (Jobicy), and 24 hours (Himalayas). Search queries and profile filters are applied locally to downloaded feeds. Providers receive feed requests from your internet connection, but Hireloom does not send them your CV, profile, or search terms. Listings may be delayed or expire, so confirm availability and eligibility on each source page. If no live feed is available, Hireloom labels its seeded sample listings as examples.

Voice transcription uses the browser's speech-recognition service when available. The selected language affects recognition, while common German, Hindi, and Hinglish job-search terms are normalized locally. The browser or its speech provider may process audio; Hireloom does not save voice recordings. Search starts only after the user reviews the transcript and presses Search. Type search remains available in browsers without speech recognition.

Local demo credentials use a salted PBKDF2 hash in browser storage and have no email verification or recovery. Match scores are deterministic heuristics; CV parsing is a local rules-based draft. Native applications and external handoffs are recorded in the local tracker only and are never sent to employers. Auto-apply remains off and is not implemented. Scanned PDFs are not OCR processed.

Feed documentation: [Arbeitnow API](https://www.arbeitnow.com/blog/job-board-api) · [Arbeitnow terms](https://www.arbeitnow.com/terms/) · [Remotive API](https://github.com/remotive-com/remote-jobs-api) · [Jobicy API](https://jobicy.com/jobs-rss-feed) · [Himalayas API](https://himalayas.app/docs/remote-jobs-api) · [Remote OK API](https://remoteok.com/faq).

No package manager or frontend build step is required.

