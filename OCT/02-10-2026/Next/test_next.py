from playwright.sync_api import sync_playwright

url = "https://www.next.co.uk/search?w=mini%20dress"

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir="/tmp/next-chrome",
        headless=False,
        viewport={"width": 1366, "height": 768},
        locale="en-GB",
    )

    page = context.pages[0] if context.pages else context.new_page()

    print("Opening Next...")
    response = page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    print("STATUS:", response.status if response else "NO RESPONSE")
    print("URL:", page.url)
    print("TITLE:", page.title())

    page.wait_for_timeout(10000)

    print("BODY SIZE:", len(page.content()))

    input("Press ENTER to close...")

    context.close()