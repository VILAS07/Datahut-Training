from camoufox.sync_api import Camoufox

url = "https://www.next.co.uk/search?w=mini%20dress"

with Camoufox(headless=False) as browser:
    page = browser.new_page()

    response = page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(5000)

    print("STATUS:", response.status if response else None)

    # Find links that point to Next product pages
    links = page.locator('a[href*="/style/"]')

    print("\nALL UNIQUE PRODUCT URLs:\n")

    seen = set()

    for i in range(links.count()):
        href = links.nth(i).get_attribute("href")

        if not href:
            continue

        # Remove fragment
        href = href.split("#")[0]

        # Only Next product URLs
        if "/style/" not in href:
            continue

        if href in seen:
            continue

        seen.add(href)

        print(f"{len(seen)}. {href}")

        if len(seen) >= 20:
            break

    browser.close()