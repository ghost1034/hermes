import os
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/bots/alpaca/.env'))
api = tradeapi.REST()
orders = api.list_orders(status='all')
for o in orders[:10]:
    print(f"{o.symbol}: {o.side} {o.qty} at {o.limit_price} (Status: {o.status})")
