"""HTTP server for the Hireloom MVP, runnable locally or on a web host."""

from __future__ import annotations

import io
import gzip
import json
import os
import re
import sys
import tempfile
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
from uuid import UUID
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "public"
JOB_INDEX_PATH = ROOT / "data" / "jobs.json.gz"
JOB_INDEX_MANIFEST_PATH = ROOT / "data" / "job_index.json"
JOB_INDEX_REMOTE_URL = os.environ.get(
    "HIRELOOM_JOB_INDEX_URL",
    "",
)
JOB_INDEX_REMOTE_CACHE_SECONDS = 4 * 60 * 60
JOB_INDEX_MAX_BYTES = 12 * 1024 * 1024
JOB_INDEX_DOWNLOAD_PATH = Path(tempfile.gettempdir()) / "hireloom-jobs.json.gz"
JOB_INDEX_DOWNLOAD_LOCK = threading.Lock()
JOB_INDEX_LAST_CHECK = float("-inf")
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))
# One CV per account is stored in Supabase Storage (free tier: 1 GB), so keep uploads small.
# This also sits well under Vercel's 4.5 MB request limit. Keep in sync with public/app.js, public/cloud.js and supabase/schema.sql.
MAX_FILE_BYTES = 1 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_FILE_BYTES + 128 * 1024
MAX_PDF_PAGES = 30
CV_RATE_LIMIT = 12
CV_RATE_WINDOW_SECONDS = 60
CV_RATE_LOCK = threading.Lock()
CV_RATE_BUCKETS: dict[str, list[float]] = {}
SEARCH_RATE_LIMIT = 30

SKILLS = [
    "Python", "SQL", "JavaScript", "TypeScript", "React", "Node.js", "REST APIs",
    "APIs", "AWS", "Azure", "GCP", "Airflow", "dbt", "Spark", "Docker",
    "Kubernetes", "Data pipelines", "Machine learning", "MLflow", "Jupyter",
    "Excel", "Tableau", "Power BI", "Looker", "Product analytics", "Figma",
    "Accounting", "Bookkeeping", "Financial analysis", "Auditing", "Taxation",
    "Sales", "Business development", "Customer service", "Retail", "Merchandising",
    "Marketing", "Digital marketing", "SEO", "Content writing", "Public relations",
    "Human resources", "Recruitment", "Payroll", "Training", "Project management",
    "Operations", "Procurement", "Supply chain", "Logistics", "Inventory management",
    "Quality assurance", "Quality control", "Lean manufacturing", "AutoCAD", "SolidWorks",
    "Mechanical engineering", "Electrical engineering", "Civil engineering", "Construction",
    "Nursing", "Patient care", "Pharmacy", "Clinical research", "Medical coding",
    "Teaching", "Curriculum development", "Counselling", "Research", "Legal research",
    "Contract management", "Compliance", "Risk management", "Hospitality", "Food safety",
    "Event management", "Real estate", "Relationship management", "Communication",
    "Leadership", "Negotiation", "Problem solving", "Team management",
]

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


def plain_text(value: object, limit: int | None = 2400) -> str:
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
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        age_days = max(0, int((time.time() - timestamp) / 86400))
        posted = "Today" if age_days == 0 else "Yesterday" if age_days == 1 else f"{age_days} days ago"
        return posted, str(int(timestamp))
    except (TypeError, ValueError, OverflowError):
        return "Date not listed", "0"


def known_skills(text: str) -> list[str]:
    lowered = text.lower()
    return [skill for skill in SKILLS if re.search(r"(?<![\w+#])" + re.escape(skill.lower()) + r"(?![\w+#])", lowered)]


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
    if re.search(r"\b(?:worldwide|anywhere|global)\b", lowered):
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


