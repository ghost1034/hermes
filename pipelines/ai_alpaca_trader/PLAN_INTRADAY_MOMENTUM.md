# Intraday Momentum Screener Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace the daily top-gainers API with a custom 15-minute intraday momentum screener. The scanner will fetch active market tickers, calculate their price change over the last 15 minutes using intraday bars, and return the true high-momentum setups happening *right now*.

**Architecture:** Update `market_scanner.py` to use Alpaca's historical bar data (`api.get_bars`) to compare current prices against prices from exactly 15 minutes ago.

**Tech Stack:** Python 3, Alpaca Trade API v2, `pandas` (for easy bar processing if needed, or native python `datetime`).

---

### Task 1: Update Market Scanner Logic

**Objective:** Rewrite the momentum generation section of `market_scanner.py` to calculate true 15-minute intraday velocity.

**Files:**
- Modify: `~/pipelines/ai_alpaca_trader/market_scanner.py`

**Step 1: Write the updated implementation**

Use the `write_file` tool to overwrite `~/pipelines/ai_alpaca_trader/market_scanner.py` with the following code. *(Note: This uses a broad market snapshot to find active tickers, then calculates 15-minute momentum).*

```python
import os
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
        # Get active tradable assets
        assets = api.list_assets(status='active', asset_class='us_equity')
        tradable_symbols = [a.symbol for a in assets if a.tradable and a.fractionable and '.' not in a.symbol][:500] # Limit to 500 for API speed
        
        # Calculate time window (15 mins ago to now)
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(minutes=16)).isoformat()
        end_time = now.isoformat()
        
        # Fetch 1Min bars for the symbols
        bars = api.get_bars(tradable_symbols, tradeapi.rest.TimeFrame.Minute, start_time, end_time, adjustment='raw').df
        
        if bars.empty:
            print("No recent bar data available (Market likely closed).")
            return
            
        momentum_list = []
        # Group by symbol
        for symbol, group in bars.groupby('symbol'):
            if len(group) < 2:
                continue
            
            start_price = group.iloc[0]['c']
            end_price = group.iloc[-1]['c']
            
            # Apply our $10 price filter
            if end_price < 10.00:
                continue
                
            pct_change = ((end_price - start_price) / start_price) * 100
            volume = group['v'].sum()
            
            if pct_change > 0: # Only care about positive momentum
                momentum_list.append({
                    'symbol': symbol,
                    'start_price': start_price,
                    'current_price': end_price,
                    'pct_change': pct_change,
                    'volume': volume
                })
        
        # Sort by highest percentage change over the last 15 mins
        momentum_list.sort(key=lambda x: x['pct_change'], reverse=True)
        
        if not momentum_list:
            print("No momentum found in the last 15 minutes above $10.00.")
        else:
            for g in momentum_list[:5]:
                print(f"{g['symbol']}: ${g['current_price']:.2f} (+{g['pct_change']:.2f}% in 15m) | Vol: {g['volume']}")
                
    except Exception as e:
        print(f"Error calculating 15-minute momentum: {e}")

if __name__ == "__main__":
    get_market_context()
```

**Step 2: Run test to verify execution**

Run: `python3 ~/pipelines/ai_alpaca_trader/market_scanner.py`
Expected: Outputs Account Info, Open Positions, and a list of 5 stocks showing their specific `15m` momentum percentage and volume.

**Step 3: Commit**

```bash
cd ~/pipelines/ai_alpaca_trader
git add market_scanner.py
git commit -m "feat: upgrade scanner to calculate true 15-minute intraday momentum"
```

### Task 2: Refine the AI Prompt

**Objective:** Update the AI's system prompt so it understands the scanner output is now exactly a 15-minute window, allowing it to accurately web search for *immediate* catalysts.

**Files:**
- Modify: Cronjob via `cronjob` tool.

**Step 1: Execute the cronjob update**

Run the `cronjob` tool (`action='update'`) for `job_id` `4ebdf4413958`.

**Target Prompt Changes (Section 4):**
Update the research instruction to explicitly map to the new 15-minute data.

```text
4. NORMAL TRADING (Between 09:45 and 15:44 ET):
   - Read the strategy in /home/ianstewart/pipelines/ai_alpaca_trader/PLAYBOOK.md.
   - Run `python3 /home/ianstewart/pipelines/ai_alpaca_trader/market_scanner.py` via terminal. This now outputs TRUE 15-minute velocity.
   - Use web search to find immediate breaking news (published within the last hour) explaining WHY the top 2 momentum tickers just spiked.
   - If the catalyst is strong and supports the 15-minute breakout, execute a trade using `python3 /home/ianstewart/pipelines/ai_alpaca_trader/execute_trade.py` with the OCO bracket parameters.
```

(Ensure the rest of the prompt remains intact regarding time-checks, flattening, and the `[SILENT]` outputs).