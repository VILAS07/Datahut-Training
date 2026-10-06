import asyncio
from playwright.async_api import async_playwright


KEYWORD_URLS = {
    # Dress
    "Mini dress": "https://shop.mango.com/in/en/search/women/q/mini+dress",
    "Midi dress": "https://shop.mango.com/in/en/search/women/q/midi+dress",
    "Maxi dress": "https://shop.mango.com/in/en/search/women/q/maxi+dress",
    "Summer dress": "https://shop.mango.com/in/en/search/women/q/summer+dress",
    "Knitted dress": "https://shop.mango.com/in/en/search/women/q/knitted+dress",

    # Jeans
    "Wide leg jeans": "https://shop.mango.com/in/en/search/women/q/wide+leg+jeans",
    "Straight leg jeans": "https://shop.mango.com/in/en/search/women/q/straight+leg+jeans",
    "Skinny jeans": "https://shop.mango.com/in/en/search/women/q/skinny+jeans",
    "Flared jeans": "https://shop.mango.com/in/en/search/women/q/flared+jeans",
    "High waist jeans": "https://shop.mango.com/in/en/search/women/q/high+waist+jeans",

    # Knitwear
    "Fine-knit jumper": "https://shop.mango.com/in/en/search/women/q/fine-knit+jumper",
    "Fine-knit cardigan": "https://shop.mango.com/in/en/search/women/q/fine-knit+cardigan",
    "Turtleneck jumper": "https://shop.mango.com/in/en/search/women/q/turtleneck+jumper",
    "Oversized jumper": "https://shop.mango.com/in/en/search/women/q/oversized+jumper",
    "Knitted top": "https://shop.mango.com/in/en/search/women/q/knitted+top",

    # Tops
    "Crop top": "https://shop.mango.com/in/en/search/women/q/crop+top",
    "Tank top": "https://shop.mango.com/in/en/search/women/q/tank+top",
    "Vest top": "https://shop.mango.com/in/en/search/women/q/vest+top",
    "Long sleeve top": "https://shop.mango.com/in/en/search/women/q/long+sleeve+top",
}


async def main():

    print("Launching Playwright...\n")

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page(
            viewport={
                "width": 1920,
                "height": 1080
            }
        )

        results = []

        for number, (keyword, url) in enumerate(
            KEYWORD_URLS.items(),
            start=1
        ):

            print("=" * 80)
            print(f"{number}. KEYWORD: {keyword}")
            print(f"URL: {url}")

            try:

                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=120000
                )

                await page.wait_for_timeout(3000)

                status = response.status if response else None
                final_url = page.url
                title = await page.title()

                body_text = await page.locator("body").inner_text()

                # Basic checks
                accessible = status is not None and status < 400

                has_content = len(body_text.strip()) > 100

                if accessible and has_content:
                    result = "ACCESSIBLE"
                else:
                    result = "FAILED"

                print(f"STATUS: {status}")
                print(f"FINAL URL: {final_url}")
                print(f"TITLE: {title}")
                print(f"RESULT: {result}")

                results.append({
                    "keyword": keyword,
                    "url": url,
                    "status": status,
                    "final_url": final_url,
                    "title": title,
                    "result": result
                })

            except Exception as e:

                print(f"RESULT: ERROR")
                print(f"ERROR: {e}")

                results.append({
                    "keyword": keyword,
                    "url": url,
                    "status": None,
                    "final_url": None,
                    "title": None,
                    "result": "ERROR"
                })

        await browser.close()

    print("\n")
    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    accessible_count = 0
    failed_count = 0
    error_count = 0

    for item in results:

        if item["result"] == "ACCESSIBLE":
            accessible_count += 1
            symbol = "✓"

        elif item["result"] == "FAILED":
            failed_count += 1
            symbol = "✗"

        else:
            error_count += 1
            symbol = "!"

        print(
            f"{symbol} {item['keyword']:<25} "
            f"{item['status']}  "
            f"{item['result']}"
        )

    print("\n")
    print(f"Total keywords : {len(results)}")
    print(f"Accessible     : {accessible_count}")
    print(f"Failed         : {failed_count}")
    print(f"Errors         : {error_count}")


if __name__ == "__main__":
    asyncio.run(main())