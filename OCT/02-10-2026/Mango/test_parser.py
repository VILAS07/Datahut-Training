from parser import parse_product


with open("product.html", "r", encoding="utf-8") as f:
    html = f.read()


product = parse_product(
    html=html,
    keyword="mini dress",
    rank=1,
    pdp_url="https://www.next.co.uk/style/sv096115/v86064",
)


print("\n" + "=" * 70)
print("PARSED PRODUCT")
print("=" * 70)

for field, value in product.items():
    print(f"{field}: {value}")