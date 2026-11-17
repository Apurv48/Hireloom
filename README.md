# Hireloom MVP

A local-first, interactive prototype of the candidate job-search loop from the supplied PRD and wireframes.

## Run it

1. Install Python 3.10 or newer.
2. For PDF parsing, install the optional parser once: `python -m pip install pdfplumber`.
3. Open PowerShell in this folder and run `.\run.ps1` (or `python .\server.py`).
4. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).

When run locally, the server binds to localhost. The app starts on the login screen every time, including after logout. Sign-up and password login are local demo features: a random salt and PBKDF2 password hash are stored in this browser; no account server, email verification, or password recovery is connected. Profile, conversations, saved jobs, and applications are also stored in this browser. CV files are uploaded to the Hireloom server for in-memory parsing and are not retained by the app. Use `http://127.0.0.1:8765` locally so browser cryptography is available.

## Deploy to Render

The repository includes a Render Blueprint (`render.yaml`) for a Python web service. Connect the GitHub repository in Render and create a Blueprint from it. The free service plan avoids a hosting charge, but Render may spin the service down after 15 minutes without traffic, so the first request after idle can take longer. The free plan is intended for previewing and hobby projects, not production use.

Hireloom keeps the demo account, profile, chats and tracker in each user's browser; it has no server-side account database or password recovery. A CV uploaded to a hosted version leaves the user's device and is sent to the Hireloom server for in-memory parsing; it is not retained by the app. Do not upload confidential applicant data or use this MVP for real hiring until it has production authentication, security and privacy reviews.

## Included flows

- Search the built in demonstration job catalog; results are ranked against the profile in the browser.
- Keep prompts and matching responses as ordered turns in the same chat; start a separate chat only with “New search.”
- Resolve location from an explicit city/country in the chat first; otherwise match the profile's interested locations and current location. Remote listings are checked against their stated country eligibility.
- Search by voice with selectable English, German, Hindi, or English-Hindi recognition; review and edit the transcript before submitting a search.
- Filter demonstration listings by work mode, location, skills, and profile preferences.
- Create a local demo account and log in with a password; passwords are hashed before browser storage.
- Edit a candidate profile and preferences; add and remove skills.
- Upload a text-based PDF or DOCX (up to 5 MB), review every profile field against the CV, including contact details, career history, education, skills, achievements, certifications, languages and any explicitly stated preferences, then choose what to update. Missing CV values stay unchanged.
- Delete individual saved search chats from the sidebar.
- Review per-job match details, matched skills, gaps, and ATS readiness.
- Edit, approve, or reject a job-specific CV draft built only from profile content.
- Download an approved, ATS-friendly DOCX CV.
- Record every application in the tracker. Company career-page roles are saved with an `Opened` status before the original application page opens, then the user can confirm whether they applied and continue updating the status.
- Save jobs, export local data, change notification preferences, and delete browser data.

## Demo boundaries

This is a runnable MVP prototype, not a production hiring service. Job search uses only the built in demonstration catalog. It does not call job boards or external job search APIs, and the sample listings are not current vacancies.

Voice transcription uses the browser's speech-recognition service when available. The selected language affects recognition, while common German, Hindi, and Hinglish job-search terms are normalized locally. The browser or its speech provider may process audio; Hireloom does not save voice recordings. Search starts only after the user reviews the transcript and presses Search. Type search remains available in browsers without speech recognition.

Local demo credentials use a salted PBKDF2 hash in browser storage and have no email verification or recovery. Match scores are deterministic heuristics; CV parsing is a local rules-based draft. Native applications and external handoffs are recorded in the local tracker only and are never sent to employers. Auto-apply remains off and is not implemented. Scanned PDFs are not OCR processed.

No package manager or frontend build step is required.

