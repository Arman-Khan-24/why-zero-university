from pathlib import Path
from playwright.sync_api import sync_playwright
import base64
import json


ROOT = Path(__file__).parent
OUT = ROOT / "verification"
OUT.mkdir(exist_ok=True)


def run(viewport, name):
    missing = []
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--enable-webgl",
                "--ignore-gpu-blocklist",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
            ],
        )
        context = browser.new_context(viewport=viewport)
        page = context.new_page()
        page.on(
            "response",
            lambda response: missing.append({"status": response.status, "url": response.url})
            if response.status >= 400
            else None,
        )
        page.on("requestfailed", lambda request: missing.append({
            "status": "failed",
            "url": request.url,
            "error": request.failure,
        }))
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto("http://127.0.0.1:4173", wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(12000)
        labels = page.evaluate(
            """() => [...document.querySelectorAll('button[aria-label^="Go to stage"]')]
              .map(button => button.getAttribute('aria-label'))"""
        )
        cdp = context.new_cdp_session(page)
        for i in range(len(labels)):
            page.evaluate(
                """index => {
                  const button = document.querySelectorAll('button[aria-label^="Go to stage"]')[index];
                  button.disabled = false;
                  button.removeAttribute('disabled');
                  button.click();
                }""",
                i,
            )
            page.wait_for_timeout(2500)
        shot = cdp.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        (OUT / f"{name}.png").write_bytes(base64.b64decode(shot["data"]))
        result = {
            "title": page.title(),
            "labels": labels,
            "missing": missing,
            "errors": errors,
            "canvas": page.locator("#webgl").count(),
            "ui": page.locator("#ui-container").count(),
        }
        (OUT / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        browser.close()
        return result


desktop = run({"width": 1440, "height": 900}, "desktop")
mobile = run({"width": 390, "height": 844}, "mobile")
print(json.dumps({"desktop": desktop, "mobile": mobile}, indent=2))
