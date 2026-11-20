import unittest
from pathlib import Path
from unittest.mock import patch

import server
from scripts import refresh_job_index


class CareerSearchTests(unittest.TestCase):
    def setUp(self):
        server._search_live_jobs_cached.cache_clear()

    def test_generic_non_technical_skills_are_detected(self):
        skills = server.known_skills("Experienced in patient care, payroll, procurement and food safety.")
        self.assertEqual(skills, ["Payroll", "Procurement", "Patient care", "Food safety"])

    def test_empty_feed_is_reported_as_a_failure(self):
        source = {"company": "Empty Co", "provider": "greenhouse", "slug": "empty"}
        with patch.object(server, "fetch_json_value", return_value={"jobs": []}), patch("scripts.refresh_job_index.time.sleep"):
            jobs, error = refresh_job_index.fetch_source(source)
        self.assertEqual(jobs, [])
        self.assertIn("no records", error.lower())

    def test_repeated_search_uses_cached_result(self):
        index = {"jobs": [], "source_count": 300, "successful_sources": 300,
                 "failed_sources": [], "generated_at": "cache-test"}
        with patch.object(server, "load_job_index", return_value=index) as load:
            server.search_live_jobs("accounting in india")
            server.search_live_jobs("accounting in india")
        self.assertEqual(load.call_count, 3)  # outer freshness checks plus one cached scan

    def test_contextual_locations(self):
        self.assertEqual(server.query_location_terms("help us build a global brand"), [])
        self.assertIn("us", server.query_location_terms("engineer in the US"))
        self.assertNotIn("Worldwide", server.eligibility_for("Globalization Office, Pune", False))

    def test_skill_after_preview(self):
        src = {"company":"Example", "slug":"example", "provider":"greenhouse", "careers_url":"https://example.org"}
        job = server.normalize_public_job(src, {"id":1, "title":"Engineer", "absolute_url":"https://example.org/job",
                                                "content":"Example work. " * 130 + "Python required."})
        self.assertIn("Python", job["skills"])
        self.assertLessEqual(len(job["description"]), 1200)

    def test_profile_fit_before_cap(self):
        jobs = [make_job(str(i), "Analyst", skills=["Excel"]) for i in range(70)]
        jobs.append(make_job("match", "Analyst", skills=["SQL"]))
        self.assertEqual(server.filter_live_jobs(jobs, "analyst", "India", [], ("sql",))[0]["id"], "match")

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
        self.assertGreaterEqual(index["successful_sources"], 270)
        self.assertEqual(len(index["jobs"]), index["job_count"])
        self.assertGreater(index["job_count"], 0)

    def test_pdf_export_and_parse_round_trip(self):
        pdf = server.make_pdf({"version": {"profile": {
            "name": "Test Candidate", "email": "test@example.org", "phone": "+91 90000 00000",
            "location": "Bengaluru, India", "title": "Data Engineer", "education": "B.Tech, Computer Science | 2021 - 2025",
            "experience": [{"title": "Data Engineer", "company": "Example Ltd", "dates": "2023 - Present",
                            "detail": "Built Python pipelines.\nImproved reporting quality."}],
            "achievements": ["Reduced processing time by 30%."], "certifications": ["AWS Fundamentals"],
            "languages": "English (Fluent), Hindi (Fluent)"},
            "skills": ["Python", "SQL"], "summary": "Data engineer.", "bullet": "Built reliable Python pipelines."}})
        result = server.parse_cv("candidate.pdf", pdf)
        text, _ = server.extract_document("candidate.pdf", pdf)
        self.assertEqual(result["email"], "test@example.org")
        self.assertIn("Python", result["skills"])
        self.assertEqual(result["pageCount"], 1)
        self.assertLess(text.index("PROFESSIONAL SUMMARY"), text.index("KEY COMPETENCIES"))
        self.assertLess(text.index("KEY COMPETENCIES"), text.index("PROFESSIONAL EXPERIENCE"))
        self.assertIn("Data Engineer - Example Ltd | 2023 - Present", text)
        self.assertIn("EDUCATION", text)
        self.assertIn("ACHIEVEMENTS", text)
        self.assertIn("CERTIFICATIONS", text)
        self.assertEqual(server.cv_download_filename({"version": {"profile": {"name": "Apurv Kumar"}}}), "Apurv_Kumar_CV.pdf")
        self.assertEqual(server.cv_download_filename({"version": {"profile": {"name": "../../"}}}), "Candidate_CV.pdf")



def make_job(job_id, title, mode="Remote", location="Bengaluru, India", description="", skills=()):
    return {"id": job_id, "title": title, "company": "Acme", "location": location, "mode": mode,
            "eligible": ["India"], "skills": list(skills), "description": description,
            "published": "2025-01-01", "languages": []}


class SearchRelevanceTests(unittest.TestCase):
    def ids(self, jobs, query, modes=None):
        return [job["id"] for job in server.filter_live_jobs(jobs, query, "India", modes)]

    def test_keywords_match_whole_words_only(self):
        jobs = [make_job("js", "JavaScript Engineer", description="Build with JavaScript"),
                make_job("java", "Java Developer"),
                make_job("analyst", "Data Analysts")]
        self.assertEqual(self.ids(jobs, "java"), ["java"])
        self.assertEqual(self.ids(jobs, "data analyst"), ["analyst"])

    def test_short_keyword_does_not_match_inside_other_words(self):
        jobs = [make_job("good", "Platform Engineer", description="Good communication skills"),
                make_job("go", "Go Developer")]
        self.assertEqual(self.ids(jobs, "go"), ["go"])

    def test_title_match_outranks_description_match(self):
        jobs = [make_job("desc", "Data Engineer", description="Python pipelines and Python tooling"),
                make_job("title", "Python Developer")]
        self.assertEqual(self.ids(jobs, "python"), ["title", "desc"])

    def test_synonym_matches_expanded_term_and_ml_ignores_html(self):
        jobs = [make_job("ml", "Machine Learning Engineer"), make_job("html", "HTML Developer")]
        self.assertEqual(self.ids(jobs, "ml"), ["ml"])

    def test_work_mode_filter_runs_before_result_cap(self):
        remote = [make_job(f"remote-{i}", "Python Engineer") for i in range(70)]
        hybrid = [make_job("hybrid", "Backend Platform Team", mode="Hybrid", description="Python services")]
        jobs = remote + hybrid
        self.assertEqual(len(self.ids(jobs, "python")), 60)
        self.assertNotIn("hybrid", self.ids(jobs, "python"))
        self.assertEqual(self.ids(jobs, "python", modes=["Hybrid"]), ["hybrid"])

    def test_unlisted_work_mode_is_kept_by_work_mode_filter(self):
        jobs = [make_job("unlisted", "Python Engineer", mode="Not listed")]
        self.assertEqual(self.ids(jobs, "python", modes=["Hybrid"]), ["unlisted"])

if __name__ == "__main__":
    unittest.main()
