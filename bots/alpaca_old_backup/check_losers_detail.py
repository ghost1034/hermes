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
syms = ['BMNR', 'NTLA', 'SMCI', 'KVUE', 'SOXL']

print("Detailed Timeline for Top 5 Losers:")
for sym in syms:
    print(f"\n--- {sym} ---")
    sym_orders = sorted([o for o in orders if o.symbol == sym and o.created_at.astimezone(ny_tz) >= today], key=lambda x: x.created_at)
    for o in sym_orders:
        filled_price = f"${float(o.filled_avg_price):.2f}" if o.filled_avg_price else "None"
        print(f"[{o.status.value.upper()}] {o.side.value.upper()} {o.qty} @ {filled_price} | Created: {o.created_at.astimezone(ny_tz).strftime('%H:%M:%S')} | Updated/Filled: {o.updated_at.astimezone(ny_tz).strftime('%H:%M:%S')}")
