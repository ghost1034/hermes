import os
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

def flatten_portfolio():
    load_dotenv(os.path.expanduser('~/bots/alpaca/.env'))
    api = tradeapi.REST()
    
    print("Cancelling all open orders...")
    try:
        api.cancel_all_orders()
        print("All open orders cancelled successfully.")
    except Exception as e:
        print(f"Error cancelling orders: {e}")
    
    print("\nFlattening all open positions...")
    try:
        positions = api.list_positions()
        if not positions:
            print("No open positions to flatten.")
        else:
            for p in positions:
                try:
                    api.close_position(p.symbol)
                    print(f"Submitted market order to close {p.qty} shares of {p.symbol}")
                except Exception as e:
                    print(f"Error closing position for {p.symbol}: {e}")
    except Exception as e:
        print(f"Error listing positions: {e}")
        
    print("\nPortfolio flattened for End of Day.")

if __name__ == "__main__":
    flatten_portfolio()