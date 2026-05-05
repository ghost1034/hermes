import os
import sys
from collections import defaultdict
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

client = TradingClient(os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY"), paper=True)
orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100))

trades = defaultdict(list)
for o in orders:
    if o.filled_at:
        trades[o.symbol].append((o.side, o.filled_at, float(o.filled_avg_price)))

for sym, ords in trades.items():
    ords.sort(key=lambda x: x[1])
    for i in range(len(ords)-1):
        if ords[i][0] != ords[i+1][0]: # Opposite side
            diff = (ords[i+1][1] - ords[i][1]).total_seconds()
            print(f"{sym} trade duration: {diff} seconds. PnL approx {ords[i+1][2] - ords[i][2]:.4f}")

