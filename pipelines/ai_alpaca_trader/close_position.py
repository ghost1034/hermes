import os
import sys
import argparse
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

def close_single_position(symbol):
    load_dotenv(os.path.expanduser(os.environ.get('ENV_PATH', '~/bots/alpaca/.env')))
    
    try:
        api = tradeapi.REST()
        # Alpaca's close_position liquidates the asset and cancels linked open orders (like OCO brackets)
        order = api.close_position(symbol)
        print(f"SUCCESS: Position for {symbol} is being closed at market price.")
        print(f"Liquidation Order ID: {order.id}")
    except Exception as e:
        print(f"ERROR: Failed to close position for {symbol}. Details: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Close an open position and cancel its associated bracket orders.")
    parser.add_argument('--symbol', required=True, type=str, help="Stock ticker symbol to close (e.g., AAPL)")
    args = parser.parse_args()
    
    close_single_position(args.symbol.upper())
