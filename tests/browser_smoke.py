"""Run with Playwright installed. Set HIRELOOM_BROWSER_CHANNEL=chrome to use local Chrome."""
import json
import os
import sys
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Handler, ThreadingHTTPServer


def main():
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=os.getenv("HIRELOOM_BROWSER_CHANNEL"))
            context = browser.new_context()
            context.route("**/config.js", lambda r: r.fulfill(content_type="text/javascript", body="window.HIRELOOM_SUPABASE={};"))
            context.route("https://cdn.jsdelivr.net/**", lambda r: r.abort())
            context.route("https://fonts.googleapis.com/**", lambda r: r.abort())
            context.route("**/careers/42", lambda r: r.fulfill(body="Employer application"))
            job = dict(id="twilio-42", title="Python Engineer", company="Twilio", location="Bengaluru",
                       mode="Remote", eligible=["India"], languages=[], source="Twilio", posted="Today",
                       sourceUrl="https://example.org/", url="https://example.org/careers/42", skills=["Python"],
                       years="Not listed", reason="Python role", description="Python role", highlights=[], match=65, isLive=True)
            context.route("**/api/search-jobs?**", lambda r: r.fulfill(content_type="application/json",
                          body=json.dumps({"jobs": [job], "sources": [{"name": "Twilio", "ok": True}]})))
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_default_timeout(7000)
            page.goto(f"http://127.0.0.1:{http.server_port}/", wait_until="domcontentloaded")
            action = lambda name: page.locator(f'[data-action="{name}"]').first.click()
            nav = lambda name: page.locator(f'button.nav-link[data-nav="{name}"]').click()

            def signup(name):
                action("show-signup")
                page.locator("#signup-name").fill(name)
                page.locator("#signup-email").fill(f"{name}@example.org")
                page.locator("#signup-password").fill("local-fixture-only")
                page.locator("#signup-confirm").fill("local-fixture-only")
                page.locator("[name=localConsent]").check()
                page.locator("#signup-form .login-submit").click()
                expect(page.locator("#search-query")).to_be_visible()

            def logout():
                action("toggle-menu")
                action("logout")
                action("confirm-logout")
                expect(page.locator("#login-form")).to_be_visible()

            signup("first")
            page.locator("#search-query").fill("Python in Bengaluru")
            page.locator("#search-query").press("Enter")
            expect(page.locator(".job-card")).to_have_count(1)
            action("edit-prompt")
            expect(page.locator("[data-action=save-prompt-edit]")).to_be_disabled()
            page.locator(".prompt-edit-input").fill("Remote Python in Bengaluru")
            action("save-prompt-edit")
            expect(page.locator(".conversation-turn")).to_have_count(1)
            page.locator("#search-query").fill("Only hybrid ones")
            with page.expect_request(lambda r: "/api/search-jobs?" in r.url) as followup:
                page.locator("#search-query").press("Enter")
            from urllib.parse import parse_qs, urlsplit
            query = parse_qs(urlsplit(followup.value.url).query)["q"][0].lower()
            assert all(term in query for term in ("python", "hybrid", "bengaluru")) and "remote" not in query
            expect(page.locator(".conversation-turn")).to_have_count(2)
            action("save-job")
            nav("saved")
            page.locator(".job-title-button").click()
            with page.expect_popup() as opened:
                action("track-listing")
            opened.value.close()
            action("external-answer")  # No
            nav("tracker")
            expect(page.locator(".status-pill")).to_have_text("Not applied")
            page.locator("[data-status-id]").select_option("Applied")
            page.locator(".table-job").click()
            with page.expect_popup() as reopened:
                action("track-listing")
            reopened.value.close()
            nav("tracker")
            expect(page.locator(".tracker-table tbody tr")).to_have_count(1)
            expect(page.locator(".status-pill")).to_have_text("Applied")
            action("delete-chat")
            action("confirm-delete-chat")
            logout()
            signup("second")
            nav("saved")
            expect(page.get_by_text("No saved jobs yet")).to_be_visible()
            nav("tracker")
            expect(page.locator("#tracker-count")).to_have_text("0")
            logout()
            page.reload()
            page.locator("#login-email").fill("first@example.org")
            page.locator("#login-password").fill("local-fixture-only")
            page.locator("#login-form .login-submit").click()
            nav("tracker")
            expect(page.locator(".status-pill")).to_have_text("Applied")
            nav("saved")
            expect(page.locator(".job-card")).to_have_count(1)
            page.set_viewport_size({"width": 375, "height": 800})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert not errors, errors
            browser.close()
            print("Browser flow passed: accounts, prompt edit, saved roles, application, history and mobile layout")
    finally:
        http.shutdown()
        http.server_close()


if __name__ == "__main__":
    main()
