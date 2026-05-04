# HFT Edge Case Fixes Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Fix critical edge cases in the HFT strategy: unpredictable slippage due to banker's rounding, missing spread validation limits, and incorrect stop-loss anchoring.

**Architecture:** 
1. Introduce a strict validation check to abort trades if quotes are crossed, zeroed out, or if the spread percentage exceeds `MAX_SPREAD_PCT`.
2. Use `math.ceil` and `math.floor` for calculating marketable limits to enforce exact slippage bounds.
3. Anchor Take Profit and Stop Loss directly to `quote.ask_price` or `quote.bid_price` rather than the slippage-padded `limit_price`.

**Tech Stack:** Python, Alpaca API

---

### Task 1: Add `math` import and Quote/Spread Safety Checks

**Objective:** Import the `math` module and add validation to ensure quotes are valid and the spread does not exceed `MAX_SPREAD_PCT`.

**Files:**
- Modify: `/home/ianstewart/bots/alpaca/daytrader.py`

**Step 1: Write a minimal test script**
Create a temporary syntax check test since we are modifying a complex async file.
Create `/home/ianstewart/bots/alpaca/tests/test_syntax.py`:
```python
import sys
import py_compile

def test_syntax():
    try:
        py_compile.compile('/home/ianstewart/bots/alpaca/daytrader.py', doraise=True)
    except Exception as e:
        print(f"Syntax error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_syntax()
```

**Step 2: Run test to verify pass (baseline)**
Run: `python /home/ianstewart/bots/alpaca/tests/test_syntax.py`
Expected: Silent pass.

**Step 3: Write minimal implementation**
Modify `/home/ianstewart/bots/alpaca/daytrader.py`:
1. Near the top of the file (around line 9, near `import traceback`), add `import math`.
2. In `evaluate_hft_entry` (around line 1335, just before the `min_clearance` calculation), insert the safety checks.

Use `patch` or standard file writing to ensure this exact code replaces the original `spread = ...` section:

```python
    # Ensure quotes are valid and not crossed
    if quote.ask_price <= 0 or quote.bid_price <= 0 or quote.ask_price < quote.bid_price:
        logger.info(f"Skipping {symbol} HFT signal - invalid or crossed quotes.")
        return
        
    spread = quote.ask_price - quote.bid_price
    midpoint = (quote.ask_price + quote.bid_price) / 2
    spread_pct = spread / midpoint if midpoint > 0 else 0
    
    if spread_pct > MAX_SPREAD_PCT:
        logger.info(f"Skipping {symbol} HFT signal - spread too wide ({spread_pct:.3%} > {MAX_SPREAD_PCT:.3%}).")
        return

    min_clearance = max(spread * 3.0, 0.04) # Minimum 3x spread, floor of 4 cents
```

**Step 4: Run test to verify syntax**
Run: `python /home/ianstewart/bots/alpaca/tests/test_syntax.py`
Expected: Silent pass.

**Step 5: Commit**
```bash
cd /home/ianstewart/bots/alpaca
git add daytrader.py
git commit -m "fix(hft): add quote validation and max spread safety check"
```

---

### Task 2: Fix Slippage Rounding and Bracket Anchoring

**Objective:** Update the HFT limit and bracket math to use `math.ceil/floor` and anchor directly to the quote prices.

**Files:**
- Modify: `/home/ianstewart/bots/alpaca/daytrader.py`

**Step 1: Write isolated math test**
Create `/home/ianstewart/bots/alpaca/tests/test_hft_math.py`:
```python
import math

def test_math():
    ask_price = 20.00
    bid_price = 19.98
    spread = ask_price - bid_price
    min_clearance = max(spread * 3.0, 0.04)
    
    # LONG
    limit_price_long = math.ceil(ask_price * 1.0005 * 100) / 100
    tp_price_long = round(ask_price + min_clearance, 2)
    sl_price_long = round(ask_price - min_clearance, 2)
    
    assert limit_price_long == 20.01
    assert tp_price_long == 20.06
    assert sl_price_long == 19.94
    print("Math tests passed!")

if __name__ == "__main__":
    test_math()
```

**Step 2: Run math test**
Run: `python /home/ianstewart/bots/alpaca/tests/test_hft_math.py`
Expected: "Math tests passed!"

**Step 3: Write minimal implementation**
In `/home/ianstewart/bots/alpaca/daytrader.py` around line 1350, replace the `if signal == "LONG":` block with the new `math.ceil`/`math.floor` logic:

```python
    if signal == "LONG":
        limit_price = math.ceil(quote.ask_price * 1.0005 * 100) / 100
        tp_price = round(quote.ask_price + min_clearance, 2)
        sl_price = round(quote.ask_price - min_clearance, 2)
        side = OrderSide.BUY
    else:
        limit_price = math.floor(quote.bid_price * 0.9995 * 100) / 100
        tp_price = round(quote.bid_price - min_clearance, 2)
        sl_price = round(quote.bid_price + min_clearance, 2)
        side = OrderSide.SELL
```

**Step 4: Run syntax check**
Run: `python /home/ianstewart/bots/alpaca/tests/test_syntax.py`
Expected: Silent pass.

**Step 5: Commit**
```bash
cd /home/ianstewart/bots/alpaca
git add daytrader.py tests/
git commit -m "fix(hft): resolve banker rounding for limits and anchor brackets to quote"
```