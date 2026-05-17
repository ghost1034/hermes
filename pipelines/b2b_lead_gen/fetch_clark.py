import urllib.request
from bs4 import BeautifulSoup
import re

urls = [
    "https://clarknuber.com",
    "https://clarknuber.com/about-us/",
    "https://clarknuber.com/services/",
    "https://clarknuber.com/about/careers/",
    "https://clarknuber.com/insights/",
    "https://clarknuber.com/contact-us/"
]

for url in urls:
    print(f"Fetching {url}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        
        # get text
        text = soup.get_text(separator=' ', strip=True)
        emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
        
        print(f"Emails: {emails}")
        print(f"Content: {text[:2000]}")
        print("-" * 50)
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
