"""HTTP server for the Hireloom MVP, runnable locally or on a web host."""

from __future__ import annotations

import io
import json
import os
import re
import sys
import threading
import time
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache
from xml.sax.saxutils import escape
from email import policy
from email.parser import BytesParser
from html import unescape
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "public"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))
# One CV per account is stored in Supabase Storage (free tier: 1 GB), so keep uploads small.
# This also sits well under Vercel's 4.5 MB request limit. Keep in sync with public/app.js, public/cloud.js and supabase/schema.sql.
MAX_FILE_BYTES = 1 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_FILE_BYTES + 128 * 1024

SKILLS = [
    "Python", "SQL", "JavaScript", "TypeScript", "React", "Node.js", "REST APIs",
    "APIs", "AWS", "Azure", "GCP", "Airflow", "dbt", "Spark", "Docker",
    "Kubernetes", "Data pipelines", "Machine learning", "MLflow", "Jupyter",
    "Excel", "Tableau", "Power BI", "Looker", "Product analytics", "Figma",
]

FEED_CACHE: dict[str, tuple[float, list[dict[str, object]], str]] = {}
# Public, employer-managed career boards. Search queries and CV data stay off these requests.
CAREER_BOARDS = {"twilio": "Twilio", "rubrik": "Rubrik", "gitlab": "GitLab"}
FEED_CACHE_LOCKS = {board: threading.Lock() for board in CAREER_BOARDS}
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
    try:
        parsed = urlsplit(url)
        return url if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password else ""
    except ValueError:
        return ""


def fetch_json_value(url: str) -> object:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": FEED_USER_AGENT})
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, (dict, list)):
        raise ValueError("The job feed returned an unexpected response.")
    return payload


def fetch_json(url: str) -> dict[str, object]:
    payload = fetch_json_value(url)
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


COUNTRY_CODES = {
    "AE": "United Arab Emirates", "AR": "Argentina", "AT": "Austria", "AU": "Australia",
    "BD": "Bangladesh", "BE": "Belgium", "BG": "Bulgaria", "BH": "Bahrain", "BR": "Brazil",
    "CA": "Canada", "CH": "Switzerland", "CL": "Chile", "CN": "China", "CO": "Colombia",
    "CR": "Costa Rica", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany", "DK": "Denmark",
    "DO": "Dominican Republic", "DZ": "Algeria", "EC": "Ecuador", "EE": "Estonia", "EG": "Egypt",
    "ES": "Spain", "FI": "Finland", "FR": "France", "GB": "United Kingdom", "GH": "Ghana",
    "GR": "Greece", "HK": "Hong Kong", "HR": "Croatia", "HU": "Hungary", "ID": "Indonesia",
    "IE": "Ireland", "IL": "Israel", "IN": "India", "IQ": "Iraq", "IS": "Iceland", "IT": "Italy",
    "JP": "Japan", "KE": "Kenya", "KR": "South Korea", "KW": "Kuwait", "LK": "Sri Lanka",
    "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MA": "Morocco", "MX": "Mexico",
    "MY": "Malaysia", "NG": "Nigeria", "NL": "Netherlands", "NO": "Norway", "NP": "Nepal",
    "NZ": "New Zealand", "OM": "Oman", "PE": "Peru", "PH": "Philippines", "PK": "Pakistan",
    "PL": "Poland", "PT": "Portugal", "QA": "Qatar", "RO": "Romania", "RS": "Serbia",
    "RU": "Russia", "SA": "Saudi Arabia", "SE": "Sweden", "SG": "Singapore", "SI": "Slovenia",
    "SK": "Slovakia", "TH": "Thailand", "TN": "Tunisia", "TR": "Türkiye", "TW": "Taiwan",
    "UA": "Ukraine", "US": "United States", "UY": "Uruguay", "VE": "Venezuela", "VN": "Vietnam",
    "ZA": "South Africa", "ZM": "Zambia", "ZW": "Zimbabwe", "UK": "United Kingdom",
}
COUNTRIES = sorted(set(COUNTRY_CODES.values()) | {
    "Germany", "Netherlands", "France", "Spain", "Italy", "United Kingdom", "Ireland", "Sweden",
    "Denmark", "Norway", "Poland", "Portugal", "Belgium", "Austria", "Switzerland", "India",
    "United States", "Canada", "Australia", "Singapore",
})


