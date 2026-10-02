from playwright.sync_api import sync_playwright

url = "https://www.next.co.uk/style/sv030971/g38316"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    page = browser.new_page(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    )

    print("Opening Next PDP...")

    response = page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    print("HTTP status:", response.status if response else "No response")
    print("Final URL:", page.url)

    page.wait_for_timeout(5000)

    print("\nPAGE TITLE:")
    print(page.title())

    print("\nPAGE TEXT:")
    text = page.locator("body").inner_text()
    print(text[:5000])

    browser.close()