import os
import pytz
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

from pathlib import Path
env_path = Path(__file__).parent / ".env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'): continue
        key, value = line.split('=', 1)
        os.environ[key] = value.strip('"').strip("'")

client = TradingClient(os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"], paper=True)
req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=20)
orders = client.get_orders(req)
ny_tz = pytz.timezone('America/New_York')

for o in orders:
    print(f"{o.created_at.astimezone(ny_tz).strftime('%H:%M:%S')} - {o.symbol} {o.side.value} {o.order_class.value} {o.type.value} - status: {o.status.value} - client_order_id: {o.client_order_id}")
