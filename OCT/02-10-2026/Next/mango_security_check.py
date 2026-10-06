import requests

URL = "https://shop.mango.com/in/en/search/women/q/mini+dress"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}

print("=" * 80)
print("MANGO SECURITY / ACCESS CHECK")
print("=" * 80)

try:
    response = requests.get(
        URL,
        headers=headers,
        timeout=30,
        allow_redirects=True
    )

    print(f"STATUS CODE : {response.status_code}")
    print(f"FINAL URL  : {response.url}")
    print(f"TIME       : {response.elapsed.total_seconds():.2f}s")

    print("\n" + "-" * 80)
    print("IMPORTANT HEADERS")
    print("-" * 80)

    security_headers = [
        "Server",
        "Location",
        "Set-Cookie",
        "CF-Ray",
        "CF-Cache-Status",
        "CF-Mitigated",
        "X-Cache",
        "X-Served-By",
        "X-Request-ID",
        "X-Akamai-Transformed",
        "X-CDN",
    ]

    for header in security_headers:
        value = response.headers.get(header)

        if value:
            print(f"{header}: {value}")

    print("\n" + "-" * 80)
    print("SECURITY / BLOCKING CHECK")
    print("-" * 80)

    body = response.text.lower()

    security_signatures = {
        "Vercel": [
            "vercel security checkpoint",
            "security checkpoint",
        ],

        "Cloudflare": [
            "cloudflare",
            "cf-ray",
            "cf-mitigated",
            "checking your browser",
            "verify you are human",
        ],

        "CAPTCHA": [
            "captcha",
            "recaptcha",
            "hcaptcha",
        ],

        "Incapsula": [
            "incapsula",
            "_incap_ses",
            "visid_incap",
        ],

        "PerimeterX": [
            "perimeterx",
            "_px",
            "px-captcha",
        ],

        "Akamai": [
            "akamai",
            "ak_bmsc",
        ],

        "Access Block": [
            "access denied",
            "forbidden",
            "request blocked",
            "temporarily blocked",
            "too many requests",
        ],

        "Bot Protection": [
            "bot detection",
            "bot verification",
            "automated traffic",
            "unusual traffic",
        ],
    }

    detected = False

    for protection, signatures in security_signatures.items():
        matches = [
            signature
            for signature in signatures
            if signature in body or any(
                signature.lower() in str(v).lower()
                for v in response.headers.values()
            )
        ]

        if matches:
            detected = True
            print(f"⚠ {protection}: DETECTED")
            print(f"  Matches: {matches}")

    if not detected:
        print("✓ No obvious anti-bot/blocking signature detected")

    print("\n" + "-" * 80)
    print("RESPONSE PREVIEW")
    print("-" * 80)

    text = response.text[:500].replace("\n", " ")
    print(text)

except requests.exceptions.RequestException as e:
    print(f"ERROR: {e}")