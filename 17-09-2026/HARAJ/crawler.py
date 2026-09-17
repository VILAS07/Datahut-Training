import re
import time

from playwright.sync_api import sync_playwright

from settings import (
    START_URL,
    HEADERS,
    OUTPUT_FILE
)

from parser import Parser
from export import export_to_csv


class Crawler:

    def __init__(self):

        self.parser = Parser()

        # -----------------------------------------------------
        # Global advertisement tracking
        # -----------------------------------------------------

        self.discovered_ids = set()

        self.parsed_ids = set()

        # Final dataset
        self.items = []

    # =========================================================
    # EXTRACT ADVERTISEMENT ID
    # =========================================================
    def extract_ad_id(self, url):

        if not url:
            return None

        match = re.search(
            r"haraj\.com\.sa/(?:en/)?(\d{7,})",
            url
        )

        if match:
            return match.group(1)

        return None

    # =========================================================
    # NORMALIZE ADVERTISEMENT URL
    # =========================================================
    def normalize_url(self, url):

        if not url:
            return None

        url = url.strip()

        url = url.split("?")[0]
        url = url.split("#")[0]

        match = re.search(
            r"haraj\.com\.sa/(?:en/)?(\d{7,})(?:/[^?#]*)?",
            url
        )

        if not match:
            return None

        ad_id = match.group(1)

        return (
            f"https://haraj.com.sa/en/"
            f"{ad_id}/"
        )

    # =========================================================
    # GET ADVERTISEMENT LINKS FROM CURRENT PAGE
    # =========================================================
    def get_listing_urls(self, page):

        try:

            links = page.locator("a").evaluate_all(
                """
                elements => elements
                    .map(a => a.href)
                    .filter(Boolean)
                """
            )

        except Exception as e:

            print(
                f"Error collecting advertisement links: {e}"
            )

            return {}

        urls = {}

        for link in links:

            ad_id = self.extract_ad_id(link)

            if not ad_id:
                continue

            normalized = self.normalize_url(link)

            if normalized:

                urls[ad_id] = normalized

        return urls

    # =========================================================
    # FIND A MAIN CATEGORY
    # =========================================================
    def find_category(self, page, category_name):

        print(
            f"\nSearching for category: "
            f"{category_name}"
        )

        # -----------------------------------------------------
        # First try exact text
        # -----------------------------------------------------

        selectors = [

            f"text={category_name}",

            f"a:has-text('{category_name}')",

            f"button:has-text('{category_name}')",

        ]

        for selector in selectors:

            try:

                locator = page.locator(selector)

                count = locator.count()

                if count == 0:
                    continue

                for i in range(count):

                    element = locator.nth(i)

                    try:

                        if not element.is_visible():
                            continue

                        text = (
                            element.inner_text()
                            .strip()
                        )

                        if category_name.lower() in text.lower():

                            print(
                                f"Found category: "
                                f"{text}"
                            )

                            return element

                    except Exception:

                        continue

            except Exception:

                continue

        return None

    # =========================================================
    # MOVE HORIZONTAL CATEGORY BAR
    # =========================================================
    def move_category_bar(self, page):

        print(
            "Searching horizontally for categories..."
        )

        # -----------------------------------------------------
        # We are NOT scrolling the page.
        #
        # We only move horizontally inside elements that
        # have horizontal overflow.
        # -----------------------------------------------------

        try:

            page.evaluate(
                """
                () => {

                    const elements =
                        Array.from(
                            document.querySelectorAll('*')
                        );

                    elements.forEach(el => {

                        if (
                            el.scrollWidth >
                            el.clientWidth
                        ) {

                            const style =
                                window.getComputedStyle(el);

                            if (
                                style.overflowX === 'auto' ||
                                style.overflowX === 'scroll'
                            ) {

                                el.scrollLeft =
                                    el.scrollWidth;
                            }
                        }

                    });

                }
                """
            )

            time.sleep(1)

        except Exception as e:

            print(
                f"Horizontal category movement error: "
                f"{e}"
            )

    # =========================================================
    # CLICK MAIN CATEGORY
    # =========================================================
    def click_category(
        self,
        page,
        category_name
    ):

        print(
            f"\n=========================================="
        )

        print(
            f"Selecting category: "
            f"{category_name}"
        )

        print(
            f"=========================================="
        )

        # -----------------------------------------------------
        # Try to find category first
        # -----------------------------------------------------

        category = self.find_category(
            page,
            category_name
        )

        # -----------------------------------------------------
        # If not visible, move horizontal category bar
        # -----------------------------------------------------

        if not category:

            self.move_category_bar(
                page
            )

            time.sleep(1)

            category = self.find_category(
                page,
                category_name
            )

        # -----------------------------------------------------
        # Category still not found
        # -----------------------------------------------------

        if not category:

            print(
                f"Category not found: "
                f"{category_name}"
            )

            return False

        # -----------------------------------------------------
        # Click
        # -----------------------------------------------------

        try:

            category.scroll_into_view_if_needed()

            time.sleep(1)

            category.click()

        except Exception as e:

            print(
                f"Could not click category "
                f"{category_name}: {e}"
            )

            return False

        # -----------------------------------------------------
        # Wait for category page/feed
        # -----------------------------------------------------

        print(
            f"Waiting for {category_name} page..."
        )

        time.sleep(4)

        print(
            f"{category_name} selected."
        )

        return True

    # =========================================================
    # PARSE NEW ADVERTISEMENTS
    # =========================================================
    def parse_new_urls(
        self,
        detail_page,
        urls,
        category_name
    ):

        new_urls = []

        for ad_id, url in urls.items():

            if ad_id in self.discovered_ids:

                continue

            self.discovered_ids.add(
                ad_id
            )

            new_urls.append(
                (ad_id, url)
            )

        if not new_urls:

            return 0

        print(
            "\n------------------------------------------"
        )

        print(
            f"Category: {category_name}"
        )

        print(
            f"New advertisements: "
            f"{len(new_urls)}"
        )

        print(
            "------------------------------------------"
        )

        for index, (ad_id, url) in enumerate(
            new_urls,
            start=1
        ):

            print(
                f"\nParsing property "
                f"{index}/{len(new_urls)}"
            )

            print(
                f"URL: {url}"
            )

            try:

                item = self.parser.parse(
                    detail_page,
                    url
                )

                if item:

                    # ------------------------------------------------
                    # Convert item to dictionary
                    # ------------------------------------------------

                    if hasattr(
                        item,
                        "to_dict"
                    ):

                        row = item.to_dict()

                    elif hasattr(
                        item,
                        "__dict__"
                    ):

                        row = item.__dict__.copy()

                    else:

                        row = dict(item)

                    # ------------------------------------------------
                    # ADD CATEGORY COLUMN
                    # ------------------------------------------------

                    row["category"] = category_name

                    # ------------------------------------------------
                    # Save
                    # ------------------------------------------------

                    self.items.append(
                        row
                    )

                    self.parsed_ids.add(
                        ad_id
                    )

                    print(
                        f"Parsed: "
                        f"{item.title}"
                    )

                    print(
                        f"Category: "
                        f"{category_name}"
                    )

                else:

                    print(
                        f"Parser returned no item: "
                        f"{ad_id}"
                    )

            except Exception as e:

                print(
                    f"Error parsing {url}: {e}"
                )

        return len(new_urls)

    # =========================================================
    # FIND SHOW MORE FOR ADVERTISEMENTS
    # =========================================================
    def find_show_more(self, page):

        selectors = [

            "button:has-text('Show More')",

            "button:has-text('Show more')",

            "text=Show More",

            "text=Show more",

        ]

        for selector in selectors:

            try:

                locator = page.locator(
                    selector
                )

                count = locator.count()

                if count == 0:
                    continue

                for i in range(count):

                    button = locator.nth(i)

                    try:

                        if button.is_visible():

                            return button

                    except Exception:

                        continue

            except Exception:

                continue

        return None

    # =========================================================
    # LOAD MORE ADVERTISEMENTS
    # =========================================================
    def load_more_ads(
        self,
        page,
        old_ids
    ):

        print(
            "\nLooking for Show More..."
        )

        button = self.find_show_more(
            page
        )

        if not button:

            print(
                "Show More not found."
            )

            return False

        print(
            "Show More found."
        )

        try:

            button.scroll_into_view_if_needed()

            time.sleep(1)

            button.click(
                timeout=10000
            )

        except Exception as e:

            print(
                f"Could not click Show More: "
                f"{e}"
            )

            return False

        print(
            "Waiting for more advertisements..."
        )

        # -----------------------------------------------------
        # Wait for DOM rebuild
        # -----------------------------------------------------

        for attempt in range(1, 16):

            time.sleep(2)

            print(
                f"Checking new advertisements "
                f"({attempt}/15)..."
            )

            current_urls = (
                self.get_listing_urls(
                    page
                )
            )

            current_ids = set(
                current_urls.keys()
            )

            print(
                f"Advertisements in DOM: "
                f"{len(current_ids)}"
            )

            new_ids = (
                current_ids - old_ids
            )

            if new_ids:

                print(
                    f"New advertisements found: "
                    f"{len(new_ids)}"
                )

                return True

        print(
            "No new advertisements found."
        )

        return False

    # =========================================================
    # SCRAPE ONE CATEGORY
    # =========================================================
    def scrape_category(
        self,
        main_page,
        detail_page,
        category_name
    ):

        # -----------------------------------------------------
        # Click category
        # -----------------------------------------------------

        success = self.click_category(
            main_page,
            category_name
        )

        if not success:

            return

        # -----------------------------------------------------
        # Category-specific IDs
        # -----------------------------------------------------

        category_ids = set()

        batch = 1

        no_new_batches = 0

        while True:

            print(
                "\n"
                "=========================================="
            )

            print(
                f"CATEGORY: {category_name}"
            )

            print(
                f"BATCH: {batch}"
            )

            print(
                "=========================================="
            )

            # -------------------------------------------------
            # Get current advertisements
            # -------------------------------------------------

            current_urls = (
                self.get_listing_urls(
                    main_page
                )
            )

            current_ids = set(
                current_urls.keys()
            )

            print(
                f"Advertisements currently found: "
                f"{len(current_ids)}"
            )

            # -------------------------------------------------
            # Find advertisements belonging to this category
            # -------------------------------------------------

            new_category_ids = (
                current_ids - category_ids
            )

            print(
                f"New advertisements in "
                f"{category_name}: "
                f"{len(new_category_ids)}"
            )

            # -------------------------------------------------
            # Parse
            # -------------------------------------------------

            if new_category_ids:

                self.parse_new_urls(
                    detail_page,
                    current_urls,
                    category_name
                )

                category_ids.update(
                    new_category_ids
                )

                no_new_batches = 0

            else:

                no_new_batches += 1

                print(
                    f"No-new-ad batch: "
                    f"{no_new_batches}"
                )

            # -------------------------------------------------
            # Try Show More
            # -------------------------------------------------

            old_ids = set(
                current_ids
            )

            more = self.load_more_ads(
                main_page,
                old_ids
            )

            if more:

                print(
                    "More advertisements loaded."
                )

                batch += 1

                continue

            # -------------------------------------------------
            # No more advertisements
            # -------------------------------------------------

            print(
                f"\nFinished category: "
                f"{category_name}"
            )

            print(
                f"Advertisements discovered in "
                f"category: "
                f"{len(category_ids)}"
            )

            break

        # -----------------------------------------------------
        # Go back to main page
        # -----------------------------------------------------

        print(
            f"\nReturning to main categories..."
        )

        try:

            main_page.goto(
                START_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            time.sleep(4)

        except Exception as e:

            print(
                f"Could not return to main page: "
                f"{e}"
            )

    # =========================================================
    # MAIN RUN
    # =========================================================
    def run(self):

        with sync_playwright() as p:

            # -------------------------------------------------
            # Browser
            # -------------------------------------------------

            browser = p.chromium.launch(
                headless=False
            )

            # -------------------------------------------------
            # Context
            # -------------------------------------------------

            context = browser.new_context(
                extra_http_headers=HEADERS,

                viewport={
                    "width": 1440,
                    "height": 900
                }
            )

            # -------------------------------------------------
            # Main page
            # -------------------------------------------------

            main_page = context.new_page()

            # -------------------------------------------------
            # Detail page
            # -------------------------------------------------

            detail_page = context.new_page()

            # -------------------------------------------------
            # Open MAIN START URL
            # -------------------------------------------------

            print(
                f"\nOpening main page:"
            )

            print(
                START_URL
            )

            main_page.goto(
                START_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            time.sleep(4)

            print(
                "\nMain page loaded."
            )

            # =================================================
            # CATEGORIES
            # =================================================

            categories = [
                "Tourism",
                "Food",
                "Coaching",
                "Games",
                "Jobs",
                "Animals",
                "Fashion",
                "Services",
            ]

            # -------------------------------------------------
            # Process each category
            # -------------------------------------------------

            for category_name in categories:

                self.scrape_category(
                    main_page,
                    detail_page,
                    category_name
                )

            # =================================================
            # FINAL RESULTS
            # =================================================

            print(
                "\n\n"
                "##################################################"
            )

            print(
                "ALL CATEGORIES FINISHED"
            )

            print(
                "##################################################"
            )

            print(
                f"\nTotal unique advertisements: "
                f"{len(self.discovered_ids)}"
            )

            print(
                f"Total parsed: "
                f"{len(self.parsed_ids)}"
            )

            failed = (
                self.discovered_ids
                - self.parsed_ids
            )

            print(
                f"Not parsed: "
                f"{len(failed)}"
            )

            # -------------------------------------------------
            # Export
            # -------------------------------------------------

            print(
                "\nExporting dataset..."
            )

            export_to_csv(
                self.items,
                OUTPUT_FILE
            )

            print(
                f"\nSaved dataset to:"
            )

            print(
                OUTPUT_FILE
            )

            # -------------------------------------------------
            # Close
            # -------------------------------------------------

            browser.close()


# =============================================================
# START
# =============================================================

if __name__ == "__main__":

    crawler = Crawler()

    crawler.run()