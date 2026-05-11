# Order Management & Visibility Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Improve visibility of tied-up capital by exposing pending orders in the scanner, create a tool to cancel stale orders, and update the AI playbook to use marketable limits and run daily order cleanup.

**Architecture:** 
- `fundamental_scanner.py` will query Alpaca's `list_orders(status='open')` and print the pending orders.
- A new script `cancel_orders.py` will iterate over open orders and cancel those matching a specific ticker.
- `PLAYBOOK.md` will be updated to instruct the AI trader on how to avoid missed fills (marketable limits) and clean up stale orders.

**Tech Stack:** Python 3, Alpaca Trade API (`alpaca_trade_api`), Markdown.

---

### Task 1: Add Pending Orders to `fundamental_scanner.py`

**Objective:** Expose open/pending orders in the daily scanner output so the AI knows why buying power is tied up.

**Files:**
- Modify: `~/pipelines/ai_alpaca_trader/fundamental_scanner.py`

**Step 1: Write implementation**

Modify `fundamental_scanner.py` in the `get_portfolio()` function. Right after printing `Open Positions`, add the logic to fetch and print open orders.

```python
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
                print(f"{o.symbol}: {o.side} {o.qty} @ limit {o.limit_price} (Class: {o.order_class})")
            print()
```

**Step 2: Verify execution**

Run: `python3 ~/pipelines/ai_alpaca_trader/fundamental_scanner.py`
Expected: Output should now include the `--- Pending/Open Orders ---` section, listing the pending MU, NVDA, and QCOM bracket limit orders.

**Step 3: Commit**

```bash
cd ~/pipelines/ai_alpaca_trader
git add fundamental_scanner.py
git commit -m "feat: add pending order visibility to fundamental scanner"
```

---

### Task 2: Create Order Cleanup Tool `cancel_orders.py`

**Objective:** Create a CLI tool to cancel specific pending orders by ticker symbol.

**Files:**
- Create: `~/pipelines/ai_alpaca_trader/cancel_orders.py`

**Step 1: Write minimal implementation**

Create the script `cancel_orders.py`.

```python
import os
import sys
import argparse
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

def cancel_pending_orders(symbol):
    env_path = os.environ.get('ENV_PATH', '~/bots/alpaca/.env')
    load_dotenv(os.path.expanduser(env_path))
    
    try:
        api = tradeapi.REST()
        orders = api.list_orders(status='open')
        
        canceled_count = 0
        for order in orders:
            if order.symbol == symbol:
                api.cancel_order(order.id)
                print(f"Canceled order {order.id} for {symbol} ({order.side} {order.qty} @ {order.limit_price})")
                canceled_count += 1
                
        if canceled_count == 0:
            print(f"No pending orders found for {symbol}.")
        else:
            print(f"SUCCESS: Canceled {canceled_count} pending orders for {symbol}.")
            
    except Exception as e:
        print(f"ERROR: Failed to cancel orders for {symbol}. Details: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cancel all pending orders for a specific ticker symbol.")
    parser.add_argument('--symbol', required=True, type=str, help="Stock ticker symbol (e.g., AAPL)")
    args = parser.parse_args()
    
    cancel_pending_orders(args.symbol.upper())
```

**Step 2: Verify execution**

Run: `python3 ~/pipelines/ai_alpaca_trader/cancel_orders.py --help`
Expected: Output shows the help text.

**Step 3: Commit**

```bash
cd ~/pipelines/ai_alpaca_trader
git add cancel_orders.py
git commit -m "feat: create cancel_orders tool for cleaning up stale limits"
```

---

### Task 3: Update `PLAYBOOK.md`

**Objective:** Instruct the AI to use marketable limits to ensure execution, and to clear out stale pending orders daily.

**Files:**
- Modify: `~/pipelines/ai_alpaca_trader/PLAYBOOK.md`

**Step 1: Update the markdown file**

Update the `PLAYBOOK.md` with the new rules.

```markdown
# AI Swing Trader Playbook

## Strategy: Fundamental Swing Trading
1. **Analyze:** Run `python3 ~/pipelines/ai_alpaca_trader/fundamental_scanner.py` to find stocks with strong fundamentals (e.g., low PEG ratio, reasonable P/E) that present good value. Review `Open Positions` and `Pending/Open Orders`.
2. **Order Cleanup:** If there are stale "Pending" entry orders from previous days that never filled, cancel them using `python3 ~/pipelines/ai_alpaca_trader/cancel_orders.py --symbol <TICKER>` to free up buying power.
3. **Contextualize:** Use web search to read recent earnings call summaries, analyst upgrades, and macro news for the top candidate tickers.
4. **Execute:** Buy using `python3 ~/pipelines/ai_alpaca_trader/execute_trade.py`. **Important:** To avoid missed fills on fast-moving stocks, calculate your entry Limit Price as a "Marketable Limit" with a slight premium (`Current Price * 1.002`). Hold duration is typically days to weeks.
5. **Risk Management:** Use GTC (Good 'Til Canceled) OCO brackets. Because this is swing trading, use wider targets: Take Profit at +10% to +15%, Stop Loss at -5% to -8%. Maximum 5 open positions concurrently. Only trade stocks priced at $10.00 or above.
6. **Monitoring:** Review positions daily. Do NOT flatten at the end of the day. Allow the bracket orders to manage exits, OR manually intervene if your news research shows fundamentals have drastically degraded. To manually exit a trade before it hits its bracket targets, run `python3 ~/pipelines/ai_alpaca_trader/close_position.py --symbol <TICKER>`.
```

**Step 2: Commit**

```bash
cd ~/pipelines/ai_alpaca_trader
git add PLAYBOOK.md
git commit -m "docs: update playbook with marketable limits and order cleanup rules"
```

---
