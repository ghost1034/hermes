import os, requests
from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/bots/alpaca/.env'))
url = "https://data.alpaca.markets/v1beta1/screener/stocks/most-actives?by=volume&top=100"
headers = {'APCA-API-KEY-ID': os.environ.get('APCA_API_KEY_ID'), 'APCA-API-SECRET-KEY': os.environ.get('APCA_API_SECRET_KEY')}
print(requests.get(url, headers=headers).status_code)
