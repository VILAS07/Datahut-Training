class NextProductItem:

    def __init__(
        self,
        keyword="",
        product_name="",
        size="",
        product_description="",
        category="",
        product_type="",
        price="",
        main_image="",
        pdp_url="",
        rank="",
        colour="",
        gender="",
        material="",
        fit_sizing="",
        occasion_style="",
    ):
        self.keyword = keyword
        self.product_name = product_name
        self.size = size
        self.product_description = product_description
        self.category = category
        self.product_type = product_type
        self.price = price
        self.main_image = main_image
        self.pdp_url = pdp_url
        self.rank = rank
        self.colour = colour
        self.gender = gender
        self.material = material
        self.fit_sizing = fit_sizing
        self.occasion_style = occasion_style

    def to_dict(self):
        return {
            "keyword": self.keyword,
            "product_name": self.product_name,
            "size": self.size,
            "product_description": self.product_description,
            "category": self.category,
            "product_type": self.product_type,
            "price": self.price,
            "main_image": self.main_image,
            "pdp_url": self.pdp_url,
            "rank": self.rank,
            "colour": self.colour,
            "gender": self.gender,
            "material": self.material,
            "fit_sizing": self.fit_sizing,
            "occasion_style": self.occasion_style,
        }