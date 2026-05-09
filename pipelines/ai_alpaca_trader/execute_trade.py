import os
import sys
import argparse
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

def execute_oco_trade(symbol, qty, limit_price, take_profit, stop_loss):
    env_path = os.environ.get('ENV_PATH', '~/bots/alpaca/.env')
    load_dotenv(os.path.expanduser(env_path))
    api = tradeapi.REST()
    
    try:
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side='buy',
            type='limit',
            time_in_force='gtc',
            limit_price=limit_price,
            order_class='bracket',
            take_profit={'limit_price': take_profit},
            stop_loss={'stop_price': stop_loss}
        )
        print(f"SUCCESS: Order placed for {qty} shares of {symbol}. ID: {order.id}")
    except Exception as e:
        print(f"ERROR: Failed to place order. Details: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute an OCO (One-Cancels-Other) trade via Alpaca API.")
    parser.add_argument('--symbol', required=True, help="Ticker symbol to trade (e.g., AAPL)")
    parser.add_argument('--qty', type=int, required=True, help="Quantity of shares to buy")
    parser.add_argument('--limit', type=float, required=True, help="Limit price for the buy order")
    parser.add_argument('--tp', type=float, required=True, help="Take profit limit price")
    parser.add_argument('--sl', type=float, required=True, help="Stop loss price")
    args = parser.parse_args()
    
    if args.qty <= 0:
        print("ERROR: Quantity must be greater than 0.")
        sys.exit(1)
        
    if args.limit <= 0 or args.tp <= 0 or args.sl <= 0:
        print("ERROR: Prices must be greater than 0.")
        sys.exit(1)
        
    execute_oco_trade(args.symbol, args.qty, args.limit, args.tp, args.sl)