@lru_cache(maxsize=1024)
def eligibility_for(location: str, remote: bool) -> list[str]:
    lowered = location.lower()
    normalized = normalize_location(location)
    found = [country for country in COUNTRIES if f" {country.lower()} " in f" {normalized} "]
    for country, aliases in LOCATION_ALIASES.items():
        if country in COUNTRIES and any(f" {normalize_location(alias)} " in f" {normalized} " for alias in aliases):
            found.append(country)
    if re.search(r"\beurope\b", lowered):
        found.append("Europe")
    if "worldwide" in lowered or "anywhere" in lowered or "global" in lowered:
        found.append("Worldwide")
    if "european union" in lowered or re.search(r"\beu\b", lowered):
        found.append("European Union")
    if not found:
        found.append("Not specified")
    return list(dict.fromkeys(found))


def job_mode(is_remote: bool, text: str) -> str:
    if re.search(r"\bhybrid\b", text, re.I):
        return "Hybrid"
    if is_remote:
        return "Remote"
    if re.search(r"\b(on[- ]?site|in[- ]office|office based)\b", text, re.I):
        return "Onsite"
    return "Not listed"


def load_career_board(board: str) -> list[dict[str, object]]:
    company = CAREER_BOARDS[board]
    payload = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
    if not isinstance(payload.get("jobs"), list):
        raise ValueError("Invalid career board response")
    jobs = []
    for record in payload["jobs"]:
        if not isinstance(record, dict) or not isinstance(record.get("id"), int):
            continue
        title = plain_text(record.get("title"), 240)
        url = safe_https_url(record.get("absolute_url"))
        if not title or not url:
            continue
        place = record.get("location") or {}
        location = plain_text(place.get("name"), 500) if isinstance(place, dict) else ""
        description = plain_text(unescape(record.get("content") or ""), 6000)
        mode_text = f"{title} {location}"
        remote = bool(re.search(r"\bremote\b|work from home", mode_text, re.I))
        mode = job_mode(remote, mode_text)
        posted, published = posted_label(record.get("first_published"))
        jobs.append({
            "id": f"{board}-{record['id']}", "title": title, "company": company,
            "location": location or "Location not listed", "mode": mode,
            "eligible": eligibility_for(location, remote), "languages": [],
            "source": company, "sourceUrl": f"https://job-boards.greenhouse.io/{board}",
            "route": "Company career page", "url": url, "posted": posted, "published": published,
            "years": "Not listed", "match": 65, "skills": known_skills(f"{title} {description}"),
            "description": description or "See the employer’s posting for details.",
            "highlights": [], "reason": "Review the requirements and work location on the company career page.",
            "isLive": True,
        })
    return jobs


def cached_feed(board: str) -> tuple[list[dict[str, object]], str, bool]:
    with FEED_CACHE_LOCKS[board]:
        cached = FEED_CACHE.get(board)
        now = time.monotonic()
        if cached:
            saved_at, jobs, error = cached
            if now - saved_at < (60 if error else 1800):
                return jobs, error, True
        try:
            jobs, error = load_career_board(board), ""
        except (OSError, ValueError, TimeoutError):
            jobs, error = [], "Career page temporarily unavailable."
        FEED_CACHE[board] = time.monotonic(), jobs, error
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
LOCATION_ALIASES.update({
    "United Arab Emirates": ["united arab emirates", "uae", "dubai", "abu dhabi"],
    "Argentina": ["argentina", "buenos aires"], "Brazil": ["brazil", "sao paulo", "são paulo", "rio de janeiro"],
    "Bangladesh": ["bangladesh", "dhaka"], "Bahrain": ["bahrain", "manama"], "Bulgaria": ["bulgaria", "sofia"],
    "China": ["china", "beijing", "shanghai", "shenzhen", "guangzhou"], "Colombia": ["colombia", "bogota", "bogotá", "medellin"],
    "Costa Rica": ["costa rica", "san jose", "san josé"], "Czechia": ["czechia", "czech republic", "prague"],
    "Egypt": ["egypt", "cairo"], "Finland": ["finland", "helsinki"], "Ghana": ["ghana", "accra"],
    "Greece": ["greece", "athens"], "Hong Kong": ["hong kong"], "Hungary": ["hungary", "budapest"],
    "Indonesia": ["indonesia", "jakarta"], "Israel": ["israel", "tel aviv", "jerusalem"],
    "Japan": ["japan", "tokyo", "osaka", "kyoto"], "Kenya": ["kenya", "nairobi"],
    "South Korea": ["south korea", "korea", "seoul"], "Kuwait": ["kuwait", "kuwait city"],
    "Sri Lanka": ["sri lanka", "colombo"], "Lithuania": ["lithuania", "vilnius"],
    "Luxembourg": ["luxembourg", "luxembourg city"], "Latvia": ["latvia", "riga"],
    "Morocco": ["morocco", "casablanca", "rabat"], "Mexico": ["mexico", "mexico city", "guadalajara"],
    "Malaysia": ["malaysia", "kuala lumpur"], "Nigeria": ["nigeria", "lagos", "abuja"],
    "Nepal": ["nepal", "kathmandu"], "New Zealand": ["new zealand", "auckland", "wellington"],
    "Oman": ["oman", "muscat"], "Peru": ["peru", "lima"], "Philippines": ["philippines", "manila"],
    "Pakistan": ["pakistan", "karachi", "lahore", "islamabad"], "Qatar": ["qatar", "doha"],
    "Romania": ["romania", "bucharest"], "Russia": ["russia", "moscow"],
    "Saudi Arabia": ["saudi arabia", "riyadh", "jeddah"], "South Africa": ["south africa", "cape town", "johannesburg", "durban"],
    "Slovenia": ["slovenia", "ljubljana"], "Slovakia": ["slovakia", "bratislava"], "Thailand": ["thailand", "bangkok"],
    "Tunisia": ["tunisia", "tunis"], "Türkiye": ["türkiye", "turkey", "istanbul", "ankara"],
    "Taiwan": ["taiwan", "taipei"], "Ukraine": ["ukraine", "kyiv", "kiev"],
    "Chile": ["chile", "santiago"], "Ecuador": ["ecuador", "quito"], "Estonia": ["estonia", "tallinn"],
    "Croatia": ["croatia", "zagreb"], "Iceland": ["iceland", "reykjavik"], "Iraq": ["iraq", "baghdad"],
    "Uruguay": ["uruguay", "montevideo"], "Venezuela": ["venezuela", "caracas"], "Vietnam": ["vietnam", "hanoi", "ho chi minh city", "saigon"],
    "Zambia": ["zambia", "lusaka"], "Zimbabwe": ["zimbabwe", "harare"],
})
for country in COUNTRIES:
    LOCATION_ALIASES.setdefault(country, [country.lower()])
