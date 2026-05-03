import os
from alpaca.trading.client import TradingClient

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

positions = client.get_all_positions()
print(f"Total open positions: {len(positions)}")
for p in positions:
    print(f"{p.symbol}: {p.qty} shares (PnL: {p.unrealized_pl})")
