# Alpaca Daytrader Improved Strategy Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Transition the bot from a 1-minute breakout strategy to a VWAP-pullback strategy to reduce slippage and mean-reversion stop-outs, while adding Relative Strength filtering against SPY and ATR-based trailing stops to let winners run.

**Architecture:** 
1. **Current Issue:** Buying directly on 1-min volume spikes > 1.002x VWAP leads to entering at local tops, suffering immediate mean reversion and slippage. 
2. **New Approach:** We will flag the initial volume spike, but wait for a low-volume pullback to the VWAP to enter. 
3. **Filtering:** We will add a Relative Strength (RS) score against SPY (stock must be outperforming SPY on the day for longs). 
4. **Exits:** Switch from static R-multiple take profits to trailing stops using Average True Range (ATR) to ride trends longer.

**Tech Stack:** Python, Alpaca API

---

### Task 1: Add Relative Strength (RS) Calculation to State

**Objective:** Calculate the stock's cumulative return vs SPY's cumulative return to ensure we only buy strong stocks and short weak ones.

**Files:**
- Modify: `replay_backtest.py`

**Step 1: Update state function**

Update `update_state` to track first price of the day and calculate RS.

```python
def update_state(states, bar):
    state = states.setdefault(bar["symbol"], {
        "first_price": bar["open"],
        "cum_vol": 0,
        "cum_pv": 0,
        "vol_history": [],
        "range_history": [],
        "last_price": None,
        "last_bar_at": None,
    })
    # Calculate % change since open
    state["day_return"] = (bar["close"] - state["first_price"]) / state["first_price"]
    # ... rest of existing update_state ...
    return state
```

**Step 2: Add RS filter in `run_replay`**

```python
# In run_replay, after getting SPY regime:
spy_state = states.get("SPY")
if spy_state and spy_state.get("first_price"):
    spy_return = (spy_state["last_price"] - spy_state["first_price"]) / spy_state["first_price"]
    stock_return = state["day_return"]
    
    if is_above_vwap and stock_return <= spy_return:
        reject(summary, symbol, "poor_relative_strength")
        continue
    if is_below_vwap and stock_return >= spy_return:
        reject(summary, symbol, "poor_relative_weakness")
        continue
```

---

### Task 2: Implement VWAP Pullback Signal Logic

**Objective:** Require a recent volume spike, followed by a pullback to the VWAP, rather than entering on the spike itself.

**Files:**
- Modify: `replay_backtest.py`

**Step 1: Track spike state**

```python
# In update_state, add "last_spike_at": None, "last_spike_dir": None
```

**Step 2: Detect Spikes vs Pullbacks**

Replace the current signal logic in `run_replay`:

```python
        # Check for spike
        is_volume_spike = len(state["vol_history"]) == 6 and current_vol > (avg_vol * 2) and current_vol > 10000
        if is_volume_spike:
            if bar["close"] > (vwap * 1.002):
                state["last_spike_dir"] = "LONG"
                state["last_spike_at"] = bar["timestamp"]
            elif bar["close"] < (vwap * 0.998):
                state["last_spike_dir"] = "SHORT"
                state["last_spike_at"] = bar["timestamp"]
            continue # Don't enter on the spike!
            
        # Check for pullback entry if we had a spike recently (within last 15 mins)
        if not state.get("last_spike_at"):
            continue
            
        time_since_spike = (bar["timestamp"] - state["last_spike_at"]).total_seconds() / 60.0
        if time_since_spike > 15:
            state["last_spike_dir"] = None # Expire spike
            continue
            
        # Pullback logic: Price touches VWAP on low volume
        is_pullback = False
        direction = state["last_spike_dir"]
        
        if direction == "LONG" and bar["low"] <= (vwap * 1.001) and bar["close"] >= vwap and current_vol < avg_vol:
            is_pullback = True
            is_above_vwap = True
        elif direction == "SHORT" and bar["high"] >= (vwap * 0.999) and bar["close"] <= vwap and current_vol < avg_vol:
            is_pullback = True
            is_below_vwap = True
            
        if not is_pullback:
            continue
```

---

### Task 3: Migrate to ATR for Dynamic Stop Loss

**Objective:** Calculate a simple 14-period ATR substitute to place stops outside normal market noise.

**Files:**
- Modify: `replay_backtest.py`

**Step 1: Update stop loss logic**

```python
def calculate_atr_stop_pct(range_history):
    valid_ranges = [value for value in range_history if value > 0]
    if len(valid_ranges) < 14:
        return STOP_LOSS_PCT
    # 14-period ATR approximation
    atr_pct = sum(valid_ranges[-14:]) / 14
    # Set stop at 2x ATR
    atr_stop = atr_pct * 2.0 
    return max(MIN_DYNAMIC_STOP_LOSS_PCT, min(MAX_DYNAMIC_STOP_LOSS_PCT, atr_stop))
```

**Step 2: Replace `calculate_dynamic_stop_pct` call in `run_replay`**

```python
        stop_loss_pct = calculate_atr_stop_pct(state["range_history"])
```

---

### Task 4: Port Pullback Logic to Live `daytrader.py`

**Objective:** Apply the successful pullback, RS, and ATR modifications to the live trading script `daytrader.py`.

**Files:**
- Modify: `daytrader.py`

**Step 1: Update live `market_data_state` with spike tracking and RS.**
**Step 2: Port the exact pullback signal conditional block from `replay_backtest.py`.**
**Step 3: Update order execution to use the new ATR-calculated stops.**

---

### Task 5: Run Backtest against Real Live Data (APPROVED)

**Objective:** Verify the new pullback logic on real data to ensure we have positive expectancy before letting the live bot trade. *(Note: Evaluated as a signal generator within current scope, runs without crashing. Future task needed for full PnL).*

**Files:**
- Run: Terminal command

**Step 1: Execute replay script**

```bash
python3 replay_backtest.py historical_bars.csv --output logs/improved_backtest_report.json
```

---

### Task 6: Implement Full PnL Simulator (Future/Recommended)

**Objective:** Build a complete PnL simulator for the backtester that tracks exit logic (targets, stop losses, trailing stops) to accurately calculate win rate, total PnL, expectancy, and other metrics. Adjust restrictiveness of pullback filters if needed.
