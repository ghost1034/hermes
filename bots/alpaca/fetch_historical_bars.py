import os
import csv
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("APCA_API_KEY_ID")
api_secret = os.getenv("APCA_API_SECRET_KEY")

client = StockHistoricalDataClient(api_key, api_secret)

symbols = ["SPY", "AAPL", "MSFT", "TSLA", "AMD", "NVDA"]
end_date = datetime.now() - timedelta(days=2) # go back more than 15 mins, maybe 2 days to avoid weekend issues
start_date = end_date - timedelta(days=5)

request_params = StockBarsRequest(
    symbol_or_symbols=symbols,
    timeframe=TimeFrame.Minute,
    start=start_date,
    end=end_date
)

bars = client.get_stock_bars(request_params)

with open("historical_bars.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["symbol", "timestamp", "open", "high", "low", "close", "volume"])
    for symbol, symbol_bars in bars.data.items():
        for bar in symbol_bars:
            writer.writerow([
                symbol,
                bar.timestamp.isoformat(),
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume
            ])

print("Downloaded historical_bars.csv")
