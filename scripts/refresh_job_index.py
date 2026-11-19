"""Refresh Hireloom's searchable index from the fixed public company-board registry."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


REGISTRY_PATH = ROOT / "data" / "company_boards.json"
INDEX_PATH = ROOT / "data" / "jobs.json.gz"
BUNDLE_MANIFEST_PATH = ROOT / "data" / "job_index.json"
BUNDLE_SHARDS = 24
PROVIDER_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
}


def load_registry() -> list[dict[str, object]]:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    companies = payload.get("companies") if isinstance(payload, dict) else None
    if not isinstance(companies, list) or len(companies) != 300:
        raise ValueError("The company registry must contain exactly 300 sources.")
    keys = {(str(item.get("provider")), str(item.get("slug"))) for item in companies if isinstance(item, dict)}
    if len(keys) != len(companies):
        raise ValueError("The company registry contains an invalid or duplicate source.")
    return companies


def source_url(source: dict[str, object]) -> str:
    provider = str(source.get("provider", ""))
    template = PROVIDER_URLS.get(provider)
    if not template:
        raise ValueError(f"Unsupported provider: {provider}")
    return template.format(slug=quote(str(source.get("slug", "")), safe=".-_"))


def source_records(source: dict[str, object], payload: object) -> list[dict[str, object]]:
    provider = str(source.get("provider", ""))
    if provider in {"greenhouse", "ashby"}:
        records = payload.get("jobs") if isinstance(payload, dict) else None
    else:
        records = payload
    if not isinstance(records, list):
        raise ValueError("Unexpected job feed response.")
    return [record for record in records if isinstance(record, dict)]


def fetch_source(source: dict[str, object]) -> tuple[list[dict[str, object]], str]:
    for attempt in range(3):
        try:
            payload = server.fetch_json_value(source_url(source))
            jobs = [server.normalize_public_job(source, record) for record in source_records(source, payload)]
            return [job for job in jobs if job], ""
        except HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                return [], f"HTTPError: {exc.code}"
            error: Exception = exc
        except Exception as exc:
            error = exc
        if attempt < 2:
            time.sleep(attempt + 1)
    return [], f"{type(error).__name__}: {str(error)[:160]}"


def write_index(payload: dict[str, object], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix="jobs-", suffix=".json.gz", dir=destination.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as compressed:
                compressed.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def write_bundle(payload: dict[str, object], shard_count: int = BUNDLE_SHARDS) -> None:
    shards: list[list[dict[str, object]]] = [[] for _ in range(shard_count)]
    for job in payload["jobs"]:
        bucket = hashlib.sha256(str(job["id"]).encode("utf-8")).digest()[0] % shard_count
        shards[bucket].append(job)
    files = []
    for index, jobs in enumerate(shards):
        path = ROOT / "data" / f"jobs-{index:02d}.json.gz"
        write_index({"jobs": sorted(jobs, key=lambda item: str(item["id"]))}, path)
        files.append(path.name)
    manifest = {key: value for key, value in payload.items() if key != "jobs"}
    manifest["files"] = files
    BUNDLE_MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def refresh(destination: Path = INDEX_PATH, workers: int = 12, minimum_success: int = 270) -> dict[str, object]:
    companies = load_registry()
    results: list[tuple[list[dict[str, object]], str] | None] = [None] * len(companies)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_source, source): index for index, source in enumerate(companies)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    jobs: list[dict[str, object]] = []
    failures = []
    for source, result in zip(companies, results):
        source_jobs, error = result or ([], "No result returned")
        if error:
            failures.append({"company": source["company"], "provider": source["provider"], "slug": source["slug"], "error": error})
        else:
            jobs.extend(source_jobs)

    successful = len(companies) - len(failures)
    if successful < minimum_success:
        raise RuntimeError(f"Only {successful} of {len(companies)} company feeds succeeded. Existing index kept.")
    unique = {str(job["id"]): job for job in jobs}
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_count": len(companies),
        "successful_sources": successful,
        "failed_sources": failures,
        "job_count": len(unique),
        "jobs": list(unique.values()),
    }
    write_index(payload, destination)
    write_bundle(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=INDEX_PATH)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--minimum-success", type=int, default=270)
    args = parser.parse_args()
    payload = refresh(args.output, max(1, min(args.workers, 20)), args.minimum_success)
    print(json.dumps({key: payload[key] for key in ("generated_at", "source_count", "successful_sources", "job_count")}))
    if payload["failed_sources"]:
        print("Unavailable sources:", ", ".join(item["company"] for item in payload["failed_sources"]), file=sys.stderr)


if __name__ == "__main__":
    main()
