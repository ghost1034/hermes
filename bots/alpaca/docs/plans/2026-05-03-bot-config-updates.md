# Alpaca Bot Configuration Updates Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Allow unlimited trades per symbol per day and increase the maximum position size from 10% to 15%.

**Architecture:** Configuration constants are updated in the main `daytrader.py` and `replay_backtest.py`. Logic checks are updated to treat a limit of `0` or less as "unlimited". Existing test logic is split to explicitly verify both limited and unlimited behaviors.

**Tech Stack:** Python, Alpaca API

---

### Task 1: Increase maximum position size to 15%

**Objective:** Update the global constant controlling maximum position size in the daytrader bot.

**Files:**
- Modify: `daytrader.py`

**Step 1: Write minimal implementation**
Modify `daytrader.py` to change `POSITION_SIZE_MAX_PCT` from `0.10` to `0.15`.

```python
# Before
POSITION_SIZE_MAX_PCT = 0.10

# After
POSITION_SIZE_MAX_PCT = 0.15
```

**Step 2: Commit**
```bash
git add daytrader.py
git commit -m "feat: increase max position size to 15 percent"
```

### Task 2: Implement unlimited trades per ticker in `daytrader.py`

**Objective:** Update the daily symbol trade counter configuration and logic to treat `0` as unlimited.

**Files:**
- Modify: `daytrader.py`

**Step 1: Write minimal implementation**
Change the fallback value in `os.environ.get("MAX_TRADES_PER_SYMBOL_PER_DAY", ...)` from `"3"` to `"0"`.

```python
# Before
MAX_TRADES_PER_SYMBOL_PER_DAY = int(os.environ.get("MAX_TRADES_PER_SYMBOL_PER_DAY", "3"))

# After
MAX_TRADES_PER_SYMBOL_PER_DAY = int(os.environ.get("MAX_TRADES_PER_SYMBOL_PER_DAY", "0"))
```

Bypass the max trade count check if `MAX_TRADES_PER_SYMBOL_PER_DAY` is `<= 0`.

```python
# Before
    if trade_count >= MAX_TRADES_PER_SYMBOL_PER_DAY:
        logger.info(f"Skipping {symbol} signal - max daily symbol trades reached ({MAX_TRADES_PER_SYMBOL_PER_DAY}).")
        log_signal_rejection(symbol, "max_symbol_trades", trade_count=trade_count, max_trades=MAX_TRADES_PER_SYMBOL_PER_DAY)
        return False

# After
    if MAX_TRADES_PER_SYMBOL_PER_DAY > 0 and trade_count >= MAX_TRADES_PER_SYMBOL_PER_DAY:
        logger.info(f"Skipping {symbol} signal - max daily symbol trades reached ({MAX_TRADES_PER_SYMBOL_PER_DAY}).")
        log_signal_rejection(symbol, "max_symbol_trades", trade_count=trade_count, max_trades=MAX_TRADES_PER_SYMBOL_PER_DAY)
        return False
```

**Step 2: Commit**
```bash
git add daytrader.py
git commit -m "feat: allow unlimited trades per symbol per day by default"
```

### Task 3: Implement unlimited trades in `replay_backtest.py`

**Objective:** Apply the same trade count check bypass logic to the replay backtesting engine.

**Files:**
- Modify: `replay_backtest.py`

**Step 1: Write minimal implementation**

```python
# Before
MAX_TRADES_PER_SYMBOL_PER_DAY = int(os.environ.get("MAX_TRADES_PER_SYMBOL_PER_DAY", "3"))

# After
MAX_TRADES_PER_SYMBOL_PER_DAY = int(os.environ.get("MAX_TRADES_PER_SYMBOL_PER_DAY", "0"))
```

Update the backtest loop check:

```python
# Before
        if trade_counts[symbol] >= MAX_TRADES_PER_SYMBOL_PER_DAY:
            continue

# After
        if MAX_TRADES_PER_SYMBOL_PER_DAY > 0 and trade_counts[symbol] >= MAX_TRADES_PER_SYMBOL_PER_DAY:
            continue
```

**Step 2: Commit**
```bash
git add replay_backtest.py
git commit -m "feat: support unlimited daily trades in backtest replay"
```

### Task 4: Update test suite to verify limited and unlimited behavior

**Objective:** Rewrite the trade count test to assert both legacy "limit reached" behavior and the new "unlimited" behavior.

**Files:**
- Modify: `tests/test_daytrader_logic.py`

**Step 1: Write minimal implementation**
Replace the `self.dt.symbol_trade_counts["AAPL"]...` block in `test_symbol_cooldown_and_trade_count_gates`.

```python
# Before
        self.dt.symbol_cooldowns.clear()
        self.dt.symbol_trade_counts["AAPL"] = self.dt.MAX_TRADES_PER_SYMBOL_PER_DAY
        self.assertFalse(self.dt.is_symbol_trade_allowed("AAPL", now=now))

        self.dt.symbol_trade_counts["AAPL"] = self.dt.MAX_TRADES_PER_SYMBOL_PER_DAY - 1
        self.assertTrue(self.dt.is_symbol_trade_allowed("AAPL", now=now))

# After
        self.dt.symbol_cooldowns.clear()
        
        # Test unlimited behavior (0)
        self.dt.MAX_TRADES_PER_SYMBOL_PER_DAY = 0
        self.dt.symbol_trade_counts["AAPL"] = 10
        self.assertTrue(self.dt.is_symbol_trade_allowed("AAPL", now=now))
        
        # Test limited behavior (3)
        self.dt.MAX_TRADES_PER_SYMBOL_PER_DAY = 3
        self.dt.symbol_trade_counts["AAPL"] = 3
        self.assertFalse(self.dt.is_symbol_trade_allowed("AAPL", now=now))
        
        self.dt.symbol_trade_counts["AAPL"] = 2
        self.assertTrue(self.dt.is_symbol_trade_allowed("AAPL", now=now))
```

**Step 2: Run test to verify pass**
Run: `python -m unittest tests/test_daytrader_logic.py -v`
Expected: PASS

**Step 3: Commit**
```bash
git add tests/test_daytrader_logic.py
git commit -m "test: verify limited and unlimited daily symbol trade behaviors"
```
