def extract_product_name(reviews_page, reviews_html_path):
    """Prefer the saved product page, then fall back to reviews HTML."""

    product_html_path = reviews_html_path.with_name(
        "amazon_airtag.html"
    )

    # Prefer the product page because its title is correctly formatted.
    if product_html_path.is_file():
        product_html = product_html_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        product_page = Selector(
            text=product_html,
            type="html",
        )

        product_name = joined_text(
            product_page,
            '//*[@id="productTitle"]//text()',
        )

        if product_name:
            return product_name

    # Fall back to the reviews page if needed.
    return (
        joined_text(
            reviews_page,
            '//*[@id="productTitle"]//text()',
        )
        or None
    )