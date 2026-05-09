# Fundamental Swing Trading Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Transition the AI Alpaca Trader from an intraday momentum bot to a fundamental-based swing trader. It will scan for undervalued stocks, enter positions using GTC bracket orders, and hold them across days or weeks.

**Architecture:** 
1. Rewrite `PLAYBOOK.md` to reflect fundamental rules.
2. Update `execute_trade.py` to use `gtc` instead of `day` time-in-force.
3. Replace the intraday scanner with a `fundamental_scanner.py` using `yfinance` to pull P/E, PEG, and Price-to-Book.
4. Provide instructions to update the AI Agent cronjob schedule to run once daily instead of every 15 minutes, removing the end-of-day flattening logic.

**Tech Stack:** Python 3, Alpaca Trade API v2, `yfinance`, `pandas`.

---

### Task 1: Update the Trading Playbook

**Objective:** Change the core strategy definition to Fundamental Swing Trading.

**Files:**
- Modify: `~/pipelines/ai_alpaca_trader/PLAYBOOK.md`

**Step 1: Write the updated implementation**
Use the `write_file` tool to overwrite `~/pipelines/ai_alpaca_trader/PLAYBOOK.md` with the following content:

```markdown
# AI Swing Trader Playbook

## Strategy: Fundamental Swing Trading
1. **Analyze:** Run `python3 ~/pipelines/ai_alpaca_trader/fundamental_scanner.py` to find stocks with strong fundamentals (e.g., low PEG ratio, reasonable P/E) that present good value.
2. **Contextualize:** Use web search to read recent earnings call summaries, analyst upgrades, and macro news for the top candidate tickers.
3. **Execute:** Buy using `execute_trade.py`. Hold duration is typically days to weeks.
4. **Risk Management:** Use GTC (Good 'Til Canceled) OCO brackets. Because this is swing trading, use wider targets: Take Profit at +10% to +15%, Stop Loss at -5% to -8%. Maximum 5 open positions concurrently. Only trade stocks priced at $10.00 or above.
5. **Monitoring:** Review positions daily. Do NOT flatten at the end of the day. Allow the bracket orders to manage exits, or manually intervene if fundamentals drastically change.
```

**Step 2: Commit**
```bash
cd ~/pipelines/ai_alpaca_trader
git add PLAYBOOK.md
git commit -m "docs: update playbook for fundamental swing trading"
```

### Task 2: Modify Order Execution for Swing Trading

**Objective:** Change the time-in-force on entry orders to Good 'Til Canceled (gtc) so bracket legs persist overnight.

**Files:**
- Modify: `~/pipelines/ai_alpaca_trader/execute_trade.py`

**Step 1: Update the script**
Use the `patch` tool on `~/pipelines/ai_alpaca_trader/execute_trade.py` to replace `time_in_force='day',` with `time_in_force='gtc',`.

**Step 2: Run a syntax check**
Run: `python3 -m py_compile ~/pipelines/ai_alpaca_trader/execute_trade.py`
Expected: No output (clean syntax).

**Step 3: Commit**
```bash
cd ~/pipelines/ai_alpaca_trader
git add execute_trade.py
git commit -m "fix: change time_in_force to gtc for swing trade brackets"
```

### Task 3: Create the Fundamental Scanner

**Objective:** Create a script that pulls fundamental metrics for a basket of stocks using `yfinance`.

**Files:**
- Create: `~/pipelines/ai_alpaca_trader/fundamental_scanner.py`

**Step 1: Install `yfinance`**
Run: `pip install yfinance`
Expected: Successful installation.

**Step 2: Write the scanner**
Use the `write_file` tool to create `~/pipelines/ai_alpaca_trader/fundamental_scanner.py` with:

```python
import yfinance as yf
import pandas as pd
import alpaca_trade_api as tradeapi
import os
from dotenv import load_dotenv

def get_portfolio():
    load_dotenv(os.path.expanduser('~/bots/alpaca/.env'))
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
            
            price = info.get('currentPrice', 0)
            pe = info.get('trailingPE', 0)
            fwd_pe = info.get('forwardPE', 0)
            peg = info.get('pegRatio', 0)
            pb = info.get('priceToBook', 0)
            
            if price < 10.0:
                continue
                
            results.append({
                'Symbol': ticker,
                'Price': price,
                'P/E': round(pe, 2) if pe else 'N/A',
                'Fwd P/E': round(fwd_pe, 2) if fwd_pe else 'N/A',
                'PEG': round(peg, 2) if peg else 'N/A',
                'P/B': round(pb, 2) if pb else 'N/A'
            })
        except Exception:
            continue
            
    df = pd.DataFrame(results)
    df_valid = df[df['PEG'] != 'N/A'].copy()
    df_valid['PEG'] = pd.to_numeric(df_valid['PEG'])
    df_sorted = df_valid[df_valid['PEG'] > 0].sort_values(by='PEG').head(5)
    
    print("Top 5 Fundamental Setups (Sorted by Lowest Positive PEG Ratio):")
    print(df_sorted.to_string(index=False))

if __name__ == "__main__":
    get_portfolio()
    scan_fundamentals()
```

**Step 3: Run test to verify execution**
Run: `python3 ~/pipelines/ai_alpaca_trader/fundamental_scanner.py`
Expected: Outputs Account Info, Open Positions, and a table of the top 5 stocks ranked by PEG ratio.

**Step 4: Commit**
```bash
cd ~/pipelines/ai_alpaca_trader
git add fundamental_scanner.py
git commit -m "feat: add yfinance fundamental scanner for swing trading"
```

### Task 4: Remove Obsolete Intraday Scripts

**Objective:** Clean up the intraday scripts so the bot doesn't mistakenly execute momentum logic or close swing positions.

**Files:**
- Modify: `~/pipelines/ai_alpaca_trader/flatten_positions.py`
- Modify: `~/pipelines/ai_alpaca_trader/market_scanner.py`

**Step 1: Remove the scripts**
Run: `rm ~/pipelines/ai_alpaca_trader/flatten_positions.py ~/pipelines/ai_alpaca_trader/market_scanner.py`

**Step 2: Commit**
```bash
cd ~/pipelines/ai_alpaca_trader
git rm flatten_positions.py market_scanner.py
git commit -m "refactor: remove intraday scanners and end-of-day flatten scripts"
```
