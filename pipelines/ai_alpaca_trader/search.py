import urllib.request
import json
import re

def search(query):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read().decode('utf-8')
    results = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    for i, r in enumerate(results[:5]):
        text = re.sub(r'<[^>]+>', '', r)
        print(f"{i+1}. {text.strip()}")

search("top stock market gainers today")
