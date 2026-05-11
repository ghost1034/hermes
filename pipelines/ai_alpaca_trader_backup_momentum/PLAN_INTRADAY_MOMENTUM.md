# Intraday Momentum Screener Plan (Hybrid Sniper)

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace the daily top-gainers API logic with a "Hybrid Sniper" 15-minute intraday momentum screener. The scanner will fetch the top 100 daily gainers, filter out penny stocks and warrants, and then query Alpaca's historical 1-minute bars to calculate exactly how those stocks performed *over the last 15 minutes*. This guarantees the AI only buys daily gainers that are actively surging right now, avoiding stocks that peaked hours ago and are fading.

**Architecture:** Update `market_scanner.py` to combine the REST `movers` API with `api.get_bars`.

**Tech Stack:** Python 3, Alpaca Trade API v2, `requests`, `pandas` (via Alpaca SDK).

---

### Task 1: Update Market Scanner Logic

**Objective:** Rewrite the momentum generation section of `market_scanner.py` to use the Hybrid Sniper approach.

**Files:**
- Modify: `~/pipelines/ai_alpaca_trader/market_scanner.py`

**Step 1: Write the updated implementation**

Use the `write_file` tool to overwrite `~/pipelines/ai_alpaca_trader/market_scanner.py` with the following code.

```python
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
        url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=100"
        
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
        
        bars = api.get_bars(clean_symbols, tradeapi.rest.TimeFrame.Minute, start_time, end_time, adjustment='raw').df
        
        if bars.empty:
            print("No recent bar data available (Market closed or no trades).")
            return
            
        momentum_list = []
        for symbol, group in bars.groupby('symbol'):
            if len(group) < 2:
                continue
            
            start_price = group.iloc[0]['c']
            end_price = group.iloc[-1]['c']
            
            pct_change = ((end_price - start_price) / start_price) * 100
            volume = group['v'].sum()
            
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
```

**Step 2: Run test to verify execution**

Run: `python3 ~/pipelines/ai_alpaca_trader/market_scanner.py`
Expected: Outputs Account Info, Open Positions, and a list of up to 5 stocks showing their specific `15m` momentum percentage and volume.

**Step 3: Commit**

```bash
cd ~/pipelines/ai_alpaca_trader
git add market_scanner.py
git commit -m "feat: upgrade scanner to hybrid 15-min sniper approach"
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
   - Run `python3 /home/ianstewart/pipelines/ai_alpaca_trader/market_scanner.py` via terminal. This now outputs TRUE 15-minute velocity on daily gainers.
   - Use web search to find immediate breaking news (published within the last hour) explaining WHY the top momentum tickers just spiked.
   - If the catalyst is strong and supports the 15-minute breakout, execute a trade using `python3 /home/ianstewart/pipelines/ai_alpaca_trader/execute_trade.py` with the OCO bracket parameters.
```

(Ensure the rest of the prompt remains intact regarding time-checks, flattening, and the `[SILENT]` outputs).