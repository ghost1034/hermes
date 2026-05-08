import os
import requests
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

def get_market_context():
    load_dotenv(os.path.expanduser('~/bots/alpaca/.env'))
    api = tradeapi.REST()
    
    account = api.get_account()
    print(f"--- Account Info ---")
    print(f"Buying Power: ${account.buying_power}")
    print(f"Portfolio Value: ${account.portfolio_value}")
    
    positions = api.list_positions()
    print("\n--- Open Positions ---")
    if not positions:
        print("None")
    for p in positions:
        print(f"{p.symbol}: {p.qty} shares @ ${p.avg_entry_price} (Current: ${p.current_price})")

    print("\n--- Top Market Gainers (Live Momentum) ---")
    API_KEY = os.environ.get('APCA_API_KEY_ID')
    API_SECRET = os.environ.get('APCA_API_SECRET_KEY')
    headers = {
        'APCA-API-KEY-ID': API_KEY,
        'APCA-API-SECRET-KEY': API_SECRET
    }
    # Fetch top 20 to allow room for filtering out warrants
    url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=20"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            gainers = data.get('gainers', [])
            
            clean_gainers = []
            for g in gainers:
                sym = g['symbol']
                # Filter out obvious warrants and rights (typically 5 letters ending in W, or containing '.')
                if '.' in sym or (len(sym) > 4 and sym.endswith('W')):
                    continue
                # Filter out penny stocks (under $10)
                if g.get('price', 0) < 10.00:
                    continue
                clean_gainers.append(g)
            
            # Display the top 5 clean gainers for the AI to research
            for g in clean_gainers[:5]:
                print(f"{g['symbol']}: ${g['price']} (+{g['percent_change']}%)")
        else:
            print(f"Failed to fetch movers. HTTP {response.status_code}")
    except Exception as e:
        print(f"Error fetching movers: {e}")

if __name__ == "__main__":
    get_market_context()