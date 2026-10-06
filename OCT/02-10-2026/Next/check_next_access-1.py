import requests
import subprocess
import re
import time

URLS = [
    ("Mini dress", "https://www.next.co.uk/search?w=mini%20dress"),
    ("Midi dress", "https://www.next.co.uk/search?w=midi%20dress"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


def check_requests(keyword, url):
    print("=" * 80)
    print(f"KEYWORD : {keyword}")
    print(f"URL     : {url}")
    print("=" * 80)

    try:
        start = time.time()

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
            allow_redirects=True
        )

        elapsed = time.time() - start

        print("\nREQUESTS CHECK")
        print("-" * 80)
        print(f"STATUS       : {response.status_code}")
        print(f"FINAL URL    : {response.url}")
        print(f"TIME         : {elapsed:.2f}s")
        print(f"SERVER       : {response.headers.get('server')}")
        print(f"CONTENT TYPE : {response.headers.get('content-type')}")

        security_patterns = [
            "cloudflare",
            "captcha",
            "incapsula",
            "perimeterx",
            "akamai",
            "access denied",
            "forbidden",
            "challenge",
            "rate limit",
            "bot detection",
            "security check",
        ]

        body_lower = response.text.lower()

        detected = [
            pattern
            for pattern in security_patterns
            if pattern in body_lower
        ]

        if detected:
            print(f"SECURITY     : DETECTED")
            print(f"MATCHES      : {detected}")
        else:
            print("SECURITY     : NO OBVIOUS BLOCK")

        print("\nBODY SIZE")
        print("-" * 80)
        print(f"Characters   : {len(response.text):,}")

        # Look for common product-related content
        product_words = [
            "dress",
            "£",
            "product",
            "shop",
            "women"
        ]

        found = [
            word for word in product_words
            if word.lower() in body_lower
        ]

        print(f"PRODUCT TERMS: {found}")

        return response.status_code == 200

    except Exception as e:
        print(f"REQUEST ERROR: {e}")
        return False


def check_curl(url):
    print("\nCURL CHECK")
    print("-" * 80)

    try:
        result = subprocess.run(
            [
                "curl",
                "-I",
                "-L",
                "--max-time",
                "30",
                "-A",
                HEADERS["User-Agent"],
                url
            ],
            capture_output=True,
            text=True
        )

        output = result.stdout + result.stderr

        print(output)

        status_codes = re.findall(
            r"HTTP/\S+\s+(\d+)",
            output
        )

        if status_codes:
            print(
                f"FINAL CURL STATUS: {status_codes[-1]}"
            )

    except Exception as e:
        print(f"CURL ERROR: {e}")


def main():
    requests_success = 0
    requests_failure = 0

    for keyword, url in URLS:

        success = check_requests(
            keyword,
            url
        )

        if success:
            requests_success += 1
        else:
            requests_failure += 1

        check_curl(url)

        time.sleep(2)

    total = requests_success + requests_failure

    success_rate = (
        requests_success / total * 100
        if total
        else 0
    )

    failure_rate = (
        requests_failure / total * 100
        if total
        else 0
    )

    print("\n")
    print("=" * 80)
    print("NEXT ACCESS SUMMARY")
    print("=" * 80)

    print("\nCrawler Blocking:")
    print(f"total_requests: {total}")
    print(f"success_rate_percent: {success_rate:.1f}")
    print(f"failure_rate_percent: {failure_rate:.1f}")


if __name__ == "__main__":
    main()