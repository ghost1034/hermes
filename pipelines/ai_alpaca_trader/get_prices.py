import os
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/bots/alpaca/.env'))
api = tradeapi.REST()

for sym in ['IREN', 'INTC']:
    try:
        quote = api.get_latest_quote(sym)
        print(f"{sym} Price: ${quote.askprice}")
    except Exception as e:
        print(f"Error getting quote for {sym}: {e}")
