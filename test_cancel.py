import os, alpaca_trade_api as tradeapi
from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/bots/alpaca/.env'))
api = tradeapi.REST()
orders = api.list_orders(status='open')
print("Open orders:")
for o in orders:
    print(o.symbol, o.side, o.qty, o.order_class)
