import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from datetime import datetime
import pytz
from collections import defaultdict

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
today_orders = [o for o in orders if o.created_at.astimezone(ny_tz) >= today and o.status.value == "filled"]

trades = defaultdict(list)
for o in today_orders:
    trades[o.symbol].append(o)

pnl_by_symbol = {}
for symbol, sym_orders in trades.items():
    cash_flow = 0.0
    for o in sym_orders:
        if o.filled_avg_price and o.filled_qty:
            val = float(o.filled_avg_price) * float(o.filled_qty)
            if o.side.value == 'buy':
                cash_flow -= val
            else:
                cash_flow += val
    pnl_by_symbol[symbol] = cash_flow

sorted_pnl = sorted(pnl_by_symbol.items(), key=lambda x: x[1], reverse=True)

print("Top 5 Gainers:")
for symbol, pnl in sorted_pnl[:5]:
    sym_orders = sorted([o for o in today_orders if o.symbol == symbol], key=lambda x: x.created_at)
    print(f"\n--- {symbol}: ${pnl:.2f} ---")
    for o in sym_orders:
        print(f"[{o.updated_at.astimezone(ny_tz).strftime('%H:%M:%S')}] {o.side.value.upper()} {o.filled_qty} @ ${float(o.filled_avg_price):.2f} (Created: {o.created_at.astimezone(ny_tz).strftime('%H:%M:%S')})")
