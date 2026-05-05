import os
import sys

from pathlib import Path
env_path = Path(__file__).parent / ".env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        os.environ[key] = value.strip('"').strip("'")

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from datetime import datetime, timedelta
import pytz

API_KEY = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")
client = TradingClient(API_KEY, API_SECRET, paper=True)

account = client.get_account()
print(f"Equity: {account.equity}")
print(f"Today PnL: {float(account.equity) - float(account.last_equity)}")

ny_tz = pytz.timezone('America/New_York')
today = datetime.now(ny_tz).replace(hour=0, minute=0, second=0, microsecond=0)

req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100)
orders = client.get_orders(req)
print(f"Total orders fetched: {len(orders)}")
for o in orders:
    if o.created_at.astimezone(ny_tz) >= today:
        print(f"{o.created_at.astimezone(ny_tz).strftime('%H:%M:%S')} - {o.symbol} {o.side.value} {o.qty} @ {o.filled_avg_price} - {o.status.value}")