COUNTRY_TERM_ALIASES = {
    "united states": {"usa", "us"}, "united kingdom": {"uk", "britain", "england"},
    "european union": {"eu"},
}
LOCATION_NOISE = re.compile(r"\b(?:remote|hybrid|onsite|on-site|in-office|jobs?|roles?|positions?|work|opportunities|openings?|for|with|that|paying|salary|experience|years?|yrs?)\b", re.I)
NON_LOCATION_SEARCH = re.compile(r"\b(?:software|data|product|backend|front[- ]?end|engineering|analytics|design|marketing|finance|machine learning|ai|cybersecurity|developer|engineer|analyst)\b", re.I)
EUROPE_COUNTRIES = {"germany", "netherlands", "france", "spain", "italy", "ireland", "sweden", "denmark", "norway", "poland", "portugal", "belgium", "austria"}


# Where Hireloom looks when a search does not name a place: India, the main English-speaking
# countries, and countries with close ties to India (Gulf states, Germany, France, Netherlands,
# Japan, Malaysia, Sri Lanka, Nepal). Edit this list to change the default coverage. Keep it in sync
# with DEFAULT_MARKETS in public/app.js. Remote jobs open "worldwide" always match.
DEFAULT_MARKETS = (
    "India",
    "United States", "United Kingdom", "Canada", "Australia", "New Zealand", "Ireland", "Singapore", "South Africa",
    "United Arab Emirates", "Saudi Arabia", "Qatar", "Oman", "Kuwait", "Bahrain",
    "Germany", "France", "Netherlands", "Japan", "Malaysia", "Sri Lanka", "Nepal",
)


@lru_cache(maxsize=4096)
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
        refers_to_profile = re.fullmatch(r"(?:me|here|my\s+(?:current\s+)?location|my\s+area|where\s+i\s+am)", candidate, re.I)
        if candidate and not refers_to_profile and not LOCATION_NOISE.search(candidate) and not NON_LOCATION_SEARCH.search(candidate):
            explicit = split_location_terms(candidate)
    return list(dict.fromkeys([*explicit, *recognized]))


# Different spellings of the same city, so "Bangalore" also finds listings that say "Bengaluru".
CITY_SYNONYMS = ({"bangalore", "bengaluru"}, {"gurgaon", "gurugram"}, {"mumbai", "bombay"}, {"chennai", "madras"}, {"kolkata", "calcutta"}, {"delhi", "new delhi"})


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
        # Worldwide remote postings accept candidates from any profile or chat location.
        if mode == "Remote" and "worldwide" in eligible:
            return True
        variants = next((group for group in CITY_SYNONYMS if wanted in group), {wanted})
        if any(contains(job_location, name) or any(contains(item, name) for item in eligible) for name in variants):
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


