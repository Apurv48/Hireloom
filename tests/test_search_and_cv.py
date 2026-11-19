import unittest
from pathlib import Path
from unittest.mock import patch

import server
from scripts import refresh_job_index


class CareerSearchTests(unittest.TestCase):
    def test_greenhouse_listing_is_normalized(self):
        source = {"company": "Twilio", "provider": "greenhouse", "slug": "twilio",
                  "careers_url": "https://job-boards.greenhouse.io/twilio"}
        posting = {"id": 42, "title": "Python Engineer", "location": {"name": "Bangalore"},
                   "absolute_url": "https://example.org/careers/42", "first_published": "2025-01-01T12:00:00Z",
                   "content": "&lt;p&gt;Build pipelines with Python and SQL.&lt;/p&gt;"}
        job = server.normalize_public_job(source, posting)
        self.assertEqual(job["description"], "Build pipelines with Python and SQL.")
        self.assertEqual(job["mode"], "Not listed")
        self.assertEqual(job["id"], "greenhouse-twilio-42")
        self.assertEqual(server.filter_live_jobs([job], "Python in Bengaluru", "London"), [job])
        self.assertEqual(server.filter_live_jobs([job], "Python", "London"), [])
        self.assertEqual(server.filter_live_jobs([job], "Python", "India"), [job])

    def test_ashby_listing_is_normalized(self):
        source = {"company": "Example Ashby", "provider": "ashby", "slug": "example",
                  "careers_url": "https://jobs.ashbyhq.com/example"}
        posting = {"id": "ashby-1", "title": "Data Analyst", "location": "Bengaluru, India",
                   "secondaryLocations": [{"location": "Remote - India"}], "isRemote": True,
                   "jobUrl": "https://jobs.ashbyhq.com/example/ashby-1", "publishedAt": "2026-11-18T00:00:00Z",
                   "descriptionPlain": "Build SQL dashboards."}
        job = server.normalize_public_job(source, posting)
        self.assertEqual(job["id"], "ashby-example-ashby-1")
        self.assertEqual(job["mode"], "Remote")
        self.assertIn("Remote - India", job["location"])
        self.assertEqual(job["skills"], ["SQL"])

    def test_lever_listing_is_normalized(self):
        source = {"company": "Example Lever", "provider": "lever", "slug": "example",
                  "careers_url": "https://jobs.lever.co/example"}
        posting = {"id": "lever-1", "text": "Frontend Engineer", "categories": {"location": "London"},
                   "hostedUrl": "https://jobs.lever.co/example/lever-1", "createdAt": 1794960000000,
                   "workplaceType": "hybrid", "descriptionPlain": "Build React applications."}
        job = server.normalize_public_job(source, posting)
        self.assertEqual(job["id"], "lever-example-lever-1")
        self.assertEqual(job["mode"], "Hybrid")
        self.assertEqual(job["location"], "London")
        self.assertEqual(job["skills"], ["React"])

    def test_search_uses_300_company_index(self):
        source = {"company": "Twilio", "provider": "greenhouse", "slug": "twilio",
                  "careers_url": "https://job-boards.greenhouse.io/twilio"}
        posting = {"id": 42, "title": "Python Engineer", "location": {"name": "Bengaluru"},
                   "absolute_url": "https://example.org/careers/42", "first_published": "2025-01-01T12:00:00Z"}
        job = server.normalize_public_job(source, posting)
        index = {"jobs": [job], "source_count": 300, "successful_sources": 298,
                 "failed_sources": [{"company": "Example"}], "generated_at": "2026-11-19T00:00:00Z"}
        with patch.object(server, "load_job_index", return_value=index):
            result = server.search_live_jobs("Python in Bengaluru")
        self.assertEqual(result["jobs"], [job])
        self.assertEqual(result["sources"][0]["name"], "300 company career pages")
        self.assertEqual(result["sources"][0]["successful"], 298)

    def test_registry_has_300_unique_sources(self):
        sources = refresh_job_index.load_registry()
        self.assertEqual(len(sources), 300)
        self.assertEqual(len({(source["provider"], source["slug"]) for source in sources}), 300)
        self.assertEqual({source["provider"] for source in sources}, {"greenhouse", "ashby", "lever"})

    def test_checked_in_index_is_complete(self):
        server._load_bundled_job_index.cache_clear()
        with patch.object(server, "JOB_INDEX_REMOTE_URL", ""), patch.object(server, "JOB_INDEX_PATH", Path("missing-index.gz")):
            index = server.load_job_index()
        self.assertEqual(index["source_count"], 300)
        self.assertEqual(index["successful_sources"], 300)
        self.assertEqual(len(index["jobs"]), index["job_count"])
        self.assertGreater(index["job_count"], 40_000)

    def test_pdf_export_and_parse_round_trip(self):
        pdf = server.make_pdf({"version": {"profile": {"name": "Test Candidate", "email": "test@example.org"},
                              "skills": ["Python", "SQL"], "summary": "Data engineer."}})
        result = server.parse_cv("candidate.pdf", pdf)
        self.assertEqual(result["email"], "test@example.org")
        self.assertIn("Python", result["skills"])
        self.assertEqual(result["pageCount"], 1)


if __name__ == "__main__":
    unittest.main()
