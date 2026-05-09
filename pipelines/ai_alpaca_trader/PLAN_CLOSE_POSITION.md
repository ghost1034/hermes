# Manual Position Exit Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Create a script (`close_position.py`) that allows the AI Swing Trader to manually exit a specific position and cancel its associated bracket orders, and update the playbook to document its usage.

**Architecture:** 
1. Create `close_position.py` using the Alpaca v2 SDK. The `api.close_position(symbol)` function natively liquidates the position at market price and automatically cancels any attached take-profit or stop-loss open orders.
2. Update `PLAYBOOK.md` to instruct the AI on exactly when and how to use this new capability.

**Tech Stack:** Python 3, Alpaca Trade API v2, `argparse`.

---

### Task 1: Create the Close Position Script

**Objective:** Write a Python script to liquidate a specific open position by symbol.

**Files:**
- Create: `~/pipelines/ai_alpaca_trader/close_position.py`

**Step 1: Write the implementation**
Use the `write_file` tool to create `~/pipelines/ai_alpaca_trader/close_position.py` with the following code:

```python
import os
import sys
import argparse
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

def close_single_position(symbol):
    load_dotenv(os.path.expanduser(os.environ.get('ENV_PATH', '~/bots/alpaca/.env')))
    
    try:
        api = tradeapi.REST()
        # Alpaca's close_position liquidates the asset and cancels linked open orders (like OCO brackets)
        order = api.close_position(symbol)
        print(f"SUCCESS: Position for {symbol} is being closed at market price.")
        print(f"Liquidation Order ID: {order.id}")
    except Exception as e:
        print(f"ERROR: Failed to close position for {symbol}. Details: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Close an open position and cancel its associated bracket orders.")
    parser.add_argument('--symbol', required=True, type=str, help="Stock ticker symbol to close (e.g., AAPL)")
    args = parser.parse_args()
    
    close_single_position(args.symbol.upper())
```

**Step 2: Run a syntax check**
Run: `python3 -m py_compile ~/pipelines/ai_alpaca_trader/close_position.py`
Expected: No output (clean syntax).

**Step 3: Commit**
```bash
cd ~/pipelines/ai_alpaca_trader
git add close_position.py
git commit -m "feat: add script to manually close positions and cancel brackets"
```

### Task 2: Update the Playbook Instructions

**Objective:** Teach the AI how to use the new script in the `PLAYBOOK.md` file.

**Files:**
- Modify: `~/pipelines/ai_alpaca_trader/PLAYBOOK.md`

**Step 1: Update the file**
Use the `patch` tool on `~/pipelines/ai_alpaca_trader/PLAYBOOK.md` to update the Monitoring section.

**Old String:**
```markdown
5. **Monitoring:** Review positions daily. Do NOT flatten at the end of the day. Allow the bracket orders to manage exits, or manually intervene if fundamentals drastically change.
```

**New String:**
```markdown
5. **Monitoring:** Review positions daily. Do NOT flatten at the end of the day. Allow the bracket orders to manage exits, OR manually intervene if your news research shows fundamentals have drastically degraded. To manually exit a trade before it hits its bracket targets, run `python3 ~/pipelines/ai_alpaca_trader/close_position.py --symbol <TICKER>`.
```

**Step 2: Commit**
```bash
cd ~/pipelines/ai_alpaca_trader
git add PLAYBOOK.md
git commit -m "docs: instruct AI on how to use close_position script in playbook"
```