def resolve_search(query: str, location_hint: str = "") -> tuple[list[str], list[str]]:
    """Return (places to match, keywords). A place named in the search wins. Otherwise the profile's
    places are used. Default markets apply to an empty profile."""
    explicit = query_location_terms(query)
    profile_terms = [] if explicit else split_location_terms(location_hint)
    locations = explicit or profile_terms or list(DEFAULT_MARKETS)
    location_tokens = {token for term in (explicit or profile_terms) for token in re.findall(r"[a-z][a-z0-9+#.-]*", term.lower())}
    return locations, [token for token in job_search_tokens(query) if token not in location_tokens]


def filter_live_jobs(jobs: list[dict[str, object]], query: str, location_hint: str = "") -> list[dict[str, object]]:
    lowered = query.lower()
    locations, tokens = resolve_search(query, location_hint)
    prefer_india = not query_location_terms(query)
    mode = "Remote" if re.search(r"\bremote\b", lowered) else "Hybrid" if re.search(r"\bhybrid\b", lowered) else "Onsite" if re.search(r"\b(on[- ]?site|in[- ]office)\b", lowered) else ""
    ranked: list[tuple[int, int, int, dict[str, object]]] = []
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
        in_india = int(prefer_india and ("India" in job.get("eligible", []) or "india" in normalize_location(job.get("location", "")).split()))
        ranked.append((score, in_india, freshness, job))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return [job for _, _, _, job in ranked[:60]]


def search_live_jobs(query: str, location_hint: str = "") -> dict[str, object]:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=len(CAREER_BOARDS)) as pool:
        results = list(pool.map(cached_feed, CAREER_BOARDS))
    all_jobs = []
    sources = []
    for company, (items, error, cached) in zip(CAREER_BOARDS.values(), results):
        sources.append({"name": company, "ok": not error, "count": len(items), "cached": cached, "error": error})
        all_jobs.extend(items)
    unique = {str(job["id"]): job for job in all_jobs}
    return {"jobs": filter_live_jobs(list(unique.values()), query, location_hint), "sources": sources}


def extract_document(filename: str, payload: bytes) -> tuple[str, int | None]:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        if not payload.lstrip()[:5] == b"%PDF-":
            raise ValueError("This file is not a real PDF. Save your CV as a PDF and upload that file.")
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
    raise ValueError("Only PDF CVs are accepted. Save your CV as a PDF and upload that file.")


