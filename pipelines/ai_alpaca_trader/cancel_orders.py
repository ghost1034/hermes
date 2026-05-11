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
        orders = api.list_orders(status='open', symbols=[symbol])
        
        canceled_count = 0
        for order in orders:
            # Safety check: do not cancel 'sell' orders (exit brackets) to avoid leaving positions unprotected
            if order.side == 'sell':
                print(f"Skipping sell order {order.id} for {symbol} (exit bracket). Use close_position.py to exit.")
                continue
                
            try:
                api.cancel_order(order.id)
                price_info = f" @ {order.limit_price}" if order.limit_price else ""
                print(f"Canceled order {order.id} for {symbol} ({order.side} {order.qty}{price_info})")
                canceled_count += 1
            except Exception as e:
                print(f"Warning: Failed to cancel order {order.id} for {symbol}: {e}")
                
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