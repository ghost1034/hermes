import os
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from datetime import datetime, timedelta
import pytz
from collections import defaultdict

from pathlib import Path
env_path = Path(__file__).parent / ".env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'): continue
        key, value = line.split('=', 1)
        os.environ[key] = value.strip('"').strip("'")

api_key = os.environ.get("APCA_API_KEY_ID")
api_secret = os.environ.get("APCA_API_SECRET_KEY")
trade_client = TradingClient(api_key, api_secret, paper=True)
data_client = StockHistoricalDataClient(api_key, api_secret)

ny_tz = pytz.timezone('America/New_York')
today = datetime.now(ny_tz).replace(hour=0, minute=0, second=0, microsecond=0)

req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500)
orders = trade_client.get_orders(req)
today_orders = [o for o in orders if o.created_at.astimezone(ny_tz) >= today and o.status.value == "filled"]

trades = defaultdict(list)
for o in today_orders: trades[o.symbol].append(o)

middle_syms = ['VZ', 'NU', 'AAPL', 'GOOGL', 'XLE']

for sym in middle_syms:
    if sym not in trades: continue
    sym_orders = sorted(trades[sym], key=lambda x: x.created_at)
    entry_order = sym_orders[0]
    exit_order = sym_orders[-1]
    
    is_long = entry_order.side.value == 'buy'
    entry_price = float(entry_order.filled_avg_price)
    entry_time = entry_order.created_at
    exit_time = exit_order.created_at
    
    request_params = StockBarsRequest(
        symbol_or_symbols=sym,
        timeframe=TimeFrame.Minute,
        start=entry_time,
        end=exit_time
    )
    bars = data_client.get_stock_bars(request_params)
    
    if sym in bars.data:
        high_price = max(b.high for b in bars.data[sym])
        low_price = min(b.low for b in bars.data[sym])
        
        if is_long:
            max_gain_pct = (high_price - entry_price) / entry_price * 100
            max_loss_pct = (entry_price - low_price) / entry_price * 100
            print(f"{sym} (LONG @ {entry_price:.2f}): Max Gain {max_gain_pct:.2f}% (Price: {high_price:.2f}), Max Loss {max_loss_pct:.2f}% (Price: {low_price:.2f})")
        else:
            max_gain_pct = (entry_price - low_price) / entry_price * 100
            max_loss_pct = (high_price - entry_price) / entry_price * 100
            print(f"{sym} (SHORT @ {entry_price:.2f}): Max Gain {max_gain_pct:.2f}% (Price: {low_price:.2f}), Max Loss {max_loss_pct:.2f}% (Price: {high_price:.2f})")
