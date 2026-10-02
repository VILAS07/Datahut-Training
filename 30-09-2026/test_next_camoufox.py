from camoufox.sync_api import Camoufox

url = "https://www.next.co.uk/style/sv030971/g38316"

with Camoufox(headless=False) as browser:
    page = browser.new_page()

    response = page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(5000)

    print("STATUS:", response.status if response else None)
    print("URL:", page.url)
    print("TITLE:", page.title())

    print("\nH1:")
    print(page.locator("h1").first.inner_text())

    print("\nMETA DESCRIPTION:")
    meta = page.locator('meta[name="description"]')
    print(meta.get_attribute("content") if meta.count() else "Not found")

    print("\nIMAGE COUNT:")
    print(page.locator("img").count())

    print("\nBODY TEXT AROUND PRODUCT:")
    text = page.locator("body").inner_text()

    product = "Cobalt Blue Short Sleeve Knit 2 in 1 Mini Dress"
    position = text.find(product)

    if position != -1:
        print(text[position:position + 3000])
    else:
        print("Product name not found in body text")

    browser.close()