import unittest

import server


def job(company, title, description="", skills=(), mode="Remote", location="Bengaluru, India"):
    return {
        "id": company + title, "company": company, "title": title, "description": description,
        "skills": list(skills), "mode": mode, "location": location, "eligible": ["India"],
        "languages": ["English"], "published": "0", "years": "Not listed",
    }


class ExperienceParsingTests(unittest.TestCase):
    def test_prompt_years(self):
        self.assertEqual(server.query_years("Remote Python jobs, English, 2+ years experience"), 2)
        self.assertEqual(server.query_years("data engineer with 3-5 years of experience"), 5)
        self.assertEqual(server.query_years("with 4 years experience in SQL"), 4)
        self.assertIsNone(server.query_years("junior data analyst in Berlin"))
        self.assertIsNone(server.query_years("Python jobs posted in 2024"))

    def test_posting_requirements(self):
        self.assertEqual(server.job_years_required("Requires 5+ years of experience in Python."), 5)
        self.assertEqual(server.job_years_required("Minimum of 3 years of relevant experience."), 3)
        self.assertEqual(server.job_years_required("Ideal candidate with 3-5 years of experience."), 3)
        self.assertEqual(server.job_years_required("Experience: 4+ years building APIs."), 4)

    def test_company_history_is_not_a_requirement(self):
        self.assertIsNone(server.job_years_required("We have been in business for 25 years and won four years in a row."))
        self.assertIsNone(server.job_years_required("Join a team with no stated experience requirement."))

    def test_title_implied_years(self):
        self.assertEqual(server.title_years({"principal", "engineer"}), 8)
        self.assertEqual(server.title_years({"data", "engineer"}), 0)


class RoleIntentTests(unittest.TestCase):
    def test_head_noun_and_modifiers(self):
        intent = server.role_intent("junior data analyst")
        self.assertEqual(intent["family"], {"analyst", "analysts"})
        self.assertEqual(intent["modifiers"], ["data"])

    def test_synonym_modifier_and_experience_are_not_modifiers(self):
        intent = server.role_intent("ML engineer remote 3 years experience")
        self.assertIn("developer", intent["family"])
        self.assertEqual(intent["modifiers"], ["ml"])

    def test_location_is_not_a_modifier(self):
        self.assertEqual(server.role_intent("software engineer in Berlin")["modifiers"], ["software"])

    def test_no_role_word_means_no_title_gate(self):
        self.assertEqual(server.role_intent("Remote Python jobs"), {"family": set(), "modifiers": []})


class PromptFilterTests(unittest.TestCase):
    def setUp(self):
        server._search_live_jobs_cached.cache_clear()

    def search(self, jobs, query):
        return [item["company"] for item in server.filter_live_jobs(jobs, query, "India")]

    def test_role_word_must_be_in_title(self):
        jobs = [job("Acme", "Data Engineer"), job("Beta", "Data Analyst")]
        self.assertEqual(self.search(jobs, "data engineer"), ["Acme"])

    def test_junior_excludes_senior_and_staff_titles(self):
        jobs = [job("Acme", "Senior Data Analyst"), job("Beta", "Staff Data Analyst"), job("Gamma", "Data Analyst")]
        self.assertEqual(self.search(jobs, "junior data analyst"), ["Gamma"])

    def test_stated_requirement_above_candidate_is_excluded(self):
        jobs = [
            job("Acme", "Data Engineer", "Requires 5+ years of experience."),
            job("Beta", "Data Engineer", "Requires 1-3 years of experience."),
        ]
        self.assertEqual(self.search(jobs, "data engineer 2+ years experience"), ["Beta"])

    def test_one_year_over_is_kept_but_ranked_lower(self):
        jobs = [
            job("Acme", "Data Engineer", "Minimum of 3 years of experience."),
            job("Beta", "Data Engineer", "Build pipelines."),
        ]
        self.assertEqual(self.search(jobs, "data engineer 2 years experience"), ["Beta", "Acme"])

    def test_title_level_excluded_when_no_requirement_is_stated(self):
        jobs = [
            job("Acme", "Principal Data Engineer", "Own the platform."),
            job("Beta", "Senior Data Engineer", "Own the platform."),
            job("Gamma", "Data Engineer", "Own the platform."),
        ]
        self.assertEqual(self.search(jobs, "data engineer 2 years experience"), ["Gamma"])

    def test_title_level_kept_when_years_are_close(self):
        jobs = [job("Acme", "Senior Data Engineer", "Own the platform.")]
        self.assertEqual(self.search(jobs, "data engineer 4 years experience"), ["Acme"])

    def test_role_modifier_in_description_only_is_a_near_match(self):
        strict = [job(f"Co{i}", "Python Developer") for i in range(10)]
        near = job("Near", "Developer", "We use python daily.")
        self.assertNotIn("Near", self.search(strict + [near], "python developer"))

    def test_near_match_fills_in_when_strict_matches_are_few(self):
        strict = [job("Acme", "Python Developer")]
        near = job("Near", "Developer", "We use python daily.")
        self.assertEqual(self.search(strict + [near], "python developer"), ["Acme", "Near"])


class JobDetailTests(unittest.TestCase):
    def test_highlights_come_from_work_sentences_not_promotion(self):
        text = ("We are a fast-growing company with great culture. "
                "You will design and run batch data pipelines for analytics teams. "
                "Our values guide everything we do. "
                "You will own data quality checks across the warehouse.")
        self.assertEqual(server.posting_highlights(text), [
            "You will design and run batch data pipelines for analytics teams.",
            "You will own data quality checks across the warehouse.",
        ])

    def test_no_work_sentences_gives_no_highlights(self):
        self.assertEqual(server.posting_highlights("A friendly team in Berlin."), [])

    def test_fit_reason_uses_the_checks_that_ran(self):
        posting = job("Acme", "Data Engineer", "Requires 3+ years of experience.")
        reason = server.fit_reason(posting, "data engineer 2 years experience")
        self.assertIn("The title matches your role search.", reason)
        self.assertIn("The posting asks for 3+ years; your search says 2.", reason)
        self.assertIn("Remote role.", reason)


if __name__ == "__main__":
    unittest.main()