def normalize_public_job(source: dict[str, object], record: dict[str, object]) -> dict[str, object] | None:
    """Normalize one Greenhouse, Ashby, or Lever posting for the generated search index."""
    provider = str(source.get("provider", ""))
    slug = str(source.get("slug", ""))
    company = plain_text(source.get("company"), 160)
    careers_url = safe_https_url(source.get("careers_url"))
    record_id = record.get("id")
    provider_mode = ""
    if not company or not slug or record_id in (None, ""):
        return None

    if provider == "greenhouse":
        title = plain_text(record.get("title"), 240)
        place = record.get("location") or {}
        location = plain_text(place.get("name"), 500) if isinstance(place, dict) else ""
        url = safe_https_url(record.get("absolute_url"))
        description = plain_text(unescape(record.get("content") or ""), None)
        published_value = record.get("first_published") or record.get("updated_at")
        remote = bool(re.search(r"\bremote\b|work from home", f"{title} {location}", re.I))
    elif provider == "ashby":
        title = plain_text(record.get("title"), 240)
        primary = plain_text(record.get("location"), 300)
        secondary = record.get("secondaryLocations") or []
        extra_locations = [plain_text(item.get("location") if isinstance(item, dict) else item, 160) for item in secondary if item]
        location = ", ".join(dict.fromkeys(value for value in [primary, *extra_locations] if value))
        url = safe_https_url(record.get("jobUrl") or record.get("applyUrl"))
        description = plain_text(record.get("descriptionPlain") or record.get("descriptionHtml"), None)
        published_value = record.get("publishedAt")
        remote = bool(record.get("isRemote")) or bool(re.search(r"\bremote\b|work from home", f"{title} {location}", re.I))
    elif provider == "lever":
        title = plain_text(record.get("text"), 240)
        categories = record.get("categories") or {}
        if not isinstance(categories, dict):
            categories = {}
        all_locations = categories.get("allLocations") or []
        location_values = [plain_text(categories.get("location"), 300)]
        location_values.extend(plain_text(value, 160) for value in all_locations if value)
        location = ", ".join(dict.fromkeys(value for value in location_values if value))
        url = safe_https_url(record.get("hostedUrl") or record.get("applyUrl"))
        description = plain_text(record.get("descriptionPlain") or record.get("description"), None)
        published_value = record.get("createdAt")
        workplace_type = str(record.get("workplaceType", "")).lower()
        provider_mode = {"remote": "Remote", "hybrid": "Hybrid", "on-site": "Onsite", "onsite": "Onsite"}.get(workplace_type, "")
        remote = workplace_type == "remote" or bool(re.search(r"\bremote\b|work from home", f"{title} {location}", re.I))
    else:
        return None

    if not title or not url:
        return None
    mode = provider_mode or job_mode(remote, f"{title} {location}")
    posted, published = posted_label(published_value)
    return {
        "id": f"{provider}-{slug}-{record_id}", "title": title, "company": company,
        "location": location or "Location not listed", "mode": mode,
        "eligible": eligibility_for(location, remote), "languages": [],
        "source": company, "sourceUrl": careers_url, "route": "Company career page", "url": url,
        "posted": posted, "published": published, "years": "Not listed", "match": 65,
        "skills": known_skills(f"{title} {description}"),
        "description": description[:1200] or "See the employer’s posting for details.",
        "highlights": [], "reason": "Review the requirements and work location on the company career page.",
        "isLive": True,
    }


@lru_cache(maxsize=4)
def _load_job_index(path: str, mtime_ns: int) -> dict[str, object]:
    del mtime_ns
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("The company job index is invalid.")
    return payload


@lru_cache(maxsize=2)
def _load_bundled_job_index(mtime_ns: int) -> dict[str, object]:
    del mtime_ns
    payload = json.loads(JOB_INDEX_MANIFEST_PATH.read_text(encoding="utf-8"))
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list) or not files:
        raise ValueError("The bundled company job index is invalid.")
    jobs = []
    for filename in files:
        path = ROOT / "data" / Path(str(filename)).name
        shard = _load_job_index(str(path), path.stat().st_mtime_ns)
        jobs.extend(shard["jobs"])
    payload["jobs"] = jobs
    if len(jobs) != int(payload.get("job_count", -1)):
        raise ValueError("The bundled company job index is incomplete.")
    return payload


