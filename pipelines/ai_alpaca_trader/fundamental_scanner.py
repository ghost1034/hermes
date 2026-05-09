import yfinance as yf
import pandas as pd
import alpaca_trade_api as tradeapi
import os
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
    # Basket of notable mid/large cap tickers to scan
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "AMD", "INTC", 
               "CRM", "ADBE", "PYPL", "SQ", "DIS", "NFLX", "UBER", "ABNB", "SPOT", "PLTR"]
    
    print("--- Fundamental Screener ---")
    print("Scanning basket for Value/Growth metrics (This takes a moment)...\n")
    
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
            print(f"Error fetching data for {ticker}: {e}")
            continue
            
    df = pd.DataFrame(results)
    if df.empty:
        print("No results found.")
        return
    df_valid = df[df['PEG'] != 'N/A'].copy()
    df_valid['PEG'] = pd.to_numeric(df_valid['PEG'])
    df_sorted = df_valid[df_valid['PEG'] > 0].sort_values(by='PEG').head(5)
    
    print("Top 5 Fundamental Setups (Sorted by Lowest Positive PEG Ratio):")
    print(df_sorted.to_string(index=False))

if __name__ == "__main__":
    get_portfolio()
    scan_fundamentals()
