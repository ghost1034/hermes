import os
from dotenv import load_dotenv

# Set up env vars before importing daytrader
load_dotenv()
api_key = os.environ.get("APCA_API_KEY_ID", "")
api_secret = os.environ.get("APCA_API_SECRET_KEY", "")

import csv
import sys
from datetime import datetime, timedelta
import pytz
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockTradesRequest

from daytrader import get_dynamic_watchlist

def fetch_ticks(symbols, api_key, api_secret):

    client = StockHistoricalDataClient(api_key, api_secret)
    
    # Friday May 1, 2026 at 10:00 AM EDT to 10:15 AM EDT
    ny_tz = pytz.timezone('America/New_York')
    start = ny_tz.localize(datetime(2026, 5, 1, 10, 0, 0)).astimezone(pytz.utc)
    end = ny_tz.localize(datetime(2026, 5, 1, 10, 15, 0)).astimezone(pytz.utc)

    output_path = "historical_ticks.csv"
    
    total_ticks = 0
    with open(output_path, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "timestamp", "price", "size"])
        
        for symbol in symbols:
            try:
                req = StockTradesRequest(symbol_or_symbols=symbol, start=start, end=end)
                trades = client.get_stock_trades(req)
                
                if trades and trades.data and symbol in trades.data:
                    symbol_trades = trades.data[symbol]
                    total_ticks += len(symbol_trades)
                    for t in symbol_trades:
                        writer.writerow([symbol, t.timestamp.isoformat(), t.price, t.size])
            except Exception as e:
                print(f"Error fetching trades for {symbol}: {e}", file=sys.stderr)
                
    print(f"Fetched {total_ticks} ticks total.")

if __name__ == "__main__":
    api_key = os.environ.get("APCA_API_KEY_ID")
    api_secret = os.environ.get("APCA_API_SECRET_KEY")
    
    symbols = get_dynamic_watchlist(api_key, api_secret, target_count=50, min_price=10.0)
    if "SPY" not in symbols:
        symbols.append("SPY")
        
    print(f"Fetching ticks for {len(symbols)} dynamic symbols...")
    fetch_ticks(symbols, api_key, api_secret)
