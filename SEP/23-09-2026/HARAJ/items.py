from dataclasses import dataclass, asdict


@dataclass
class PropertyItem:
    url: str = ""
    ad_id: str = ""

    title: str = ""
    city: str = ""
    district: str = ""
    seller: str = ""
    updated: str = ""

    description: str = ""

    price: str = ""
    currency: str = ""

    purpose: str = ""
    unit_price: str = ""

    property_type: str = ""
    property_age: str = ""
    area: str = ""
    rooms: str = ""
    facade: str = ""

    plan_number: str = ""
    plot_number: str = ""
    street_width: str = ""

    property_uses: str = ""
    services: str = ""
    guarantees: str = ""
    obligations: str = ""

    license_owner: str = ""
    license_expiry: str = ""

    advertiser_number: str = ""
    authorization_number: str = ""

    location_description: str = ""
    map_url: str = ""

    images: list[str] | None = None

    def __post_init__(self):
        if self.images is None:
            self.images = []

    def to_dict(self):
        return asdict(self)