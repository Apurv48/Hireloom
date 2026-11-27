import io
import json
import unittest
from email.message import Message
from unittest.mock import Mock, patch

from scripts import crawl_careers
from scripts import refresh_job_index
from scripts.refresh_job_index import fetch_source


class CareerCrawlerTest(unittest.TestCase):
    def test_indexes_public_postings_and_respects_robots_and_origin(self):
        seed = "https://careers.example.com/jobs"
        source = {"careers_url": seed, "company": "Example", "slug": "example",
                  "provider": "career-html", "job_path": r"/jobs/\d+"}
        posting = {"@type": ["JobPosting"], "title": "Engineer", "identifier": {"value": "1"},
                   "description": "a " * 800 + "<p>Python</p>", "jobLocationType": "TELECOMMUTE",
                   "applicantLocationRequirements": {"name": "India"}}
        pages = {
            "https://careers.example.com/robots.txt": "User-agent: *\nDisallow: /jobs/2\n",
            seed: '<a href="/jobs/1#job">Job</a><a href="/jobs/1">Duplicate</a>'
                  '<a href="/jobs/2">Disallowed</a><a href="https://other.example.com/jobs/3">External</a>',
            seed + "/1": '<script type="application/ld+json">' + json.dumps({
                "@graph": [posting, {**posting, "identifier": "expired", "validThrough": "2000-01-01"}]
            }) + "</script>",
        }

        def open_page(request, timeout):
            response = io.BytesIO(pages[request.full_url].encode())
            response.headers = Message()
            return response

        opener = Mock()
        opener.open.side_effect = open_page
        with patch.object(crawl_careers, "build_opener", return_value=opener), patch.object(crawl_careers.time, "sleep"):
            jobs, error = fetch_source(source)
        self.assertEqual(error, "")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["url"], seed + "/1")
        self.assertEqual(jobs[0]["mode"], "Remote")
        self.assertEqual(jobs[0]["location"], "India")
        self.assertIn("Python", jobs[0]["skills"])
        self.assertEqual(opener.open.call_count, 3)

    def test_release_refresh_skips_bundled_shards(self):
        with patch.object(refresh_job_index, "load_registry", return_value=[{}]), \
             patch.object(refresh_job_index, "fetch_source", return_value=([{"id": "test"}], "")), \
             patch.object(refresh_job_index, "write_index") as write_index, \
             patch.object(refresh_job_index, "write_bundle") as write_bundle:
            payload = refresh_job_index.refresh(minimum_success=1, release_only=True)
        self.assertEqual(payload["job_count"], 1)
        write_index.assert_called_once()
        write_bundle.assert_not_called()
