# High-Frequency Micro-Momentum Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Pivot the bot from a slow 1-minute bar strategy to a high-frequency micro-momentum strategy using real-time tick data (trades and quotes) to dramatically increase trade frequency.

**Architecture:** 
1. **Current Issue:** 1-minute bars aggregate too much data, missing rapid micro-trends, and the pullback filters are overly restrictive, resulting in near-zero trade volume.
2. **New Approach (HFT Micro-Momentum):** We will abandon `bars` and subscribe directly to the `trades` and `quotes` websocket streams. 
3. **Signal (Order Flow Imbalance):** We will track a rolling N-second window of trade volume. By comparing trade prices to the National Best Bid and Offer (NBBO) quotes, we classify volume as buyer-initiated or seller-initiated. A sudden heavy imbalance triggers an immediate entry.
4. **Execution:** Python over standard websockets has ~50-100ms latency, meaning we cannot compete with true nanosecond HFT market makers. Instead, we act as "micro-trend followers." We use marketable limit orders and extremely tight bracket exits (fractional percentages) to capture rapid price dislocations.

**Tech Stack:** Python, Alpaca API, `collections.deque`

---

### Task 1: Migrate WebSocket Streams to Trades & Quotes

**Objective:** Switch the Alpaca data stream subscriptions from 1-minute bars to real-time trades and quotes.

**Files:**
- Modify: `daytrader.py`

**Step 1: Update WebSocket Subscriptions**

In the `start_market_data_stream` (or equivalent initialization block), replace `subscribe_bars` with `subscribe_trades` and `subscribe_quotes`.

```python
# Remove or comment out: data_stream.subscribe_bars(handle_bar, *symbols)

# Add:
data_stream.subscribe_trades(handle_trade, *symbols)
data_stream.subscribe_quotes(handle_quote, *symbols)
```

**Step 2: Create basic handlers**

Create the new async handlers to replace `handle_bar`. We will flesh out the logic in subsequent tasks.

```python
async def handle_trade(trade):
    # trade has: symbol, timestamp, price, size, id, conditions
    pass

async def handle_quote(quote):
    # quote has: symbol, timestamp, bid_price, bid_size, ask_price, ask_size
    pass
```

---

### Task 2: Implement Micro-Structure State Management

**Objective:** Track the most recent quote (NBBO) and a rolling window of recent trades to calculate Order Flow Imbalance (OFI).

**Files:**
- Modify: `daytrader.py`

**Step 1: Update Global State Structures**

Use `collections.deque` for fast rolling windows.

```python
from collections import deque

# Add to Global State section
micro_state = {} 
# micro_state[symbol] = {
#     "latest_quote": None,
#     "recent_trades": deque(maxlen=500), # Store last 500 trades
#     "buy_vol_10s": 0.0,
#     "sell_vol_10s": 0.0
# }
```

**Step 2: Populate state in handlers**

Update `handle_quote` and `handle_trade`:

```python
async def handle_quote(quote):
    with state_lock:
        state = micro_state.setdefault(quote.symbol, {
            "latest_quote": None,
            "recent_trades": deque(maxlen=500),
            "buy_vol_10s": 0.0,
            "sell_vol_10s": 0.0
        })
        state["latest_quote"] = quote

async def handle_trade(trade):
    with state_lock:
        state = micro_state.setdefault(trade.symbol, {
            "latest_quote": None,
            "recent_trades": deque(maxlen=500),
            "buy_vol_10s": 0.0,
            "sell_vol_10s": 0.0
        })
        
        # Determine trade direction based on latest quote
        direction = "UNKNOWN"
        quote = state["latest_quote"]
        if quote:
            if trade.price >= quote.ask_price:
                direction = "BUY"
            elif trade.price <= quote.bid_price:
                direction = "SELL"
                
        state["recent_trades"].append({
            "timestamp": trade.timestamp,
            "price": trade.price,
            "size": trade.size,
            "direction": direction
        })
        
        # Prune trades older than 10 seconds
        cutoff = trade.timestamp - timedelta(seconds=10)
        while state["recent_trades"] and state["recent_trades"][0]["timestamp"] < cutoff:
            state["recent_trades"].popleft()
```

---

### Task 3: HFT Signal Generation & Rate Limiting

**Objective:** Trigger entries when short-term buying/selling pressure explodes, but enforce strict rate limits so we don't spam the API and get banned.

**Files:**
- Modify: `daytrader.py`

**Step 1: Calculate Imbalance and Trigger**

Inside `handle_trade`, after pruning old trades, calculate the aggregate volumes:

