import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from datetime import datetime
import pytz

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

ny_tz = pytz.timezone('America/New_York')
today = datetime.now(ny_tz).replace(hour=0, minute=0, second=0, microsecond=0)

req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500)
orders = client.get_orders(req)
today_orders = [o for o in orders if o.created_at.astimezone(ny_tz) >= today]

# Let's count entries by minute
from collections import Counter
counts = Counter()
symbols = set()
for o in today_orders:
    if o.status.value == "filled" or o.status.value == "accepted" or o.status.value == "new":
        t = o.created_at.astimezone(ny_tz).strftime('%H:%M')
        counts[t] += 1
        symbols.add(o.symbol)

print(f"Total today orders: {len(today_orders)}")
for k in sorted(counts.keys()):
    print(f"{k}: {counts[k]} orders")
print(f"Symbols traded: {len(symbols)}")
