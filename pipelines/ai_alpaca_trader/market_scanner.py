import os
import requests
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

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

    print("\n--- Top Intraday Momentum (Last 15 Minutes) ---")
    try:
        # 1. Broad Net: Get today's top gainers
        API_KEY = os.environ.get('APCA_API_KEY_ID')
        API_SECRET = os.environ.get('APCA_API_SECRET_KEY')
        headers = {'APCA-API-KEY-ID': API_KEY, 'APCA-API-SECRET-KEY': API_SECRET}
        url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=50"
        
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Failed to fetch movers. HTTP {resp.status_code}")
            return
            
        gainers = resp.json().get('gainers', [])
        
        # 2. Filter initial list (No Penny Stocks, Warrants, or Rights)
        clean_symbols = []
        for g in gainers:
            sym = g['symbol']
            if '.' in sym or (len(sym) > 4 and sym.endswith('W')):
                continue
            if g.get('price', 0) < 10.00:
                continue
            clean_symbols.append(sym)
            
        if not clean_symbols:
            print("No valid gainers > $10 found.")
            return

        # 3. The 15-Minute Sniper: Fetch recent bars for these specific symbols
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(minutes=16)).isoformat()
        end_time = now.isoformat()
        
        bars = api.get_bars(clean_symbols, tradeapi.rest.TimeFrame.Minute, start_time, end_time, adjustment='raw', feed='iex').df
        
        if bars.empty:
            print("No recent bar data available (Market closed or no trades).")
            return
            
        momentum_list = []
        for symbol, group in bars.groupby('symbol'):
            if len(group) < 2:
                continue
            
            start_price = group.iloc[0]['close']
            end_price = group.iloc[-1]['close']
            
            pct_change = ((end_price - start_price) / start_price) * 100
            volume = int(group['volume'].sum())
            
            # We only want stocks that are actively pushing UP in the last 15 minutes
            if pct_change > 0:
                momentum_list.append({
                    'symbol': symbol,
                    'current_price': end_price,
                    'pct_change': pct_change,
                    'volume': volume
                })
                
        # Sort by 15m percentage change
        momentum_list.sort(key=lambda x: x['pct_change'], reverse=True)
        
        if not momentum_list:
            print("None of the daily gainers have positive momentum in the last 15 minutes.")
        else:
            for g in momentum_list[:5]:
                print(f"{g['symbol']}: ${g['current_price']:.2f} (+{g['pct_change']:.2f}% in 15m) | Vol: {g['volume']}")

    except Exception as e:
        print(f"Error calculating 15-minute momentum: {e}")

if __name__ == "__main__":
    get_market_context()