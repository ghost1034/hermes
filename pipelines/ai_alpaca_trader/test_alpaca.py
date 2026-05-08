import os
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/bots/alpaca/.env'))
api = tradeapi.REST()
try:
    movers = api.get_movers()
    print(movers)
except Exception as e:
    print(e)