def parse_cv(filename: str, payload: bytes) -> dict[str, object]:
    text, page_count = extract_document(filename, payload)
    normalized = re.sub(r"\s+", " ", text).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sections: dict[str, list[str]] = {
        "summary": [], "experience": [], "education": [], "skills": [],
        "achievements": [], "certifications": [], "languages": [], "preferences": [], "roles": [],
    }
    current_section = ""
    section_headers = {
        "summary": re.compile(r"^(?:profile|professional profile|professional summary|summary|objective|about me|career summary|personal statement)$", re.I),
        "experience": re.compile(r"^(?:professional experience|work experience|employment history|work history|career history|experience|professional background)$", re.I),
        "education": re.compile(r"^(?:education|educational background|academic background|academics|academic qualifications)$", re.I),
        "skills": re.compile(r"^(?:skills|technical skills|core skills|key skills|core competencies|areas of expertise|technical expertise|technologies|tools and technologies|skills and tools)$", re.I),
        "achievements": re.compile(r"^(?:achievements?|key achievements|accomplishments|awards?|honors?|honours?)$", re.I),
        "certifications": re.compile(r"^(?:certifications?|certificates?|licenses and certifications|licences and certifications|licenses|licences)$", re.I),
        "languages": re.compile(r"^(?:languages|language skills|language proficiency|languages and proficiency)$", re.I),
        "preferences": re.compile(r"^(?:job preferences|employment preferences|career preferences|work preferences|preferences|job search preferences)$", re.I),
        "roles": re.compile(r"^(?:target roles|interested roles|roles of interest|target positions|positions of interest)$", re.I),
    }
    other_sections = re.compile(r"^(?:projects?|publications?|volunteering|volunteer experience|interests|hobbies|references|personal details|contact details|internships?|extracurricular activities)\s*:?$", re.I)
    for line in lines:
        candidate = line.strip(" \t•|:-–—")
        section = next((key for key, pattern in section_headers.items() if pattern.match(candidate.rstrip(":"))), "")
        if section:
            current_section = section
            continue
        if other_sections.match(candidate):
            current_section = ""
            continue
        if current_section:
            sections[current_section].append(candidate)

    def labeled_value(labels: str) -> str:
        match = re.search(rf"(?im)^\s*(?:{labels})\s*[:=–—-]\s*(.*?)\s*$", text)
        return match.group(1).strip(" \t|·-–—") if match else ""

    def cleaned_lines(values: list[str]) -> list[str]:
        return [re.sub(r"\s+", " ", value.strip(" \t•*-–—▪◦")).strip() for value in values if value.strip(" \t•*-–—▪◦")]

    def list_values(values: list[str]) -> list[str]:
        found: list[str] = []
        for line in cleaned_lines(values):
            for item in re.split(r"\s*(?:[,;|·•▪◦]|\s{2,})\s*", line):
                item = re.sub(r"^(?:skills?|tools?|technologies|languages?|certifications?|achievements?)\s*:\s*", "", item, flags=re.I).strip(" \t:-–—")
                if item and len(item) <= 180 and item.lower() not in {value.lower() for value in found}:
                    found.append(item)
        return found

    def first_nonempty(*values: str) -> str:
        return next((value.strip() for value in values if value and value.strip()), "")

    name = labeled_value(r"(?:full\s+)?name")
    if not name:
        name_skip = re.compile(r"\b(?:resume|curriculum vitae|engineer|developer|analyst|manager|designer|scientist|consultant|architect|specialist|intern|objective|profile|summary|linkedin|portfolio)\b", re.I)
        for line in lines[:10]:
            candidate = re.split(r"[|•·]", line, maxsplit=1)[0].strip(" :-–—")
            words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]*", candidate)
            if 2 <= len(words) <= 4 and len(candidate) <= 60 and not re.search(r"[@\d:/]", candidate) and not name_skip.search(candidate):
                name = candidate
                break

    role_terms = re.compile(r"\b(?:engineer|developer|analyst|manager|designer|scientist|consultant|architect|specialist|intern|director|lead|recruiter|teacher|nurse|accountant|researcher|sales|product|marketing|coordinator|administrator|technician|founder|officer|assistant|professor|executive|operator|writer|editor|mechanic|therapist|doctor|lawyer|chef|account executive|strategist|producer|owner|auditor|consultant|advisor|associate|technologist|support|operations|human resources|hr|pharmacist|veterinarian|trainer|developer advocate)\b", re.I)
    date_pattern = re.compile(r"\b(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+)?(?:19|20)\d{2}(?:\s*(?:[-–—]|to)\s*(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+)?(?:(?:19|20)\d{2}|present|current|now))?|\b(?:present|current|now)\b", re.I)
    title = labeled_value(r"(?:current\s+title|professional\s+title|current(?:\s*/\s*or)?\s*target\s+(?:role|title)|target\s+(?:role|title)|current\s+(?:role|position)|job\s+title|position\s+title|role)")
    experience_lines = sections["experience"] + [value for value in [labeled_value(r"(?:professional\s+)?experience|employment\s+history|work\s+history")] if value]
    experiences: list[dict[str, str]] = []
    current_experience: dict[str, str] | None = None
    for raw_line in experience_lines[:120]:
        clean = raw_line.strip(" \t•*-–—▪◦")
        if not clean:
            continue
        is_bullet = bool(re.match(r"^\s*[•*▪◦-]", raw_line))
        date_match = date_pattern.search(clean)
        without_dates = date_pattern.sub("", clean).strip(" ,;|·-–—")
        looks_like_role = bool(role_terms.search(without_dates)) and len(without_dates) <= 140
        separated = bool(re.search(r"\s+(?:at|@)\s+|\s*[|·—]\s*", without_dates, re.I))
        starts_experience = looks_like_role and not is_bullet and (bool(date_match) or separated or len(without_dates.split()) <= 10)
        if starts_experience:
            if len(experiences) >= 20:
                break
            title_company = re.split(r"\s+(?:at|@)\s+", without_dates, maxsplit=1, flags=re.I)
            if len(title_company) == 1:
                title_company = [part.strip() for part in re.split(r"\s*(?:\||·|—|,)\s*", without_dates, maxsplit=2) if part.strip()]
            item_title = title_company[0].strip(" ,;|·-–—")[:120]
            item_company = title_company[1].strip(" ,;|·-–—")[:120] if len(title_company) > 1 else ""
            current_experience = {"title": item_title, "company": item_company, "dates": date_match.group(0).strip() if date_match else "", "detail": ""}
            experiences.append(current_experience)
            continue
        if current_experience:
            if date_match and not current_experience["dates"]:
                current_experience["dates"] = date_match.group(0).strip()
                remainder = date_pattern.sub("", clean).strip(" ,;|·-–—")
                if remainder and not current_experience["company"]:
                    current_experience["company"] = remainder[:120]
            elif not is_bullet and not current_experience["company"] and len(clean.split()) <= 6 and len(clean) <= 100:
                current_experience["company"] = clean[:120]
            elif clean and len(clean) > 4:
                current_experience["detail"] = (current_experience["detail"] + " " + clean).strip()[:1200]

    if not experiences:
        exp_title = first_nonempty(labeled_value(r"(?:current\s+)?(?:job\s+)?(?:role|position|job\s+title)"), title)
        exp_company = labeled_value(r"(?:current\s+)?(?:company|employer|organization|organisation)")
        exp_dates = labeled_value(r"(?:employment\s+)?(?:dates|duration|tenure)")
        exp_detail = labeled_value(r"(?:key\s+)?(?:responsibilities|experience\s+details|role\s+description)")
        if any((exp_title, exp_company, exp_dates, exp_detail)):
            experiences.append({"title": exp_title, "company": exp_company, "dates": exp_dates, "detail": exp_detail})
    if not title and experiences:
        title = experiences[0]["title"]
    if not title:
        for line in lines[:12]:
            if role_terms.search(line) and len(line) <= 100:
                title = re.split(r"\s*[|·—]\s*", line, maxsplit=1)[0].strip()
                break

    location = labeled_value(r"(?:current\s+)?(?:location|based\s+in|address|city\s+and\s+country)")
    if not location:
        aliases = sorted((alias for values in LOCATION_ALIASES.values() for alias in values if len(alias) > 3), key=len, reverse=True)
        for line in lines[:18]:
            for segment in re.split(r"\s*[|·•]\s*", line):
                normalized_segment = normalize_location(segment)
                if any(re.search(r"(?<!\w)" + re.escape(normalize_location(alias)) + r"(?!\w)", normalized_segment) for alias in aliases):
                    location = segment.strip(" ,;:-")[:100]
                    break
            if location:
                break

    skills = list_values(sections["skills"] + [value for value in [labeled_value(r"(?:technical\s+)?skills?|core\s+competencies|technologies|tools") ] if value])
    for skill in SKILLS:
        if re.search(r"(?<![\w+#.])" + re.escape(skill.lower()) + r"(?![\w+#.])", normalized, re.I) and skill.lower() not in {value.lower() for value in skills}:
            skills.append(skill)
    if re.search(r"\bjs\b", normalized, re.I) and "JavaScript" not in skills:
        skills.append("JavaScript")
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.I)
    phones = re.findall(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", text)
    email = first_nonempty(labeled_value(r"(?:email|e-mail|email\s+address)"), emails[0] if emails else "")
    phone = first_nonempty(labeled_value(r"(?:phone|telephone|mobile|mobile\s+number|contact\s+number)"), phones[0].strip() if phones else "")
    summary = first_nonempty(" ".join(cleaned_lines(sections["summary"])), labeled_value(r"(?:professional\s+)?(?:profile\s+)?summary|objective|about\s+me"))[:1200]
    education = " · ".join(cleaned_lines(sections["education"]))[:1200]
    if not education:
        education = labeled_value(r"(?:education|degree|qualification|highest\s+qualification)")[:1200]
    if not education:
        education = " · ".join(line.strip(" \t•*-–—") for line in lines if re.search(r"\b(?:bachelor|master|ph\.?d|doctorate|diploma|degree|university|college|institute|school)\b", line, re.I))[:1200]

    achievements = list_values(sections["achievements"] + [value for value in [labeled_value(r"(?:key\s+)?(?:achievements|accomplishments|awards|honors|honours)")] if value])
    certifications = list_values(sections["certifications"] + [value for value in [labeled_value(r"(?:certifications?|certificates?|licenses?|licences?)")] if value])
    roles = list_values(sections["roles"] + [value for value in [labeled_value(r"(?:interested\s+roles?|roles?\s+of\s+interest|target\s+roles?|target\s+positions?|desired\s+roles?)")] if value])
    languages = first_nonempty(" · ".join(cleaned_lines(sections["languages"])), labeled_value(r"(?:spoken\s+)?languages?(?:\s+and\s+proficiency)?|language\s+proficiency"))[:600]

    gender_raw = labeled_value(r"gender|sex")
    gender_key = re.sub(r"[^a-z]+", " ", gender_raw.lower()).strip()
    gender_map = {"female": "Woman", "woman": "Woman", "male": "Man", "man": "Man", "non binary": "Non-binary", "nonbinary": "Non-binary", "prefer not to say": "Prefer not to say", "self describe": "Self describe", "other": "Self describe"}
    gender = gender_map.get(gender_key, gender_raw if gender_raw in {"Woman", "Man", "Non-binary", "Self describe", "Prefer not to say"} else "")

    dob_raw = labeled_value(r"(?:date\s+of\s+birth|birth\s+date|dob)")
    dob = ""
    if dob_raw:
        from datetime import date
        for date_format in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                dob = datetime.strptime(dob_raw.strip(), date_format).date().isoformat()
                break
            except ValueError:
                continue
        if not dob:
            numeric = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", dob_raw.strip())
            if numeric and int(numeric.group(1)) > 12:
                try:
                    dob = date(int(numeric.group(3)), int(numeric.group(2)), int(numeric.group(1))).isoformat()
                except ValueError:
                    pass

    preference_text = " ".join(sections["preferences"])
    work_modes_raw = first_nonempty(labeled_value(r"(?:preferred\s+)?work\s+modes?|work\s+arrangement|employment\s+type"), preference_text)
    work_modes: list[str] = []
    for pattern, mode in ((r"\bremote\b", "Remote"), (r"\bhybrid\b", "Hybrid"), (r"\b(?:onsite|on-site|in[- ]office|office[- ]based)\b", "Onsite")):
        if work_modes_raw and re.search(pattern, work_modes_raw, re.I):
            work_modes.append(mode)
    interested_location = first_nonempty(labeled_value(r"(?:interested|preferred|desired|target|work)\s+locations?|location\s+preferences?|preferred\s+work\s+location"))[:240]
    scope_raw = labeled_value(r"(?:search|job|location)\s+scope")
    scope_key = re.sub(r"[^a-z]+", " ", scope_raw.lower()).strip()
    scope = "Both" if any(term in scope_key for term in ("both", "national and international", "domestic and international")) else "International" if any(term in scope_key for term in ("international", "global", "worldwide")) else "National" if any(term in scope_key for term in ("national", "domestic", "local")) else ""
    relocation = first_nonempty(
        labeled_value(r"(?:relocation\s+preferences?|willing\s+to\s+relocate|open\s+to\s+relocation)"),
        (match.group(0).strip() if (match := re.search(r"(?im)^\s*(?:willing\s+to\s+relocate|open\s+to\s+relocation)\b[^\n]*", text)) else ""),
    )[:240]
    salary = labeled_value(r"(?:expected\s+salary|desired\s+salary|target\s+salary|salary\s+expectation|salary\s+range|expected\s+compensation|desired\s+compensation)")[:120]
    current_salary = labeled_value(r"(?:current\s+salary|current\s+compensation|present\s+salary)")[:120]

    warning = ""
    if not normalized:
        warning = "No selectable text found. Scanned CVs need OCR, which is not included in this demo."
    elif not skills:
        warning = "No skills section or known skills were detected. Review the blank fields and add any skills manually."
    return {
        "name": name,
        "gender": gender,
        "dob": dob,
        "email": email,
        "phone": phone,
        "location": location,
        "title": title,
        "education": education,
        "experience": experiences,
        "skills": skills,
        "summary": summary,
        "achievements": achievements,
        "certifications": certifications,
        "roles": roles,
        "languages": languages,
        "interestedLocation": interested_location,
        "workModes": work_modes,
        "scope": scope,
        "relocation": relocation,
        "salary": salary,
        "currentSalary": current_salary,
        "pageCount": page_count,
        "warning": warning,
    }


def pdf_safe(text: str) -> str:
    """Keep only characters the built-in PDF fonts can draw, so the CV never shows boxes."""
    cleaned = "".join(char for char in str(text) if char in "\t\n" or ord(char) >= 32)
    cleaned = cleaned.replace("\t", " ").replace("\u00a0", " ").replace("\u2022", "-")
    return "".join(char if char in "\n" or _encodable(char) else "?" for char in cleaned)


def _encodable(char: str) -> bool:
    try:
        char.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def make_pdf(payload: dict[str, object]) -> bytes:
    """Build the approved, ATS-friendly CV as a single-column PDF with real, selectable text."""
    try:
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError("PDF CV creation needs reportlab. Install it with: python -m pip install reportlab") from exc

    version = payload.get("version") if isinstance(payload.get("version"), dict) else {}
    profile = version.get("profile") if isinstance(version.get("profile"), dict) else {}
    name = pdf_safe(str(profile.get("name", "")).strip()) or "Candidate"
    headline = pdf_safe(str(profile.get("title", "")).strip())
    contact = " | ".join(pdf_safe(str(profile.get(key, "")).strip()) for key in ("email", "phone", "location") if str(profile.get(key, "")).strip())
    skills = version.get("skills") if isinstance(version.get("skills"), list) else []
    skill_line = pdf_safe(", ".join(str(skill).strip() for skill in skills if str(skill).strip()))

    base = ParagraphStyle("base", fontName="Helvetica", fontSize=10.5, leading=14.5, alignment=TA_LEFT, textColor="#111111")
    title = ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=2)
    subtitle = ParagraphStyle("subtitle", parent=base, fontSize=12, leading=16, textColor="#333333")
    small = ParagraphStyle("small", parent=base, fontSize=9.5, textColor="#444444", spaceAfter=4)
    heading = ParagraphStyle("heading", parent=base, fontName="Helvetica-Bold", fontSize=12, leading=16, spaceBefore=12, spaceAfter=3)

    def para(text: str, style) -> Paragraph:
        return Paragraph(escape(text).replace("\n", "<br/>"), style)

    story: list = [para(name, title)]
    if headline:
        story.append(para(headline, subtitle))
    if contact:
        story.append(para(contact, small))
    story.append(HRFlowable(width="100%", thickness=0.6, color="#999999", spaceBefore=2, spaceAfter=2))

    def section(label: str, body: str, bullets: bool = False) -> None:
        body = body.strip()
        if not body:
            return
        story.append(para(label, heading))
        if bullets:
            items = [line.strip(" -*\t") for line in body.splitlines() if line.strip(" -*\t")]
            story.append(ListFlowable([ListItem(para(item, base), leftIndent=12) for item in items], bulletType="bullet", start="-", leftIndent=12, bulletFontSize=10))
        else:
            story.append(para(body, base))

    section("Summary", pdf_safe(str(version.get("summary", ""))))
    section("Experience", pdf_safe(str(version.get("bullet", ""))), bullets=True)
    section("Skills", skill_line)
    section("Education", pdf_safe(str(profile.get("education", ""))))
    story.append(Spacer(1, 2 * mm))

    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"{name} - CV", author=name, creator="Hireloom", pageCompression=1,
    )
    document.build(story)
    return output.getvalue()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/api/search-jobs":
            query = parse_qs(parsed.query).get("q", [""])[0][:240]
            location_hint = parse_qs(parsed.query).get("location", [""])[0][:180]
            try:
                self.send_json(200, search_live_jobs(query, location_hint))
            except Exception:
                self.send_json(502, {"error": "Company career pages could not be searched right now."})
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
        body = self.read_body(MAX_REQUEST_BYTES, "The CV upload must be 1 MB or smaller.")
        if body is None:
            return
        content_type = self.headers.get("Content-Type", "")
        headers = BytesParser(policy=policy.default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
        )
        uploaded = next((part for part in headers.iter_parts() if part.get_content_disposition() == "form-data" and part.get_filename()), None)
        if uploaded is None:
            self.send_json(400, {"error": "Choose a PDF CV to parse."})
            return
        filename = Path(unescape(uploaded.get_filename() or "upload")).name
        payload = uploaded.get_payload(decode=True) or b""
        if len(payload) > MAX_FILE_BYTES:
            self.send_json(413, {"error": "The CV upload must be 1 MB or smaller."})
            return
        try:
            result = parse_cv(filename, payload)
            self.send_json(200, result)
        except (ValueError, RuntimeError) as exc:
            self.send_json(422, {"error": str(exc)})

    def read_body(self, limit: int, size_error: str) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                raise ValueError
        except ValueError:
            self.send_json(400, {"error": "A request body with a valid length is required."})
            return None
        if length > limit:
            self.send_json(413, {"error": size_error})
            return None
        return self.rfile.read(length)

    def render_cv(self) -> None:
        body = self.read_body(256 * 1024, "The CV draft is too large to render.")
        if body is None:
            return
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict) or not isinstance(payload.get('version'), dict):
                raise ValueError("Expected an approved CV version.")
            document = make_pdf(payload)
        except RuntimeError as exc:
            self.send_json(500, {"error": str(exc)})
            return
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_json(400, {"error": "The approved CV draft could not be read."})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", 'attachment; filename="Hireloom_Approved_CV.pdf"')
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
    print("Uploaded CVs are parsed in memory and are not saved by the server.")
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nHireloom MVP stopped.")

