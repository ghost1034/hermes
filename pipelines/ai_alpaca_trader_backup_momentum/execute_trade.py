import os
import argparse
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

def execute_oco_trade(symbol, qty, limit_price, take_profit, stop_loss):
    load_dotenv(os.path.expanduser('~/bots/alpaca/.env'))
    api = tradeapi.REST()
    
    try:
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side='buy',
            type='limit',
            time_in_force='day',
            limit_price=limit_price,
            order_class='bracket',
            take_profit={'limit_price': take_profit},
            stop_loss={'stop_price': stop_loss}
        )
        print(f"SUCCESS: Order placed for {qty} shares of {symbol}. ID: {order.id}")
    except Exception as e:
        print(f"ERROR: Failed to place order. Details: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--qty', type=int, required=True)
    parser.add_argument('--limit', type=float, required=True)
    parser.add_argument('--tp', type=float, required=True)
    parser.add_argument('--sl', type=float, required=True)
    args = parser.parse_args()
    
    execute_oco_trade(args.symbol, args.qty, args.limit, args.tp, args.sl)