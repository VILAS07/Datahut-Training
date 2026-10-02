import requests
from bs4 import BeautifulSoup

url = "https://www.next.co.uk/style/sv030971/g38316"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

text = soup.get_text(" ", strip=True)

fields = {
    "Product name": "Cobalt Blue Short Sleeve Knit 2 in 1 Mini Dress",
    "Price": "£45",
    "Product code": "G38-316",
    "Rating": "4.2",
    "Reviews": "13",
}

for field, value in fields.items():
    print(f"{field}: ", value in text)