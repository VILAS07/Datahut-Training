import subprocess
import re
from urllib.parse import quote

URLS = {
    "Mini dress": "https://www.next.co.uk/search?w=mini%20dress",
    "Midi dress": "https://www.next.co.uk/search?w=midi%20dress",
}

for keyword, url in URLS.items():

    print("\n" + "=" * 90)
    print(f"KEYWORD : {keyword}")
    print(f"URL     : {url}")
    print("=" * 90)

    cmd = [
        "curl",
        "-L",
        "--http2",
        "-sS",
        "-A",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: en-GB,en;q=0.9",
        "-H", "Cache-Control: no-cache",
        "-w", "\nCURL_STATUS:%{http_code}\nFINAL_URL:%{url_effective}\n",
        url
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30
    )

    output = result.stdout

    # Separate HTML from curl information
    status_match = re.search(r"CURL_STATUS:(\d+)", output)
    final_url_match = re.search(r"FINAL_URL:(.+)", output)

    status = status_match.group(1) if status_match else "UNKNOWN"
    final_url = final_url_match.group(1).strip() if final_url_match else "UNKNOWN"

    html = output

    # Remove curl metadata from HTML
    html = re.sub(r"\nCURL_STATUS:\d+\nFINAL_URL:.*$", "", html, flags=re.S)

    print("\nREQUEST")
    print("-" * 90)
    print("STATUS     :", status)
    print("FINAL URL  :", final_url)
    print("BODY SIZE  :", len(html))

    print("\nSECURITY CHECK")
    print("-" * 90)

    blocked_words = [
        "access denied",
        "edgesuite",
        "akamai",
        "you don't have permission"
    ]

    found = [
        word for word in blocked_words
        if word.lower() in html.lower()
    ]

    if found:
        print("BLOCKED    :", found)
    else:
        print("BLOCKED    : NO")

    print("\nPRODUCT CHECK")
    print("-" * 90)

    product_terms = [
        "product",
        "price",
        "£",
        "NEXT",
        "dress",
        "jeans",
        "jumper"
    ]

    found_products = [
        term for term in product_terms
        if term.lower() in html.lower()
    ]

    print("MATCHES    :", found_products)

    # Product links
    product_links = re.findall(
        r'href=["\']([^"\']+)["\']',
        html,
        flags=re.I
    )

    next_links = []

    for link in product_links:
        if "/p/" in link or "/product/" in link:
            if link not in next_links:
                next_links.append(link)

    print("\nPRODUCT LINKS")
    print("-" * 90)
    print("COUNT      :", len(next_links))

    for i, link in enumerate(next_links[:10], 1):
        if link.startswith("/"):
            link = "https://www.next.co.uk" + link

        print(f"{i}. {link}")

    print("\nHTML PREVIEW")
    print("-" * 90)
    print(html[:1000])