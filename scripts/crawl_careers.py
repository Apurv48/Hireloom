"""Collect structured job postings from configured public career pages."""

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

import server


AGENT = "HireloomJobCrawler"
MAX_BYTES = 4 * 1024 * 1024
MAX_PAGES = 60


class CareerPage(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.documents = []
        self.script = None
        self.sections = {}
        self.capture = {}
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "script" and (attrs.get("type") or "").lower() == "application/ld+json":
            self.script = []
        classes = (attrs.get("class") or "").split()
        for field, marker in (("title", "job-title"), ("location", "job-post-location"), ("description", "job-post")):
            if marker in classes:
                self.sections[field] = []
                self.capture[tag] = field
        if tag in {"p", "br", "li", "div", "h2", "h3"}:
            for field in self.capture.values():
                self.sections[field].append(" ")

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        for field in self.capture.values():
            self.sections[field].append(data)

    def handle_endtag(self, tag):
        self.capture.pop(tag, None)
        if tag == "script" and self.script is not None:
            try:
                self.documents.append(json.loads("".join(self.script)))
            except (ValueError, RecursionError):
                pass
            self.script = None


def postings(document):
    pending = [document]
    while pending:
        node = pending.pop()
        if isinstance(node, list):
            pending.extend(reversed(node))
        elif isinstance(node, dict):
            types = node.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if isinstance(types, list) and any(
                kind in ("JobPosting", "https://schema.org/JobPosting", "http://schema.org/JobPosting")
                for kind in types
            ):
                yield node
            pending.extend(reversed(list(node.values())))


def many(value):
    return value if isinstance(value, list) else [value]


def normalize(source, posting, url):
    expiry = posting.get("validThrough")
    if isinstance(expiry, str):
        try:
            if len(expiry) == 10:
                expiry += "T23:59:59"
            end = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            if (end if end.tzinfo else end.replace(tzinfo=timezone.utc)) < datetime.now(timezone.utc):
                return None
        except ValueError:
            pass
    places = []
    for item in many(posting.get("jobLocation")):
        address = item.get("address") if isinstance(item, dict) else item
        if isinstance(address, dict):
            country = address.get("addressCountry")
            if isinstance(country, dict):
                country = country.get("name")
            parts = [address.get("addressLocality"), address.get("addressRegion"), country]
            address = ", ".join(part for part in parts if isinstance(part, str) and part)
        if isinstance(address, str) and address:
            places.append(address)
    for area in many(posting.get("applicantLocationRequirements")):
        if isinstance(area, dict) and isinstance(area.get("name"), str):
            places.append(area["name"])
    remote = "TELECOMMUTE" in many(posting.get("jobLocationType"))
    description = " ".join(posting[key] for key in ("description", "qualifications", "skills")
                           if isinstance(posting.get(key), str))
    identifier = posting.get("identifier")
    identifier = identifier.get("value") if isinstance(identifier, dict) else identifier
    identity = str(identifier) if isinstance(identifier, (str, int)) and identifier else url
    job = server.normalize_public_job({**source, "provider": "ashby"}, {
        "id": hashlib.sha256(identity.encode()).hexdigest()[:24],
        "title": posting.get("title") or posting.get("name"),
        "location": ", ".join(dict.fromkeys(places)),
        "jobUrl": url,
        "descriptionHtml": description,
        "publishedAt": posting.get("datePosted"),
        "isRemote": remote,
    })
    if job:
        job["id"] = job["id"].replace("ashby-", "career-html-", 1)
    return job


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def crawl(source):
    seed = source["careers_url"]
    origin = urlsplit(seed)
    if origin.scheme != "https" or not origin.hostname or origin.username or origin.password:
        raise ValueError("Career source must be a public HTTPS URL.")
    pattern = re.compile(source["job_path"])
    opener = build_opener(NoRedirect())
    last_request = None
    delay = 1

    def fetch(url):
        nonlocal last_request
        if last_request is not None:
            time.sleep(max(0, delay - (time.monotonic() - last_request)))
        last_request = time.monotonic()
        with opener.open(Request(url, headers={"User-Agent": AGENT}), timeout=5) as response:
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("Career page exceeded the download limit.")
            return data.decode(response.headers.get_content_charset() or "utf-8", errors="replace")

    robots = RobotFileParser()
    try:
        robots.parse(fetch(urlunsplit((origin.scheme, origin.netloc, "/robots.txt", "", ""))).splitlines())
    except HTTPError as exc:
        if exc.code not in (404, 410):
            raise
        robots.allow_all = True
    delay = max(delay, robots.crawl_delay(AGENT) or 0)
    rate = robots.request_rate(AGENT)
    if rate and rate.requests > 0:
        delay = max(delay, rate.seconds / rate.requests)
    deadline = time.monotonic() + 120

    def read(url):
        if not robots.can_fetch(AGENT, url):
            return None
        if time.monotonic() + delay > deadline:
            raise ValueError("Career crawl exceeded its time budget.")
        return CareerPage(fetch(url))

    landing = read(seed)
    if landing is None:
        raise ValueError("Career page is disallowed by robots.txt.")
    urls = {}
    for link in landing.links:
        parts = urlsplit(urljoin(seed, link))
        if (parts.scheme, parts.netloc) == (origin.scheme, origin.netloc) and pattern.fullmatch(parts.path):
            urls[urlunsplit(parts._replace(fragment=""))] = None

    jobs = {}

    def collect(page, page_url):
        for document in page.documents:
            for posting in postings(document):
                target = posting.get("url")
                url = urlsplit(urljoin(page_url, target)) if isinstance(target, str) else urlsplit(page_url)
                if (url.scheme, url.netloc) != (origin.scheme, origin.netloc) or not pattern.fullmatch(url.path):
                    if page_url == seed or not pattern.fullmatch(urlsplit(page_url).path):
                        continue
                    url = urlsplit(page_url)
                job = normalize(source, posting, urlunsplit(url._replace(fragment="")))
                if job:
                    jobs[job["id"]] = job

    collect(landing, seed)
    for url in list(urls)[:MAX_PAGES]:
        if url == seed:
            continue
        try:
            page = read(url)
        except HTTPError as exc:
            if exc.code in (404, 410):
                continue
            raise
        if page:
            count_before = len(jobs)
            collect(page, url)
            if (len(jobs) == count_before and source.get("html_adapter") == "mozilla"
                    and {"title", "description"} <= page.sections.keys()):
                fields = {key: "".join(parts).strip() for key, parts in page.sections.items()}
                job = normalize(source, {"title": fields["title"], "description": fields["description"],
                                         "jobLocation": fields.get("location"),
                                         "identifier": urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]}, url)
                if job:
                    jobs[job["id"]] = job
    return list(jobs.values())
