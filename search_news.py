import urllib.request
import json
import re

tickers = ["INOD", "RKLX", "FLNC", "PHOE", "POEL"]

for ticker in tickers:
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={ticker}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req)
        data = json.loads(response.read())
        news = data.get('news', [])
        print(f"--- {ticker} News ---")
        for item in news[:2]:
            print("-", item.get('title'))
    except Exception as e:
        print(f"Failed to fetch for {ticker}: {e}")