```python
        buy_vol = sum(t["size"] for t in state["recent_trades"] if t["direction"] == "BUY")
        sell_vol = sum(t["size"] for t in state["recent_trades"] if t["direction"] == "SELL")
        total_vol = buy_vol + sell_vol
        
        state["buy_vol_10s"] = buy_vol
        state["sell_vol_10s"] = sell_vol
```

**Step 2: Signal conditions**

```python
        # HFT parameters
        MIN_BURST_VOLUME = 5000 # Configurable
        IMBALANCE_THRESHOLD = 0.80 # 80% of volume in one direction
        
        if total_vol >= MIN_BURST_VOLUME:
            buy_ratio = buy_vol / total_vol
            sell_ratio = sell_vol / total_vol
            
            signal = None
            if buy_ratio >= IMBALANCE_THRESHOLD:
                signal = "LONG"
            elif sell_ratio >= IMBALANCE_THRESHOLD:
                signal = "SHORT"
                
            if signal:
                asyncio.create_task(evaluate_hft_entry(trade.symbol, signal, trade.price, quote))
```

**Step 3: Implement `evaluate_hft_entry` with strict rate limiting**

```python
# Add configurable globals
MAX_ORDERS_PER_MINUTE = 20
order_timestamps = deque(maxlen=MAX_ORDERS_PER_MINUTE)

async def evaluate_hft_entry(symbol, signal, price, quote):
    now = datetime.now(TIMEZONE)
    with state_lock:
        # Check API spam limits
        if len(order_timestamps) == MAX_ORDERS_PER_MINUTE:
            if (now - order_timestamps[0]).total_seconds() < 60:
                return # Rate limited
                
        # Existing checks (e.g. max exposure, daily limits, symbol cooldowns)
        if not is_symbol_trade_allowed(symbol, now):
            return
            
        # Temporarily lock symbol to prevent duplicate firing on the same tick burst
        symbol_cooldowns[symbol] = now + timedelta(seconds=15)
        order_timestamps.append(now)
        
    # Execute trade... (handoff to execution logic)
    print(f"HFT SIGNAL: {signal} {symbol} at {price}")
```

---

### Task 4: Lightning-Fast Execution & Exits

**Objective:** Submit marketable limit orders (to prevent catastrophic slippage on low liquidity) with very tight, static bracket exits suitable for seconds-long holding periods.

**Files:**
- Modify: `daytrader.py`

**Step 1: HFT Execution Logic**

In `evaluate_hft_entry`, construct a bracket order. We abandon ATR here because ATR relies on minute/daily bars and we are trading seconds.

```python
    # Tight HFT params
    HFT_TAKE_PROFIT_PCT = 0.002 # 0.2%
    HFT_STOP_LOSS_PCT = 0.001   # 0.1%
    
    qty = calculate_hft_position_size(price) # implement based on existing sizing
    if qty <= 0: return

    # Marketable Limit: Limit price slightly worse than current quote to ensure fill, but cap slippage
    if signal == "LONG":
        limit_price = round(quote.ask_price * 1.0005, 2) 
        tp_price = round(limit_price * (1 + HFT_TAKE_PROFIT_PCT), 2)
        sl_price = round(limit_price * (1 - HFT_STOP_LOSS_PCT), 2)
        side = OrderSide.BUY
    else:
        limit_price = round(quote.bid_price * 0.9995, 2)
        tp_price = round(limit_price * (1 - HFT_TAKE_PROFIT_PCT), 2)
        sl_price = round(limit_price * (1 + HFT_STOP_LOSS_PCT), 2)
        side = OrderSide.SELL

    # Use existing Alpaca client submission
    submit_bracket_order(symbol, side, qty, limit_price, tp_price, sl_price)
```

---

### Task 5: Adapt the Backtester for Tick Data

**Objective:** We can't use 1-minute bars to backtest this. We need to fetch and process tick data. Because tick data is massive, we will build a fetcher for just a 1-hour window.

**Files:**
- Modify: `replay_backtest.py`
- Create: `fetch_tick_data.py`

**Step 1: Tick Data Fetcher**
Write a script using `StockTradesRequest` to fetch 1 hour of trades for `AAPL` and save to `historical_ticks.csv`.

**Step 2: Update Backtester**
Rewrite `replay_backtest.py` to ingest ticks:
```python
def run_tick_replay(csv_path):
    # Re-implement the deque sliding window logic from Task 2 & 3
    # Iterate through ticks, simulate quotes (e.g. assume spread is 1 cent), 
    # check for IMBALANCE_THRESHOLD, and record HFT entries.
    pass
```