# Dynamic Market Movers Watchlist Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace the hardcoded static watchlist in the live daytrader bot with a dynamically generated list of the top 50 market movers (most active by volume) priced over $10.

**Architecture:** 
1. **Current Issue:** The bot only listens to a hardcoded list of 5 stocks (AAPL, NVDA, AMD, TSLA, MSFT). In HFT micro-momentum, liquidity and volatility are key; we need to trade whatever is moving *today*.
2. **New Approach:** At startup, we will query Alpaca's REST API for the top 100 most active stocks by volume. We will then query the Snapshots API to retrieve their current prices, filter out "penny stocks" (price < $10.00), and select the top 50 valid symbols to feed into our Websocket subscriptions.

**Tech Stack:** Python, `requests` library, Alpaca Data API.

---

### Task 1: Create Market Movers Fetcher

**Objective:** Write a robust helper function to fetch and filter the dynamic watchlist.

**Files:**
- Modify: `/home/ianstewart/bots/alpaca/daytrader.py`

**Step 1: Implement the fetcher function**

Add the `requests` import to `daytrader.py` if not present.
Create a new function `get_dynamic_watchlist(api_key, api_secret, target_count=50, min_price=10.0):`

```python
import requests

def get_dynamic_watchlist(api_key, api_secret, target_count=50, min_price=10.0):
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }
    
    # 1. Get Top 100 most active stocks by volume
    url_active = "https://data.alpaca.markets/v1beta1/screener/stocks/most-actives?by=volume&top=100"
    try:
        res = requests.get(url_active, headers=headers, timeout=10)
        res.raise_for_status()
        active_symbols = [item["symbol"] for item in res.json().get("most_actives", [])]
    except Exception as e:
        logger.error(f"Failed to fetch most active symbols: {e}")
        return ["SPY", "QQQ", "IWM", "DIA"] # Safe fallback
        
    if not active_symbols:
        return ["SPY", "QQQ"]
        
    # 2. Get snapshots to filter by minimum price
    chunk_str = ",".join(active_symbols)
    url_snapshots = f"https://data.alpaca.markets/v2/stocks/snapshots?symbols={chunk_str}"
    
    valid_symbols = []
    try:
        snap_res = requests.get(url_snapshots, headers=headers, timeout=10)
        snap_res.raise_for_status()
        snapshots = snap_res.json()
        
        # Iterate in the original sorted volume order to keep the most active at the top
        for sym in active_symbols:
            data = snapshots.get(sym)
            if data and data.get("latestTrade"):
                price = data["latestTrade"].get("p", 0.0)
                if price >= min_price:
                    valid_symbols.append(sym)
                    if len(valid_symbols) == target_count:
                        break
    except Exception as e:
        logger.error(f"Failed to fetch snapshots for price filtering: {e}")
        return active_symbols[:target_count] # Fallback to unfiltered list
        
    return valid_symbols
```

---

### Task 2: Integrate Dynamic Watchlist into the Live Bot

**Objective:** Wire the new function into the bot's startup sequence so the Websocket subscribes to the dynamic list.

**Files:**
- Modify: `/home/ianstewart/bots/alpaca/daytrader.py`

**Step 1: Replace hardcoded symbols**

Locate the `main()` function or wherever the Websocket subscriptions are instantiated in `daytrader.py`.

```python
    # Look for something like:
    # symbols = ["AAPL", "NVDA", "AMD", "TSLA", "MSFT"]
    
    # Replace with:
    logger.info("Fetching dynamic watchlist of top movers > $10...")
    symbols = get_dynamic_watchlist(API_KEY, API_SECRET, target_count=50, min_price=10.0)
    logger.info(f"Dynamic Watchlist Generated: {len(symbols)} symbols. {symbols[:5]}...")

    # Ensure the stream uses the dynamic list:
    # data_stream.subscribe_trades(handle_trade, *symbols)
    # data_stream.subscribe_quotes(handle_quote, *symbols)
```

**Step 2: Ensure proper SPY inclusion**

The bot's logic relies on checking `SPY` for relative strength and market regimes. Ensure `SPY` is always injected into the watchlist if it isn't returned natively by the screener.

```python
    if "SPY" not in symbols:
        symbols.append("SPY")
```

---

### Task 3: Update Backtest Fetcher to Support Dynamic Watchlist

**Objective:** Allow `fetch_tick_data.py` to also pull the same 50 market movers so we can test the HFT strategy properly against a wide, volatile basket.

**Files:**
- Modify: `/home/ianstewart/bots/alpaca/fetch_tick_data.py`

**Step 1: Copy/Import helper and execute**
Add a mechanism to `fetch_tick_data.py` that utilizes the same `most-actives` API logic to generate its symbol target list. 

```python
# In fetch_tick_data.py, implement the same logic (or just copy the function) 
# and use it if no symbols are hardcoded:

if __name__ == "__main__":
    # Add identical get_dynamic_watchlist logic
    symbols = get_dynamic_watchlist(api_key, api_secret, target_count=50, min_price=10.0)
    if "SPY" not in symbols:
        symbols.append("SPY")
    print(f"Fetching ticks for {len(symbols)} dynamic symbols...")
    fetch_ticks(symbols)
```