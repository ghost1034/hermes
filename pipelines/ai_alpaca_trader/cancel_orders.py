import os
import sys
import argparse
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

def cancel_pending_orders(symbol):
    env_path = os.environ.get('ENV_PATH', '~/bots/alpaca/.env')
    load_dotenv(os.path.expanduser(env_path))
    
    try:
        api = tradeapi.REST()
        orders = api.list_orders(status='open')
        
        canceled_count = 0
        for order in orders:
            if order.symbol == symbol:
                api.cancel_order(order.id)
                print(f"Canceled order {order.id} for {symbol} ({order.side} {order.qty} @ {order.limit_price})")
                canceled_count += 1
                
        if canceled_count == 0:
            print(f"No pending orders found for {symbol}.")
        else:
            print(f"SUCCESS: Canceled {canceled_count} pending orders for {symbol}.")
            
    except Exception as e:
        print(f"ERROR: Failed to cancel orders for {symbol}. Details: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cancel all pending orders for a specific ticker symbol.")
    parser.add_argument('--symbol', required=True, type=str, help="Stock ticker symbol (e.g., AAPL)")
    args = parser.parse_args()
    
    cancel_pending_orders(args.symbol.upper())