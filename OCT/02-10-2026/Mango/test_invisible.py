from invisible_playwright import InvisiblePlaywright

with InvisiblePlaywright() as browser:
    page = browser.new_page()

    response = page.goto(
        "https://www.next.co.uk",
        wait_until="domcontentloaded",
        timeout=30000,
    )

    print("HOME STATUS:", response.status if response else None)
    print("HOME TITLE:", page.title())

    page.wait_for_timeout(5000)

    # Find Next's search input
    search = page.locator(
        '[data-testid="header-search-bar-text-input"]'
    )

    print("SEARCH COUNT:", search.count())

    # Enter keyword
    search.fill("mini dress")

    print("SEARCH VALUE:", search.input_value())

    # Submit the normal Next search form
    search.press("Enter")

    page.wait_for_timeout(5000)

    print("\n==============================")
    print("SEARCH RESULT")
    print("==============================")
    print("URL:", page.url)
    print("TITLE:", page.title())

    body = page.locator("body").inner_text()
    print("BODY:")
    print(body[:1500])