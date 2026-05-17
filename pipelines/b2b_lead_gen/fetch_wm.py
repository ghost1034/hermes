import urllib.request
import re
from bs4 import BeautifulSoup
import json

url = "https://watsonmcdonell.com"
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    
    print(f"Emails: {emails}")
    print(f"Snippet: {text[:2500]}")
except Exception as e:
    print(f"Error: {e}")