def _refresh_remote_job_index() -> Path | None:
    global JOB_INDEX_LAST_CHECK
    if not JOB_INDEX_REMOTE_URL:
        return None
    cached = JOB_INDEX_DOWNLOAD_PATH if JOB_INDEX_DOWNLOAD_PATH.exists() else None
    interval = JOB_INDEX_REMOTE_CACHE_SECONDS if cached else 60
    if time.monotonic() - JOB_INDEX_LAST_CHECK >= interval and JOB_INDEX_DOWNLOAD_LOCK.acquire(blocking=False):
        JOB_INDEX_LAST_CHECK = time.monotonic()
        threading.Thread(target=_download_remote_index, daemon=True).start()
    return cached


def _download_remote_index() -> None:
    try:
        request = Request(JOB_INDEX_REMOTE_URL, headers={"User-Agent": FEED_USER_AGENT})
        with urlopen(request, timeout=2) as response:
            payload = response.read(JOB_INDEX_MAX_BYTES + 1)
        if len(payload) > JOB_INDEX_MAX_BYTES:
            return
        with tempfile.NamedTemporaryFile(dir=JOB_INDEX_DOWNLOAD_PATH.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
        try:
            _load_job_index(str(temporary), temporary.stat().st_mtime_ns)
            temporary.replace(JOB_INDEX_DOWNLOAD_PATH)
        finally:
            temporary.unlink(missing_ok=True)
    except (OSError, ValueError, EOFError):
        pass
    finally:
        JOB_INDEX_DOWNLOAD_LOCK.release()


def load_job_index() -> dict[str, object]:
    remote = _refresh_remote_job_index()
    if remote:
        return _load_job_index(str(remote), remote.stat().st_mtime_ns)
    if JOB_INDEX_PATH.exists():
        return _load_job_index(str(JOB_INDEX_PATH), JOB_INDEX_PATH.stat().st_mtime_ns)
    return _load_bundled_job_index(JOB_INDEX_MANIFEST_PATH.stat().st_mtime_ns)


def job_search_tokens(query: str) -> list[str]:
    stop = {
        "a", "an", "the", "and", "or", "in", "at", "for", "with", "from", "to", "of", "by", "on",
        "job", "jobs", "role", "roles", "position", "positions", "work", "looking", "find", "search",
        "remote", "hybrid", "onsite", "on", "site", "flexible", "junior", "senior", "mid", "level",
        "year", "years", "yr", "yrs", "experience", "experienced", "speaking", "fluent", "english", "german",
        "french", "spanish", "worldwide", "anywhere",
    }
    return [token for token in re.findall(r"[a-z][a-z0-9+#.-]*", query.lower()) if token not in stop and not re.fullmatch(r"\d+\+?", token)][:12]


# Keep in sync with SEARCH_SYNONYMS in public/app.js.
SEARCH_SYNONYMS = {
    "ml": ("machine learning",), "ai": ("artificial intelligence",), "pm": ("product manager",),
    "js": ("javascript",), "ts": ("typescript",), "k8s": ("kubernetes",), "qa": ("quality assurance",), "ux": ("user experience",),
}
WORK_MODES = {"Remote", "Hybrid", "Onsite"}
UNLISTED_MODES = {"Flexible", "Not listed"}


def token_matchers(token: str) -> list[tuple[str, re.Pattern[str]]]:
    """Whole-word matchers for a keyword and its synonyms. 'java' does not match 'javascript'; a plural s is allowed."""
    return [(term, re.compile(rf"(?<![a-z0-9]){re.escape(term)}s?(?![a-z0-9])")) for term in (token, *SEARCH_SYNONYMS.get(token, ()))]


def fields_hit(text: str, matchers: list[tuple[str, re.Pattern[str]]]) -> bool:
    # The substring check is a cheap pre-filter; the regex runs only on likely hits.
    return any(term in text and pattern.search(text) is not None for term, pattern in matchers)


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
    searchable = re.sub(r"\bus\b", lambda m: "us" if re.search(r"\b(?:in|near|across|within|the)\s+$", query[:m.start()], re.I) else " ", query)
    searchable = re.sub(r"\bglobal\b(?!\s*(?:$|jobs?\b|roles?\b|remote\b))", " ", searchable, flags=re.I)
    lowered = normalize_location(searchable)
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


def filter_live_jobs(jobs: list[dict[str, object]], query: str, location_hint: str = "", work_modes: list[str] | None = None, profile_skills: tuple[str, ...] = ()) -> list[dict[str, object]]:
    lowered = query.lower()
    locations, tokens = resolve_search(query, location_hint)
    prefer_india = not query_location_terms(query)
    mode = "Remote" if re.search(r"\bremote\b", lowered) else "Hybrid" if re.search(r"\bhybrid\b", lowered) else "Onsite" if re.search(r"\b(on[- ]?site|in[- ]office)\b", lowered) else ""
    allowed_modes = {item for item in (work_modes or []) if item in WORK_MODES}
    matchers = [token_matchers(token) for token in tokens]
    preferred_skills = set(profile_skills)
    ranked = []
    for job in jobs:
        if mode and job.get("mode") != mode:
            continue
        # Applied before the 60-result cap, so a profile's work mode is not lost to ranking.
        if allowed_modes and job.get("mode") not in allowed_modes and job.get("mode") not in UNLISTED_MODES:
            continue
        if not location_matches(job, locations):
            continue
        title = str(job.get("title", "")).lower()
        skills = " ".join(str(skill) for skill in (job.get("skills") or [])).lower()
        other = " ".join(str(job.get(key, "")) for key in ("company", "location", "description")).lower()
        # Weights: title 3, skills 2, other text 1.
        score = sum(3 if fields_hit(title, alts) else 2 if fields_hit(skills, alts) else 1 if fields_hit(other, alts) else 0 for alts in matchers)
        if tokens and score == 0:
            continue
        try:
            freshness = int(job.get("published", "0"))
        except (TypeError, ValueError):
            freshness = 0
        in_india = int(prefer_india and ("India" in job.get("eligible", []) or "india" in normalize_location(job.get("location", "")).split()))
        required = [str(skill).strip().lower() for skill in job.get("skills", [])]
        fit = sum(skill in preferred_skills for skill in required) / len(required) if required else 0.5
        ranked.append((score, fit if preferred_skills else 0, in_india, freshness, job))
    ranked.sort(key=lambda item: item[:4], reverse=True)
    return [job for *_, job in ranked[:60]]


def search_live_jobs(query: str, location_hint: str = "", work_modes: list[str] | None = None, profile_skills: tuple[str, ...] = ()) -> dict[str, object]:
    index = load_job_index()
    generated = str(index.get("generated_at", ""))
    return _search_live_jobs_cached(query, location_hint, tuple(work_modes or ()), generated, profile_skills)


@lru_cache(maxsize=256)
def _search_live_jobs_cached(query: str, location_hint: str, work_modes: tuple[str, ...], generated: str, profile_skills: tuple[str, ...]) -> dict[str, object]:
    del generated
    index = load_job_index()
    jobs = [job for job in index["jobs"] if isinstance(job, dict)]
    source_count = int(index.get("source_count", 0))
    successful = int(index.get("successful_sources", source_count))
    failed = index.get("failed_sources") or []
    source = {
        "name": f"{source_count} company career pages",
        "ok": bool(jobs),
        "count": len(jobs),
        "cached": True,
        "updated": str(index.get("generated_at", "")),
        "error": f"{len(failed)} sources were unavailable during the last refresh." if failed else "",
        "successful": successful,
    }
    return {"jobs": filter_live_jobs(jobs, query, location_hint, list(work_modes), profile_skills), "sources": [source]}


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
                if len(pdf.pages) > MAX_PDF_PAGES:
                    raise ValueError(f"The CV must be {MAX_PDF_PAGES} pages or fewer.")
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                return text, len(pdf.pages)
        except ValueError:
            raise
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
        "skills": re.compile(r"^(?:skills|technical skills|core skills|key skills|key competencies|core competencies|areas of expertise|technical expertise|technologies|tools and technologies|skills and tools)$", re.I),
        "achievements": re.compile(r"^(?:achievements?|key achievements|accomplishments|awards?|honors?|honours?)$", re.I),
        "certifications": re.compile(r"^(?:certifications?|certificates?|licenses and certifications|licences and certifications|licenses|licences)$", re.I),
        "languages": re.compile(r"^(?:languages|language skills|language proficiency|languages and proficiency)$", re.I),
        "preferences": re.compile(r"^(?:job preferences|employment preferences|career preferences|work preferences|preferences|job search preferences)$", re.I),
        "roles": re.compile(r"^(?:target roles|interested roles|roles of interest|target positions|positions of interest)$", re.I),
    }
    other_sections = re.compile(r"^(?:projects?|key projects?|documentation|key documentation|publications?|volunteering|volunteer experience|interests|hobbies|references|personal details|contact details|internships?|extracurricular activities)\s*:?$", re.I)
    for line in lines:
        candidate = line.strip(" \t•●|:-–—")
        section = next((key for key, pattern in section_headers.items() if pattern.match(candidate.rstrip(":"))), "")
        if section:
            current_section = section
            continue
        if other_sections.match(candidate):
            current_section = ""
            continue
        if current_section:
            sections[current_section].append(line.strip() if current_section in {"experience", "skills"} else candidate)

    def labeled_value(labels: str) -> str:
        match = re.search(rf"(?im)^\s*(?:{labels})\s*[:=–—-]\s*(.*?)\s*$", text)
        return match.group(1).strip(" \t|·-–—") if match else ""

    def cleaned_lines(values: list[str]) -> list[str]:
        return [re.sub(r"\s+", " ", value.strip(" \t•●*-–—▪◦")).strip() for value in values if value.strip(" \t•●*-–—▪◦")]

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
        clean = raw_line.strip(" \t•●*-–—▪◦")
        if not clean:
            continue
        is_bullet = bool(re.match(r"^\s*[•●*▪◦-]", raw_line))
        date_match = date_pattern.search(clean)
        without_dates = date_pattern.sub("", clean).strip(" ,;|·-–—")
        looks_like_role = bool(role_terms.search(without_dates)) and len(without_dates) <= 140
        separated = bool(re.search(r"\s+(?:at|@)\s+|\s*[|·—]\s*", without_dates, re.I))
        starts_experience = looks_like_role and not is_bullet and (bool(date_match) or separated)
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
                separator = "\n" if is_bullet and current_experience["detail"] else " "
                current_experience["detail"] = (current_experience["detail"] + separator + clean).strip()[:6000]

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

    raw_skill_lines = sections["skills"]
    structured_skills = any(re.match(r"^\s*[•●*▪◦-]", line) or ":" in line for line in raw_skill_lines)
    if structured_skills:
        skills = []
        for raw_line in raw_skill_lines:
            clean = re.sub(r"\s+", " ", raw_line.strip(" \t•●*-–—▪◦")).strip()
            if not clean:
                continue
            if re.match(r"^\s*[•●*▪◦-]", raw_line) or not skills:
                skills.append(clean)
            else:
                skills[-1] = f"{skills[-1]} {clean}"[:500]
        labeled_skills = labeled_value(r"(?:technical\s+)?skills?|key\s+competencies|core\s+competencies|technologies|tools")
        if labeled_skills:
            skills.extend(list_values([labeled_skills]))
    else:
        skills = list_values(raw_skill_lines + [value for value in [labeled_value(r"(?:technical\s+)?skills?|key\s+competencies|core\s+competencies|technologies|tools")] if value])
    for skill in SKILLS:
        if re.search(r"(?<![\w+#])" + re.escape(skill.lower()) + r"(?![\w+#])", normalized, re.I) and skill.lower() not in {value.lower() for value in skills}:
            skills.append(skill)
    if re.search(r"\bjs\b", normalized, re.I) and "JavaScript" not in skills:
        skills.append("JavaScript")
    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.I)
    phones = re.findall(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", text)
    email = first_nonempty(labeled_value(r"(?:email|e-mail|email\s+address)"), emails[0] if emails else "")
    phone = first_nonempty(labeled_value(r"(?:phone|telephone|mobile|mobile\s+number|contact\s+number)"), phones[0].strip() if phones else "")
    summary = first_nonempty(" ".join(cleaned_lines(sections["summary"])), labeled_value(r"(?:professional\s+)?(?:profile\s+)?summary|objective|about\s+me"))[:1200]
    education = "\n".join(cleaned_lines(sections["education"]))[:1200]
    if not education:
        education = labeled_value(r"(?:education|degree|qualification|highest\s+qualification)")[:1200]
    if not education:
        education = "\n".join(line.strip(" \t•●*-–—") for line in lines if re.search(r"\b(?:bachelor|master|ph\.?d|doctorate|diploma|degree|university|college|institute|school)\b", line, re.I))[:1200]

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
    cleaned = (cleaned.replace("\t", " ").replace("\u00a0", " ").replace("\u2022", "-").replace("\u25cf", "-")
               .replace("\u2013", "-").replace("\u2014", "-").replace("\u2192", "to"))
    return "".join(char if char in "\n" or _encodable(char) else "?" for char in cleaned)


def _encodable(char: str) -> bool:
    try:
        char.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def cv_download_filename(payload: dict[str, object]) -> str:
    version = payload.get("version") if isinstance(payload.get("version"), dict) else {}
    profile = version.get("profile") if isinstance(version.get("profile"), dict) else {}
    raw_name = str(profile.get("name", "")).strip() or "Candidate"
    ascii_name = unicodedata.normalize("NFKD", raw_name).encode("ascii", "ignore").decode("ascii")
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", ascii_name).strip("_")[:80] or "Candidate"
    return f"{safe_name}_CV.pdf"


def make_pdf(payload: dict[str, object]) -> bytes:
    """Build an ATS-friendly CV modeled on the supplied traditional single-column format."""
    try:
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError("PDF CV creation needs reportlab. Install it with: python -m pip install reportlab") from exc

    version = payload.get("version") if isinstance(payload.get("version"), dict) else {}
    profile = version.get("profile") if isinstance(version.get("profile"), dict) else {}
    name = pdf_safe(str(profile.get("name", "")).strip()) or "Candidate"
    headline = pdf_safe(str(profile.get("title", "")).strip())
    contact = " | ".join(pdf_safe(str(profile.get(key, "")).strip()) for key in ("location", "phone", "email") if str(profile.get(key, "")).strip())
    skills = version.get("skills") if isinstance(version.get("skills"), list) else []
    experiences = profile.get("experience") if isinstance(profile.get("experience"), list) else []
    achievements = profile.get("achievements") if isinstance(profile.get("achievements"), list) else []
    certifications = profile.get("certifications") if isinstance(profile.get("certifications"), list) else []

    base = ParagraphStyle("base", fontName="Times-Roman", fontSize=10.2, leading=12.6, alignment=TA_LEFT, textColor="#111111", spaceAfter=2)
    title = ParagraphStyle("title", parent=base, fontName="Times-Bold", fontSize=17, leading=20, spaceAfter=1)
    subtitle = ParagraphStyle("subtitle", parent=base, fontName="Times-Bold", fontSize=11, leading=14, spaceAfter=1)
    contact_style = ParagraphStyle("contact", parent=base, fontSize=9.5, leading=12, spaceAfter=2)
    heading = ParagraphStyle("heading", parent=base, fontName="Times-Bold", fontSize=11.2, leading=13.5, spaceBefore=9, spaceAfter=1)
    role_style = ParagraphStyle("role", parent=base, fontName="Times-Bold", fontSize=10.7, leading=13, spaceBefore=4, spaceAfter=1)
    bullet_style = ParagraphStyle("bullet", parent=base, leftIndent=12, firstLineIndent=-8, spaceAfter=1)

    def para(text: str, style) -> Paragraph:
        return Paragraph(escape(text).replace("\n", "<br/>"), style)

    story: list = [para(name, title)]
    if headline:
        story.append(para(headline, subtitle))
    if contact:
        story.append(para(contact, contact_style))

    def heading_block(label: str) -> None:
        story.append(para(label.upper(), heading))
        story.append(HRFlowable(width="100%", thickness=0.65, color="#111111", spaceBefore=0, spaceAfter=3))

    def bullet(text: object) -> Paragraph:
        return para(f"- {pdf_safe(str(text)).strip()}", bullet_style)

    def text_items(value: object) -> list[str]:
        if isinstance(value, list):
            return [pdf_safe(str(item)).strip(" -*\t") for item in value if str(item).strip(" -*\t")]
        return [pdf_safe(line).strip(" -*\t") for line in str(value or "").splitlines() if line.strip(" -*\t")]

    summary = pdf_safe(str(version.get("summary", ""))).strip()
    if summary:
        heading_block("Professional Summary")
        story.append(para(summary, base))

    skill_items = [pdf_safe(str(skill)).strip() for skill in skills if str(skill).strip()]
    if skill_items:
        heading_block("Key Competencies")
        grouped_skills = [item for item in skill_items if ":" in item]
        if grouped_skills:
            story.extend(bullet(item) for item in grouped_skills)
        else:
            story.append(para(" | ".join(skill_items), base))

    tailored_bullet = pdf_safe(str(version.get("bullet", ""))).strip()
    valid_experiences = [item for item in experiences if isinstance(item, dict) and any(str(value).strip() for value in item.values())]
    if valid_experiences or tailored_bullet:
        heading_block("Professional Experience")
        if valid_experiences:
            for index, experience in enumerate(valid_experiences):
                role = pdf_safe(str(experience.get("title", "")).strip())
                company = pdf_safe(str(experience.get("company", "")).strip())
                dates = pdf_safe(str(experience.get("dates", "")).strip())
                role_company = " - ".join(value for value in (role, company) if value)
                header = " | ".join(value for value in (role_company, dates) if value) or "Experience"
                details = tailored_bullet if index == version.get("experienceIndex", 0) and tailored_bullet else experience.get("detail", "")
                items = text_items(details)
                first = [para(header, role_style)]
                if items:
                    first.append(bullet(items[0]))
                story.append(KeepTogether(first))
                story.extend(bullet(item) for item in items[1:])
        else:
            story.extend(bullet(item) for item in text_items(tailored_bullet))

    education = pdf_safe(str(profile.get("education", ""))).strip()
    if education:
        heading_block("Education")
        story.extend(bullet(item) for item in text_items(education))

    if achievements:
        heading_block("Achievements")
        story.extend(bullet(item) for item in text_items(achievements))

    if certifications:
        heading_block("Certifications")
        story.extend(bullet(item) for item in text_items(certifications))

    languages = pdf_safe(str(profile.get("languages", ""))).strip()
    if languages:
        heading_block("Languages")
        story.append(para(languages, base))
    story.append(Spacer(1, 1 * mm))

    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=19 * mm, rightMargin=19 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
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
            if not self.allow_request("search", SEARCH_RATE_LIMIT, 60):
                self.send_json(429, {"error": "Too many searches. Wait a minute and try again."})
                return
            query = parse_qs(parsed.query).get("q", [""])[0][:240]
            location_hint = parse_qs(parsed.query).get("location", [""])[0][:180]
            work_modes = [item.strip() for item in parse_qs(parsed.query).get("modes", [""])[0][:60].split(",") if item.strip()]
            try:
                from urllib.parse import unquote
                values = json.loads(unquote(self.headers.get("X-Hireloom-Skills", "%5B%5D")[:8192]))
                if not isinstance(values, list):
                    raise ValueError("Expected a list of skills")
                skills = tuple(sorted({value.strip().lower() for value in values[:100] if isinstance(value, str)}))
                self.send_json(200, search_live_jobs(query, location_hint, work_modes, skills))
            except ValueError:
                self.send_json(400, {"error": "Invalid search preferences."})
            except Exception:
                self.send_json(502, {"error": "Company career pages could not be searched right now."})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        try:
            self.handle_post()
        except Exception:
            self.send_json(500, {"error": "Hireloom could not process this request. Please try again."})

    def handle_post(self) -> None:
        path = urlsplit(self.path).path
        if path in {"/api/render-cv", "/api/parse-cv", "/api/store-cv"} and not self.allow_request("cv", CV_RATE_LIMIT, CV_RATE_WINDOW_SECONDS):
            self.send_json(429, {"error": "Too many CV requests. Wait a minute and try again."})
            return
        if path == "/api/store-cv":
            self.store_cv()
            return
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

    def allow_request(self, scope: str, limit: int, window_seconds: int) -> bool:
        forwarded = self.headers.get("x-vercel-forwarded-for", "").split(",", 1)[0].strip() if os.environ.get("VERCEL") else ""
        client = f"{scope}:{forwarded or (self.client_address[0] if self.client_address else 'unknown')}"
        now = time.monotonic()
        with CV_RATE_LOCK:
            if len(CV_RATE_BUCKETS) >= 4096:
                for key in list(CV_RATE_BUCKETS):
                    if now - CV_RATE_BUCKETS[key][-1] >= 60:
                        del CV_RATE_BUCKETS[key]
                if client not in CV_RATE_BUCKETS and len(CV_RATE_BUCKETS) >= 4096:
                    return False
            recent = [stamp for stamp in CV_RATE_BUCKETS.get(client, []) if now - stamp < window_seconds]
            if len(recent) >= limit:
                CV_RATE_BUCKETS[client] = recent
                return False
            recent.append(now)
            CV_RATE_BUCKETS[client] = recent
            return True

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

    def store_cv(self) -> None:
        project = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not project.startswith("https://") or not key:
            self.send_json(503, {"error": "Private CV storage is not configured."})
            return
        bearer = self.headers.get("Authorization", "")
        if not bearer.startswith("Bearer "):
            self.send_json(401, {"error": "Sign in to store your CV."})
            return
        try:
            req = Request(project + "/auth/v1/user", headers={"apikey": key, "Authorization": bearer})
            with urlopen(req, timeout=5) as response:
                owner = UUID(json.load(response)["id"])
        except HTTPError as exc:
            if exc.code not in (401, 403):
                raise
            self.send_json(401, {"error": "Sign in again to store your CV."})
            return
        payload = self.read_body(MAX_FILE_BYTES, "The CV must be 1 MB or smaller.")
        if payload is None:
            return
        try:
            extract_document("cv.pdf", payload)
        except ValueError:
            self.send_json(422, {"error": "Choose a readable PDF of 30 pages or fewer."})
            return
        upload = Request(f"{project}/storage/v1/object/cvs/{owner}/cv.pdf", data=payload,
                         headers={"apikey": key, "Authorization": f"Bearer {key}",
                                  "Content-Type": "application/pdf", "x-upsert": "true"}, method="POST")
        with urlopen(upload, timeout=10):
            self.send_json(200, {"stored": True})

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
        self.send_header("Content-Disposition", f'attachment; filename="{cv_download_filename(payload)}"')
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

