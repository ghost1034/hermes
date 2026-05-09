import yfinance as yf
import pandas as pd
import alpaca_trade_api as tradeapi
import os
import requests
from dotenv import load_dotenv

def get_portfolio():
    load_dotenv(os.path.expanduser(os.environ.get('ENV_PATH', '~/bots/alpaca/.env')))
    try:
        api = tradeapi.REST()
        account = api.get_account()
        print(f"--- Account Info ---")
        print(f"Buying Power: ${account.buying_power}")
        print(f"Portfolio Value: ${account.portfolio_value}\n")
        
        positions = api.list_positions()
        print("--- Open Positions ---")
        if not positions:
            print("None\n")
        else:
            for p in positions:
                print(f"{p.symbol}: {p.qty} shares @ ${p.avg_entry_price} (Current: ${p.current_price})")
            print()
    except Exception as e:
        print(f"Could not load Alpaca portfolio: {e}\n")

def scan_fundamentals():
    load_dotenv(os.path.expanduser(os.environ.get('ENV_PATH', '~/bots/alpaca/.env')))
    api_key = os.environ.get('APCA_API_KEY_ID')
    api_secret = os.environ.get('APCA_API_SECRET_KEY')
    
    print("--- Fundamental Screener ---")
    print("Fetching most active stocks from Alpaca...")
    
    # Fetch most active stocks
    url = "https://data.alpaca.markets/v1beta1/screener/stocks/most-actives?by=volume&top=100"
    headers = {'APCA-API-KEY-ID': api_key, 'APCA-API-SECRET-KEY': api_secret}
    
    tickers = []
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        most_actives = response.json().get('most_actives', [])
        
        for item in most_actives:
            sym = item['symbol']
            # Filter out warrants, rights, or preferred shares
            if '.' in sym or (len(sym) > 4 and sym.endswith('W')):
                continue
            tickers.append(sym)
            if len(tickers) >= 50: # Limit to top 50 to manage yfinance execution time
                break
    except Exception as e:
        print(f"Error fetching active tickers: {e}")
        return

    print(f"Scanning {len(tickers)} active tickers for Value/Growth metrics (This takes a moment)...\n")
    
    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            price = info.get('currentPrice', None)
            pe = info.get('trailingPE', None)
            fwd_pe = info.get('forwardPE', None)
            peg = info.get('pegRatio', None)
            pb = info.get('priceToBook', None)
            
            # $10 floor filter
            if price is None or price < 10.0:
                continue
                
            results.append({
                'Symbol': ticker,
                'Price': price,
                'P/E': round(pe, 2) if pe else 'N/A',
                'Fwd P/E': round(fwd_pe, 2) if fwd_pe else 'N/A',
                'PEG': round(peg, 2) if peg else 'N/A',
                'P/B': round(pb, 2) if pb else 'N/A'
            })
        except Exception as e:
            # yfinance often throws errors on volatile/new tickers; fail silently on individual tickers
            continue
            
    df = pd.DataFrame(results)
    if df.empty:
        print("No results found matching fundamental criteria.")
        return
        
    df_valid = df[df['PEG'] != 'N/A'].copy()
    df_valid['PEG'] = pd.to_numeric(df_valid['PEG'])
    df_sorted = df_valid[df_valid['PEG'] > 0].sort_values(by='PEG').head(5)
    
    print("Top 5 Fundamental Setups (Sorted by Lowest Positive PEG Ratio):")
    if df_sorted.empty:
        print("No stocks passed the PEG ratio filters.")
    else:
        print(df_sorted.to_string(index=False))

if __name__ == "__main__":
    get_portfolio()
    scan_fundamentals()