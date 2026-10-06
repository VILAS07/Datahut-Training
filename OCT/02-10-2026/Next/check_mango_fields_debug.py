from playwright.sync_api import sync_playwright

URL = "https://shop.mango.com/in/en/p/women/dresses-and-jumpsuits/party/ruched-dress-with-draped-neckline/37006011/05/00"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    print("Opening PDP...")
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    print("\n" + "=" * 80)
    print("MANGO FIELD DEBUG")
    print("=" * 80)

    # BODY
    body = page.locator("body").inner_text()

    print("\n--- SIZE / PRICE / MATERIAL RELATED TEXT ---\n")

    lines = body.splitlines()

    keywords = [
        "price",
        "£",
        "EUR",
        "size",
        "composition",
        "material",
        "fabric",
        "cotton",
        "polyester",
        "viscose",
        "elastane",
        "polyamide",
        "care",
    ]

    for i, line in enumerate(lines):
        line_lower = line.lower()

        if any(k in line_lower for k in keywords):
            start = max(0, i - 2)
            end = min(len(lines), i + 4)

            print(f"\n--- around line {i} ---")

            for x in range(start, end):
                print(lines[x])

    # META TAGS
    print("\n" + "=" * 80)
    print("ALL META TAGS")
    print("=" * 80)

    metas = page.locator("meta")

    for i in range(metas.count()):
        meta = metas.nth(i)

        name = meta.get_attribute("name")
        prop = meta.get_attribute("property")
        content = meta.get_attribute("content")

        if name or prop:
            print(
                f"name={name} | "
                f"property={prop} | "
                f"content={content}"
            )

    # BUTTONS
    print("\n" + "=" * 80)
    print("BUTTONS")
    print("=" * 80)

    buttons = page.locator("button")

    for i in range(buttons.count()):
        try:
            text = buttons.nth(i).inner_text().strip()

            if text:
                print(repr(text))
        except:
            pass

    browser.close()