from cloakbrowser import launch
from pathlib import Path

PDP_URL = "https://www.next.co.uk/style/sv096115/v86064"

OUTPUT = Path("product.html")


def main():

    browser = launch(headless=False)

    page = browser.new_page()

    print("Opening PDP...")
    response = page.goto(
        PDP_URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(5000)

    print("STATUS:", response.status if response else None)
    print("URL:", page.url)
    print("TITLE:", page.title())

    if not response or response.status != 200:
        print("PDP failed.")
        print(page.locator("body").inner_text()[:1000])
        browser.close()
        return

    # Get the fully rendered HTML
    html = page.content()

    OUTPUT.write_text(
        html,
        encoding="utf-8"
    )

    print()
    print("========== SAVED ==========")
    print("FILE:", OUTPUT.resolve())
    print("HTML SIZE:", len(html), "characters")

    browser.close()


if __name__ == "__main__":
    main()