import yfinance as yf
import pandas as pd
import alpaca_trade_api as tradeapi
import os
import requests
import concurrent.futures
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Module level load_dotenv
load_dotenv(os.path.expanduser(os.environ.get('ENV_PATH', '~/bots/alpaca/.env')))

def get_portfolio() -> None:
    """
    Retrieves and prints the current Alpaca portfolio and open positions.
    """
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

        open_orders = api.list_orders(status='open')
        print("--- Pending/Open Orders ---")
        if not open_orders:
            print("None\n")
        else:
            for o in open_orders:
                price_str = f"limit {o.limit_price}" if o.limit_price else f"stop {o.stop_price}" if hasattr(o, 'stop_price') and o.stop_price else "market"
                print(f"{o.symbol}: {o.side} {o.qty} @ {price_str} (Class: {o.order_class})")
            print()
    except Exception as e:
        print(f"Could not load Alpaca portfolio: {e}\n")

def fetch_ticker_data(ticker: str, min_price: float) -> Optional[Dict[str, Any]]:
    """
    Fetches fundamental data for a single ticker using yfinance.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        price = info.get('currentPrice', None)
        pe = info.get('trailingPE', None)
        fwd_pe = info.get('forwardPE', None)
        peg = info.get('pegRatio', None)
        pb = info.get('priceToBook', None)
        
        if price is None or price < min_price:
            return None
            
        return {
            'Symbol': ticker,
            'Price': price,
            'P/E': round(pe, 2) if pe else 'N/A',
            'Fwd P/E': round(fwd_pe, 2) if fwd_pe else 'N/A',
            'PEG': round(peg, 2) if peg else 'N/A',
            'P/B': round(pb, 2) if pb else 'N/A'
        }
    except Exception:
        # Fail silently on individual tickers
        return None

def scan_fundamentals(top_n_actives: int = 100, max_tickers: int = 50, min_price: float = 10.0, top_setups: int = 5) -> pd.DataFrame:
    """
    Fetches most active stocks from Alpaca and screens them for fundamental value.
    Uses a thread pool to fetch yfinance data concurrently.
    
    Returns:
        pd.DataFrame: Top fundamental setups sorted by PEG ratio.
    """
    api_key = os.environ.get('APCA_API_KEY_ID')
    api_secret = os.environ.get('APCA_API_SECRET_KEY')
    
    if not api_key or not api_secret:
        print("Error: Alpaca API credentials not found in environment.")
        return pd.DataFrame()
        
    print("--- Fundamental Screener ---")
    print("Fetching most active stocks from Alpaca...")
    
    # Fetch most active stocks
    url = f"https://data.alpaca.markets/v1beta1/screener/stocks/most-actives?by=volume&top={top_n_actives}"
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
            if len(tickers) >= max_tickers:
                break
    except requests.exceptions.RequestException as e:
        print(f"Error fetching active tickers: {e}")
        return pd.DataFrame()

    print(f"Scanning {len(tickers)} active tickers for Value/Growth metrics (This takes a moment)...\n")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_ticker_data, ticker, min_price): ticker for ticker in tickers}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res is not None:
                results.append(res)
            
    df = pd.DataFrame(results)
    if df.empty:
        print("No results found matching fundamental criteria.")
        return pd.DataFrame()
        
    df_valid = df[df['PEG'] != 'N/A'].copy()
    if df_valid.empty:
        print("No stocks passed the PEG ratio filters.")
        return pd.DataFrame()
        
    df_valid['PEG'] = pd.to_numeric(df_valid['PEG'])
    df_sorted = df_valid[df_valid['PEG'] > 0].sort_values(by='PEG').head(top_setups)
    
    print(f"Top {top_setups} Fundamental Setups (Sorted by Lowest Positive PEG Ratio):")
    if df_sorted.empty:
        print("No stocks passed the PEG ratio filters.")
    else:
        print(df_sorted.to_string(index=False))
        
    return df_sorted

if __name__ == "__main__":
    get_portfolio()
    scan_fundamentals()