import unittest
from unittest.mock import patch

import server


class CareerSearchTests(unittest.TestCase):
    def test_employer_listing_is_normalized(self):
        posting = {"id": 42, "title": "Python Engineer", "location": {"name": "Bangalore"},
                   "absolute_url": "https://example.org/careers/42", "first_published": "2025-01-01T12:00:00Z",
                   "content": "&lt;p&gt;Build pipelines with Python and SQL.&lt;/p&gt;"}
        with patch.object(server, "fetch_json", return_value={"jobs": [posting, {}, None]}) as fetch:
            jobs = server.load_career_board("twilio")
        fetch.assert_called_once_with("https://boards-api.greenhouse.io/v1/boards/twilio/jobs?content=true")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["description"], "Build pipelines with Python and SQL.")
        self.assertEqual(jobs[0]["mode"], "Not listed")
        self.assertEqual(jobs[0]["id"], "twilio-42")
        self.assertEqual(server.filter_live_jobs(jobs, "Python in Bengaluru", "London"), jobs)
        self.assertEqual(server.filter_live_jobs(jobs, "Python", "London"), [])
        self.assertEqual(server.filter_live_jobs(jobs, "Python", "India"), jobs)

    def test_partial_outage_keeps_healthy_boards(self):
        with patch.object(server, "FEED_CACHE", {}), patch.object(server, "load_career_board") as fetch:
            def response(board):
                if board == "rubrik":
                    raise TimeoutError()
                return []
            fetch.side_effect = response
            result = server.search_live_jobs("developer")
            second = server.search_live_jobs("analyst")
            self.assertEqual(fetch.call_count, 3)
        self.assertEqual(result["jobs"], [])
        self.assertEqual([s["name"] for s in result["sources"] if not s["ok"]], ["Rubrik"])
        self.assertTrue(all(s["cached"] for s in second["sources"]))

    def test_pdf_export_and_parse_round_trip(self):
        pdf = server.make_pdf({"version": {"profile": {"name": "Test Candidate", "email": "test@example.org"},
                              "skills": ["Python", "SQL"], "summary": "Data engineer."}})
        result = server.parse_cv("candidate.pdf", pdf)
        self.assertEqual(result["email"], "test@example.org")
        self.assertIn("Python", result["skills"])
        self.assertEqual(result["pageCount"], 1)


if __name__ == "__main__":
    unittest.main()
