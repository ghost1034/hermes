import urllib.request
import re

url = "https://www.google.com/finance/markets/gainers"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    matches = re.findall(r'href="\./quote/([^:]+):([^"]+)"', html)
    print("Gainers:")
    for sym, exch in matches[:10]:
        print(sym)
except Exception as e:
    print(e)
