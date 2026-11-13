"""Local-only server for the Hireloom MVP demo."""

from __future__ import annotations

import io
import json
import re
import sys
import threading
import time
import unicodedata
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from email import policy
from email.parser import BytesParser
from html import unescape
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_FILE_BYTES + 128 * 1024

SKILLS = [
    "Python", "SQL", "JavaScript", "TypeScript", "React", "Node.js", "REST APIs",
    "APIs", "AWS", "Azure", "GCP", "Airflow", "dbt", "Spark", "Docker",
    "Kubernetes", "Data pipelines", "Machine learning", "MLflow", "Jupyter",
    "Excel", "Tableau", "Power BI", "Looker", "Product analytics", "Figma",
]

FEED_CACHE: dict[str, tuple[float, list[dict[str, object]], str]] = {}
FEED_CACHE_LOCKS = {"arbeitnow": threading.Lock(), "remotive": threading.Lock()}
FEED_CACHE_TTLS = {"arbeitnow": 30 * 60, "remotive": 6 * 60 * 60}
FEED_USER_AGENT = "HireloomMVP/1.0 (local personal job search)"


class JobDescriptionText(HTMLParser):
    """Turn provider HTML into plain text before it reaches the browser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg", "noscript"}:
            self.skip_depth += 1
        elif not self.skip_depth and tag in {"p", "br", "li", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth and tag in {"script", "style", "svg", "noscript"}:
            self.skip_depth -= 1
        elif not self.skip_depth and tag in {"p", "br", "li", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def plain_text(value: object, limit: int = 2400) -> str:
    parser = JobDescriptionText()
    try:
        parser.feed(str(value or ""))
        text = unescape(" ".join(parser.parts))
    except Exception:
        text = re.sub(r"<[^>]*>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def safe_https_url(value: object) -> str:
    url = str(value or "").strip()
    return url if urlsplit(url).scheme == "https" and urlsplit(url).netloc else ""


def fetch_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": FEED_USER_AGENT})
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("The job feed returned an unexpected response.")
    return payload


def posted_label(value: object) -> tuple[str, str]:
    try:
        if isinstance(value, (int, float)):
            timestamp = float(value)
        else:
            raw = str(value or "").replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(raw)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                timestamp = parsed.timestamp()
            except ValueError:
                timestamp = float(raw)
        age_days = max(0, int((time.time() - timestamp) / 86400))
        posted = "Today" if age_days == 0 else "Yesterday" if age_days == 1 else f"{age_days} days ago"
        return posted, str(int(timestamp))
    except (TypeError, ValueError, OverflowError):
        return "Date not listed", "0"


def known_skills(text: str) -> list[str]:
    lowered = text.lower()
    return [skill for skill in SKILLS if re.search(r"(?<![\w+#.])" + re.escape(skill.lower()) + r"(?![\w+#.])", lowered)]


COUNTRIES = [
    "Germany", "Netherlands", "France", "Spain", "Italy", "United Kingdom", "Ireland", "Sweden",
    "Denmark", "Norway", "Poland", "Portugal", "Belgium", "Austria", "Switzerland", "India",
    "United States", "Canada", "Australia", "Singapore",
]


def eligibility_for(location: str, remote: bool) -> list[str]:
    lowered = location.lower()
    normalized = normalize_location(location)
    found = [country for country in COUNTRIES if country.lower() in lowered]
    for country, aliases in LOCATION_ALIASES.items():
        if country in COUNTRIES and any(f" {normalize_location(alias)} " in f" {normalized} " for alias in aliases):
            found.append(country)
    if "europe" in lowered:
        found.append("Europe")
    if "worldwide" in lowered or "anywhere" in lowered or "global" in lowered:
        found.append("Worldwide")
    if "european union" in lowered or re.search(r"\beu\b", lowered):
        found.append("European Union")
    if not found:
        found.append("Not specified")
    return list(dict.fromkeys(found))


def job_mode(is_remote: bool, text: str) -> str:
    if is_remote:
        return "Remote"
    if re.search(r"\bhybrid\b", text, re.I):
        return "Hybrid"
    if re.search(r"\b(on[- ]?site|in[- ]office|office based)\b", text, re.I):
        return "Onsite"
    return "Flexible"


def normalize_job(record: dict[str, object], provider: str) -> dict[str, object] | None:
    if provider == "Arbeitnow":
        title = str(record.get("title") or "").strip()
        company = str(record.get("company_name") or "Company not listed").strip()
        location = str(record.get("location") or ("Remote" if record.get("remote") else "Location not listed")).strip()
        description = plain_text(record.get("description"))
        external_url = safe_https_url(record.get("url"))
        remote = bool(record.get("remote"))
        tags = record.get("tags") if isinstance(record.get("tags"), list) else []
        slug = str(record.get("slug") or external_url or title)
        posted, published = posted_label(record.get("created_at"))
        source_url = "https://www.arbeitnow.com/"
        job_id = "arbeitnow-" + re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:90]
    else:
        title = str(record.get("title") or "").strip()
        company = str(record.get("company_name") or "Company not listed").strip()
        location = str(record.get("candidate_required_location") or "Remote location not listed").strip()
        description = plain_text(record.get("description"))
        external_url = safe_https_url(record.get("url"))
        remote = True
        tags = [record.get("category", ""), record.get("job_type", "")]
        slug = str(record.get("id") or external_url or title)
        posted, published = posted_label(record.get("publication_date"))
        source_url = "https://remotive.com/"
        job_id = "remotive-" + re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:90]
    if not title or not external_url:
        return None
    full_text = f"{title} {company} {location} {description} {' '.join(str(item) for item in tags)}"
    skills = known_skills(full_text)
    sentences = [part.strip(" •\t\r\n") for part in re.split(r"(?<=[.!?])\s+|\s+[•·]\s+", description) if len(part.strip()) > 22]
    highlights = sentences[:3] or [f"Review the {skill} requirements in the original listing." for skill in skills[:3]]
    mode = job_mode(remote, full_text)
    return {
        "id": job_id, "title": title, "company": company, "location": location, "mode": mode,
        "eligible": eligibility_for(location, remote), "languages": [], "source": provider,
        "sourceUrl": source_url, "route": "External listing", "posted": posted, "published": published,
        "years": "Not listed", "match": 65, "skills": skills, "description": description or "Open the original listing for the complete job description.",
        "highlights": highlights, "reason": "Live listing matched your search. Review the original posting and eligibility before applying.",
        "url": external_url, "isLive": True,
    }


def load_arbeitnow() -> list[dict[str, object]]:
    payload = fetch_json("https://www.arbeitnow.com/api/job-board-api")
    records = payload.get("data") if isinstance(payload.get("data"), list) else []
    return [job for record in records if isinstance(record, dict) if (job := normalize_job(record, "Arbeitnow"))]


def load_remotive() -> list[dict[str, object]]:
    # Download a small broad feed on a long cache so each search stays local and respects Remotive's API guidance.
    url = "https://remotive.com/api/remote-jobs?" + urlencode({"limit": 100})
    payload = fetch_json(url)
    records = payload.get("jobs") if isinstance(payload.get("jobs"), list) else []
    return [job for record in records if isinstance(record, dict) if (job := normalize_job(record, "Remotive"))]


def cached_feed(name: str, loader) -> tuple[list[dict[str, object]], str, bool]:
    lock = FEED_CACHE_LOCKS[name]
    with lock:
        cached = FEED_CACHE.get(name)
        now = time.monotonic()
        cache_ttl = 60 if cached and cached[2] else FEED_CACHE_TTLS[name]
        if cached and now - cached[0] < cache_ttl:
            return cached[1], cached[2], True
        try:
            jobs = loader()
            error = ""
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            jobs = cached[1] if cached else []
            error = f"Could not refresh: {type(exc).__name__}" if cached else "Feed is temporarily unavailable."
        FEED_CACHE[name] = (time.monotonic(), jobs, error)
        return jobs, error, False


def job_search_tokens(query: str) -> list[str]:
    stop = {
        "a", "an", "the", "and", "or", "in", "at", "for", "with", "from", "to", "of", "by", "on",
        "job", "jobs", "role", "roles", "position", "positions", "work", "looking", "find", "search",
        "remote", "hybrid", "onsite", "on", "site", "flexible", "junior", "senior", "mid", "level",
        "year", "years", "yr", "yrs", "experience", "experienced", "speaking", "fluent", "english", "german",
        "french", "spanish", "worldwide", "anywhere",
    }
    return [token for token in re.findall(r"[a-z][a-z0-9+#.-]*", query.lower()) if token not in stop and not re.fullmatch(r"\d+\+?", token)][:12]


LOCATION_ALIASES = {
    "United States": ["united states", "usa", "us", "new york", "san francisco", "los angeles", "seattle", "austin", "boston", "chicago", "denver", "atlanta", "portland"],
    "United Kingdom": ["united kingdom", "uk", "britain", "england", "london", "manchester", "edinburgh", "birmingham", "bristol", "glasgow"],
    "Germany": ["germany", "berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne", "köln", "stuttgart", "dusseldorf", "düsseldorf"],
    "India": ["india", "bengaluru", "bangalore", "mumbai", "delhi", "new delhi", "hyderabad", "chennai", "pune", "kolkata", "ahmedabad", "jaipur", "indore", "kochi", "noida", "gurgaon", "gurugram", "lucknow", "chandigarh", "coimbatore"],
    "Canada": ["canada", "toronto", "vancouver", "montreal", "ottawa", "calgary"],
    "Australia": ["australia", "sydney", "melbourne", "brisbane", "perth"],
    "Netherlands": ["netherlands", "amsterdam", "rotterdam", "utrecht"],
    "France": ["france", "paris", "lyon", "marseille"],
    "Spain": ["spain", "madrid", "barcelona", "valencia"],
    "Ireland": ["ireland", "dublin"], "Italy": ["italy", "rome", "milan"],
    "Singapore": ["singapore"], "Sweden": ["sweden", "stockholm"],
    "Denmark": ["denmark", "copenhagen"], "Norway": ["norway", "oslo"],
    "Poland": ["poland", "warsaw", "krakow"], "Portugal": ["portugal", "lisbon", "porto"],
    "Belgium": ["belgium", "brussels"], "Austria": ["austria", "vienna"],
    "Switzerland": ["switzerland", "zurich", "geneva"],
    "European Union": ["european union", "eu"], "Europe": ["europe"],
    "Worldwide": ["worldwide", "anywhere", "global"],
}
COUNTRY_TERM_ALIASES = {
    "united states": {"usa", "us"}, "united kingdom": {"uk", "britain", "england"},
    "european union": {"eu"},
}
LOCATION_NOISE = re.compile(r"\b(?:remote|hybrid|onsite|on-site|in-office|jobs?|roles?|positions?|work|opportunities|openings?|for|with|that|paying|salary|experience|years?|yrs?)\b", re.I)
NON_LOCATION_SEARCH = re.compile(r"\b(?:software|data|product|backend|front[- ]?end|engineering|analytics|design|marketing|finance|machine learning|ai|cybersecurity|developer|engineer|analyst)\b", re.I)
EUROPE_COUNTRIES = {"germany", "netherlands", "france", "spain", "italy", "ireland", "sweden", "denmark", "norway", "poland", "portugal", "belgium", "austria"}


def normalize_location(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii")).split())


def split_location_terms(value: str) -> list[str]:
    terms = re.split(r",|;|\||/|\s+(?:or|and)\s+", value, flags=re.I)
    return [re.sub(r"^\s*(?:remote\s+)?(?:in|near|around)\s+|^\s*remote\s+", "", term, flags=re.I).strip(" .!?\t") for term in terms if term.strip(" .!?\t")]


def query_location_terms(query: str) -> list[str]:
    lowered = normalize_location(query)
    recognized = [alias for aliases in LOCATION_ALIASES.values() for alias in aliases if re.search(r"(?<!\w)" + re.escape(normalize_location(alias)) + r"(?!\w)", lowered)]
    match = re.search(r"\b(?:in|near|around|based\s+in|located\s+in)\s+(.+?)(?=\s+\b(?:remote|hybrid|onsite|on-site|english|german|french|spanish|hindi|junior|senior|for|with|jobs?|roles?|positions?|experience|years?)\b|[,;.!?]|$)", query, re.I)
    explicit: list[str] = []
    if match:
        candidate = match.group(1).strip()
        if candidate and not LOCATION_NOISE.search(candidate) and not NON_LOCATION_SEARCH.search(candidate):
            explicit = split_location_terms(candidate)
    return list(dict.fromkeys([*explicit, *recognized]))


def location_matches(job: dict[str, object], terms: list[str]) -> bool:
    if not terms:
        return True
    job_location = normalize_location(job.get("location", ""))
    eligible = [normalize_location(value) for value in job.get("eligible", []) if str(value).strip()]
    mode = str(job.get("mode", ""))
    contains = lambda text, term: bool(text and term and f" {term} " in f" {text} ")
    for term in terms:
        wanted = normalize_location(term)
        if not wanted:
            continue
        if contains(job_location, wanted) or any(contains(item, wanted) for item in eligible):
            return True
        country = next((name for name, aliases in LOCATION_ALIASES.items() if any(normalize_location(alias) == wanted for alias in aliases)), "")
        if not country:
            continue
        normalized_country = normalize_location(country)
        # City aliases can match country eligibility for remote jobs. For office roles,
        # keep city-level searches tied to the actual listing location.
        is_country_term = wanted == normalized_country or wanted in COUNTRY_TERM_ALIASES.get(normalized_country, set())
        if mode == "Remote" and any(normalize_location(alias) == wanted for alias in LOCATION_ALIASES[country]):
            if any(item in {normalized_country, "worldwide"} for item in eligible):
                return True
            if "europe" in eligible and normalized_country in EUROPE_COUNTRIES:
                return True
            if "european union" in eligible and normalized_country in EUROPE_COUNTRIES:
                return True
        if is_country_term and any(item == normalized_country for item in eligible):
            return True
        if is_country_term and (("europe" in eligible and normalized_country in EUROPE_COUNTRIES) or ("european union" in eligible and normalized_country in EUROPE_COUNTRIES)):
            return True
    return False


def filter_live_jobs(jobs: list[dict[str, object]], query: str, location_hint: str = "") -> list[dict[str, object]]:
    lowered = query.lower()
    locations = query_location_terms(query) or split_location_terms(location_hint)
    location_tokens = {token for term in locations for token in re.findall(r"[a-z][a-z0-9+#.-]*", term.lower())}
    tokens = [token for token in job_search_tokens(query) if token not in location_tokens]
    mode = "Remote" if re.search(r"\bremote\b", lowered) else "Hybrid" if re.search(r"\bhybrid\b", lowered) else "Onsite" if re.search(r"\b(on[- ]?site|in[- ]office)\b", lowered) else ""
    ranked: list[tuple[int, int, dict[str, object]]] = []
    for job in jobs:
        if mode and job.get("mode") != mode:
            continue
        searchable = " ".join(str(job.get(key, "")) for key in ("title", "company", "location", "description", "skills")).lower()
        if not location_matches(job, locations):
            continue
        score = sum(2 if token in str(job.get("title", "")).lower() else 1 for token in tokens if token in searchable)
        if tokens and score == 0:
            continue
        try:
            freshness = int(job.get("published", "0"))
        except (TypeError, ValueError):
            freshness = 0
        ranked.append((score, freshness, job))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [job for _, _, job in ranked[:60]]


def search_live_jobs(query: str, location_hint: str = "") -> dict[str, object]:
    from concurrent.futures import ThreadPoolExecutor
    providers = [("arbeitnow", load_arbeitnow, "Arbeitnow"), ("remotive", load_remotive, "Remotive")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda item: cached_feed(item[0], item[1]), providers))
    all_jobs: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    for provider, result in zip(providers, results):
        name = provider[2]
        items, error, from_cache = result
        sources.append({"name": name, "ok": bool(items) or not error, "count": len(items), "cached": from_cache, "error": error})
        all_jobs.extend(items)
    unique = {str(job["id"]): job for job in all_jobs}
    return {"jobs": filter_live_jobs(list(unique.values()), query, location_hint), "sources": sources}


def extract_document(filename: str, payload: bytes) -> tuple[str, int | None]:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        try:
            import pdfplumber  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("PDF support needs pdfplumber. Install it with: python -m pip install pdfplumber") from exc
        try:
            with pdfplumber.open(io.BytesIO(payload)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                return text, len(pdf.pages)
        except Exception as exc:  # PDF parsing errors should return a useful message to the user.
            raise ValueError("We could not read this PDF. Check that it opens normally and is not password protected.") from exc
    if extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                document = archive.read("word/document.xml")
                root = ElementTree.fromstring(document)
        except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            raise ValueError("We could not read this DOCX file. Try saving it again from your document editor.") from exc
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in root.findall(".//w:p", namespace):
            content = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
            if content.strip():
                paragraphs.append(content)
        return "\n".join(paragraphs), None
    raise ValueError("Choose a PDF or DOCX CV.")


def parse_cv(filename: str, payload: bytes) -> dict[str, object]:
    text, page_count = extract_document(filename, payload)
    normalized = re.sub(r"\s+", " ", text).strip()
    lowered = normalized.lower()
    skills: list[str] = []
    for skill in SKILLS:
        if re.search(r"(?<![\w+#.])" + re.escape(skill.lower()) + r"(?![\w+#.])", lowered):
            skills.append(skill)
    if re.search(r"\bjs\b", lowered) and "JavaScript" not in skills:
        skills.append("JavaScript")
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.I)
    phones = re.findall(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", text)
    warning = ""
    if not normalized:
        warning = "No selectable text found. Scanned CVs need OCR, which is not included in this demo."
    elif not skills:
        warning = "No skills from the demo skill list were found. You can add skills manually in your profile."
    return {
        "email": emails[0] if emails else "",
        "phone": phones[0].strip() if phones else "",
        "skills": skills,
        "summary": "",
        "pageCount": page_count,
        "warning": warning,
    }


def make_docx(payload: dict[str, object]) -> bytes:
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    version = payload.get("version") if isinstance(payload.get("version"), dict) else {}
    profile = version.get("profile") if isinstance(version.get("profile"), dict) else {}
    _job_title = str(job.get("title", "Target role"))
    name = str(profile.get("name", "Candidate"))
    contact = " · ".join(value for value in [str(profile.get("email", "")), str(profile.get("phone", "")), str(profile.get("location", ""))] if value.strip())
    skills = version.get("skills") if isinstance(version.get("skills"), list) else []
    fields = [
        (name, "Title"),
        (str(profile.get("title", "")), "Subtitle"),
        (contact, "Normal"),
        ("", "Normal"),
        ("Summary", "Heading1"),
        (str(version.get("summary", "")), "Normal"),
        ("", "Normal"),
        ("Experience", "Heading1"),
        (str(version.get("bullet", "")), "Normal"),
        ("", "Normal"),
        ("Skills", "Heading1"),
        (", ".join(str(skill) for skill in skills), "Normal"),
        ("", "Normal"),
        ("Education", "Heading1"),
        (str(profile.get("education", "")), "Normal"),
    ]
    paragraphs = []
    for text, style in fields:
        safe_text = escape("".join(char for char in text if char in "\t\n\r" or ord(char) >= 32))
        paragraphs.append(f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t xml:space="preserve">{safe_text}</w:t></w:r></w:p>')
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(paragraphs)}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1152" w:right="1152" w:bottom="1152" w:left="1152"/></w:sectPr></w:body></w:document>'
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="34"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:rPr><w:sz w:val="24"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
        '</w:styles>'
    )
    types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '</Types>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    doc_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", styles_xml)
        archive.writestr("word/_rels/document.xml.rels", doc_rels_xml)
    return output.getvalue()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/api/search-jobs":
            query = parse_qs(parsed.query).get("q", [""])[0][:240]
            location_hint = parse_qs(parsed.query).get("location", [""])[0][:180]
            try:
                self.send_json(200, search_live_jobs(query, location_hint))
            except Exception:
                self.send_json(502, {"error": "The live job feeds could not be searched right now."})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/api/render-cv":
            self.render_cv()
            return
        if path != "/api/parse-cv":
            self.send_error(404)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            self.send_json(413, {"error": "The CV upload must be 5 MB or smaller."})
            return
        body = self.rfile.read(content_length)
        content_type = self.headers.get("Content-Type", "")
        headers = BytesParser(policy=policy.default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
        )
        uploaded = next((part for part in headers.iter_parts() if part.get_content_disposition() == "form-data" and part.get_filename()), None)
        if uploaded is None:
            self.send_json(400, {"error": "Choose a PDF or DOCX CV to parse."})
            return
        filename = Path(unescape(uploaded.get_filename() or "upload")).name
        payload = uploaded.get_payload(decode=True) or b""
        if len(payload) > MAX_FILE_BYTES:
            self.send_json(413, {"error": "The CV upload must be 5 MB or smaller."})
            return
        try:
            result = parse_cv(filename, payload)
            self.send_json(200, result)
        except (ValueError, RuntimeError) as exc:
            self.send_json(422, {"error": str(exc)})

    def render_cv(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > 256 * 1024:
            self.send_json(413, {"error": "The CV draft is too large to render."})
            return
        try:
            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("Expected CV data as a JSON object.")
            document = make_docx(payload)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_json(400, {"error": "The approved CV draft could not be read."})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.send_header("Content-Disposition", 'attachment; filename="Hireloom_Approved_CV.docx"')
        self.send_header("Content-Length", str(len(document)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(document)

    def send_json(self, status: int, data: dict[str, object]) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        # Keep search text out of the terminal log along with CV content and submitted form fields.
        message = re.sub(r"(/api/search-jobs)\?[^\s\"]*", r"\1", format % args)
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.address_string()} {message}\n")


if __name__ == "__main__":
    print(f"Hireloom MVP running at http://{HOST}:{PORT}")
    print("This demo binds to localhost. Uploaded CVs are parsed in memory and are not saved by the server.")
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nHireloom MVP stopped.")

