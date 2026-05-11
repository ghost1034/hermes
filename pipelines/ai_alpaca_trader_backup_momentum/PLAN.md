# AI Alpaca Trader Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Transition from a standalone Python bot to an AI-driven trading system where the Hermes agent evaluates market conditions, reads news sentiment, and executes Alpaca trades autonomously to maximize profit.

**Architecture:** A cron-triggered AI prompt that reads market context via a Python script, analyzes news/sentiment using web tools, and executes trades via a dedicated execution script. All strategy files will reside in `~/pipelines/ai_alpaca_trader/`.

**Tech Stack:** Python 3, Alpaca Trade API v2, Hermes Cronjob Engine, Hermes web tools.

---

### Task 1: Create Strategy Directory and Playbook

**Objective:** Initialize the pipeline directory and define the AI's trading rules of engagement.

**Files:**
- Create: `~/pipelines/ai_alpaca_trader/PLAYBOOK.md`

**Step 1: Write minimal implementation**

Use the `write_file` tool to create `~/pipelines/ai_alpaca_trader/PLAYBOOK.md` with the following content:

```markdown
# AI Trader Playbook

## Strategy: Catalyst & Momentum
1. **Analyze:** Check `market_scanner.py` for portfolio status and top movers.
2. **Contextualize:** Use web search to evaluate news sentiment for the top 2 movers.
3. **Execute:** If sentiment aligns with momentum (bullish news + price up), buy using `execute_trade.py`.
4. **Risk Management:** Always use OCO brackets (Take Profit at +5%, Stop Loss at -2%). Maximum 2 open positions.
```

**Step 2: Commit**

```bash
cd ~/pipelines/ai_alpaca_trader
git init
git add PLAYBOOK.md
git commit -m "docs: add AI trader playbook"
```

### Task 2: Create Market Scanner Script

**Objective:** Build a script that the AI runs to get current buying power, open positions, and general market data.

**Files:**
- Create: `~/pipelines/ai_alpaca_trader/market_scanner.py`

**Step 1: Write minimal implementation**

Use `write_file` tool to create `~/pipelines/ai_alpaca_trader/market_scanner.py`:

```python
import os
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

if __name__ == "__main__":
    get_market_context()
```

**Step 2: Run test to verify functionality**

Run: `python3 ~/pipelines/ai_alpaca_trader/market_scanner.py`
Expected: Outputs account info and open positions.

**Step 3: Commit**

```bash
cd ~/pipelines/ai_alpaca_trader
git add market_scanner.py
git commit -m "feat: add market scanner for AI context"
```

### Task 3: Create Trade Execution Script

**Objective:** Build a robust, AI-callable script to execute OCO trades safely using the Alpaca v2 SDK rules.

**Files:**
- Create: `~/pipelines/ai_alpaca_trader/execute_trade.py`

**Step 1: Write minimal implementation**

Use `write_file` to create `~/pipelines/ai_alpaca_trader/execute_trade.py`:

```python
import os
import argparse
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

def execute_oco_trade(symbol, qty, limit_price, take_profit, stop_loss):
    load_dotenv(os.path.expanduser('~/bots/alpaca/.env'))
    api = tradeapi.REST()
    
    try:
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side='buy',
            type='limit',
            time_in_force='day',
            limit_price=limit_price,
            order_class='oco',
            take_profit={'limit_price': take_profit},
            stop_loss={'stop_price': stop_loss}
        )
        print(f"SUCCESS: Order placed for {qty} shares of {symbol}. ID: {order.id}")
    except Exception as e:
        print(f"ERROR: Failed to place order. Details: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--qty', type=int, required=True)
    parser.add_argument('--limit', type=float, required=True)
    parser.add_argument('--tp', type=float, required=True)
    parser.add_argument('--sl', type=float, required=True)
    args = parser.parse_args()
    
    execute_oco_trade(args.symbol, args.qty, args.limit, args.tp, args.sl)
```

**Step 2: Run test to verify failure/pass handling**

Run: `python3 ~/pipelines/ai_alpaca_trader/execute_trade.py --symbol AAPL --qty 1 --limit 150.0 --tp 160.0 --sl 145.0`
Expected: Submits order or returns API error (if market closed/insufficient funds), but outputs a clear SUCCESS/ERROR string.

**Step 3: Commit**

```bash
cd ~/pipelines/ai_alpaca_trader
git add execute_trade.py
git commit -m "feat: add robust OCO trade execution script"
```

### Task 4: Setup AI Cronjob

**Objective:** Schedule Hermes to act as the trader autonomously.

**Step 1: Create the cronjob**

Use the `cronjob` tool with `action='create'` to schedule the AI trader.

- **Schedule:** `0 10 * * 1-5` (Every weekday at 10:00 AM)
- **Prompt:**
  ```text
  You are the AI Stock Trader. 
  1. Read the strategy in ~/pipelines/ai_alpaca_trader/PLAYBOOK.md.
  2. Run `python3 ~/pipelines/ai_alpaca_trader/market_scanner.py` via terminal to get your portfolio status.
  3. Research the top 2 market movers today using web search.
  4. If a strong setup is found, execute a trade using `python3 ~/pipelines/ai_alpaca_trader/execute_trade.py` with appropriate OCO bracket parameters.
  5. Provide a summary of your trading actions and reasoning.
  ```

**Step 2: Verify creation**

Use `cronjob` tool with `action='list'` to verify the job is scheduled.