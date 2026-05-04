# HFT Spread Multiple Bracket Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Modify the HFT strategy in `daytrader.py` to use a dynamic "Spread Multiple" for stop-loss and take-profit calculations to prevent instant stop-outs on tight-spread stocks.

**Architecture:** Instead of using fixed percentage constants (`HFT_TAKE_PROFIT_PCT` and `HFT_STOP_LOSS_PCT`) to calculate the absolute price for brackets, we will calculate the live bid-ask spread (`quote.ask_price - quote.bid_price`), multiply it by 3, and ensure a hard minimum clearance of $0.04. This value will be added/subtracted to the entry price to form the `tp_price` and `sl_price`.

**Tech Stack:** Python, Alpaca Trading API

---

### Task 1: Replace Fixed Percentage Brackets with Dynamic Spread Multiple

**Objective:** Update the HFT signal handler to calculate `tp_price` and `sl_price` dynamically based on the live spread rather than hardcoded percentages.

**Files:**
- Modify: `/home/ianstewart/bots/alpaca/daytrader.py:1335-1350`

**Step 1: Write the minimal implementation**

Replace the existing `if signal == "LONG":` block starting around line 1335 with the dynamic spread multiple calculation:

```python
    # Marketable Limit: Limit price slightly worse than current quote to ensure fill, but cap slippage
    spread = quote.ask_price - quote.bid_price
    min_clearance = max(spread * 3.0, 0.04) # Minimum 3x spread, floor of 4 cents
    
    if signal == "LONG":
        limit_price = round(quote.ask_price * 1.0005, 2) 
        tp_price = round(limit_price + min_clearance, 2)
        sl_price = round(limit_price - min_clearance, 2)
        side = OrderSide.BUY
    else:
        limit_price = round(quote.bid_price * 0.9995, 2)
        tp_price = round(limit_price - min_clearance, 2)
        sl_price = round(limit_price + min_clearance, 2)
        side = OrderSide.SELL

    with state_lock:
        pending_entries[symbol] = now
        pending_entry_values[symbol] = qty * limit_price
        pending_entry_risks[symbol] = qty * min_clearance
```

**Step 2: Verify Syntax**

Run: `python -m py_compile /home/ianstewart/bots/alpaca/daytrader.py`
Expected: Silent pass (no SyntaxError).

**Step 3: Commit**

```bash
cd /home/ianstewart/bots/alpaca
git add daytrader.py
git commit -m "fix(hft): replace static percentage brackets with dynamic spread multiple"
```