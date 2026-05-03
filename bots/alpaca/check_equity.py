import os
from alpaca.trading.client import TradingClient
import pytz
from datetime import datetime

from pathlib import Path
env_path = Path(__file__).parent / ".env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        os.environ[key] = value.strip('"').strip("'")

client = TradingClient(os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY"), paper=True)
account = client.get_account()

print(f"Initial Margin: {account.initial_margin}")
print(f"Maintenance Margin: {account.maintenance_margin}")
print(f"Buying Power: {account.buying_power}")
print(f"Daytrading Buying Power: {account.daytrading_buying_power}")
print(f"Equity: {account.equity}")

# Get portfolio history
# The python client for Alpaca changed. It might be in another module. 
# Let's just try to fetch it via requests.
import requests
import json
headers = {
    "APCA-API-KEY-ID": os.environ.get("APCA_API_KEY_ID"),
    "APCA-API-SECRET-KEY": os.environ.get("APCA_API_SECRET_KEY")
}
url = "https://paper-api.alpaca.markets/v2/account/portfolio/history?period=1D&timeframe=1Min"
resp = requests.get(url, headers=headers)
data = resp.json()

equities = data.get("equity", [])
times = data.get("timestamp", [])
if equities:
    max_eq = max(equities)
    min_eq = min(equities)
    print(f"Max Equity: {max_eq} at {datetime.fromtimestamp(times[equities.index(max_eq)]).strftime('%H:%M:%S')}")
    print(f"Min Equity: {min_eq} at {datetime.fromtimestamp(times[equities.index(min_eq)]).strftime('%H:%M:%S')}")
