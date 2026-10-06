from playwright.sync_api import sync_playwright

URL = "https://www.bayut.eg/en/egypt/properties-for-sale/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print(f"Opening: {URL}")

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(5000)

    current_url = page.url
    page_title = page.title()

    print(f"Current URL: {current_url}")
    print(f"Page title: {page_title}")

    if "captchaChallenge" in current_url:
        print("CAPTCHA detected: Bayut verification page")
        page.screenshot(path="captcha_detected.png")
        print("Screenshot saved to captcha_detected.png")

    elif "captcha" in page_title.lower():
        print("CAPTCHA detected from page title")

    else:
        print("No CAPTCHA detected")

    browser.close()