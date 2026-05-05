#!/usr/bin/env python3
import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, time as datetime_time

import pytz


TIMEZONE = pytz.timezone("America/New_York")

START_TIME = datetime_time(10, 0)
STOP_ENTRIES_TIME = datetime_time(15, 0)
STOP_LOSS_PCT = float(os.environ.get("STOP_LOSS_PCT", "0.0075"))
TAKE_PROFIT_PCT = float(os.environ.get("TAKE_PROFIT_PCT", "0.015"))
SPY_REGIME_MAX_AGE_SECONDS = int(os.environ.get("SPY_REGIME_MAX_AGE_SECONDS", "180"))
MAX_SPREAD_PCT = float(os.environ.get("MAX_SPREAD_PCT", "0.002"))
MIN_DOLLAR_VOLUME_1M = float(os.environ.get("MIN_DOLLAR_VOLUME_1M", "250000"))
MAX_BAR_RANGE_PCT = float(os.environ.get("MAX_BAR_RANGE_PCT", "0.03"))
MIN_DIRECTIONAL_CLOSE_LOCATION = float(os.environ.get("MIN_DIRECTIONAL_CLOSE_LOCATION", "0.65"))
MIN_DYNAMIC_STOP_LOSS_PCT = float(os.environ.get("MIN_DYNAMIC_STOP_LOSS_PCT", "0.005"))
MAX_DYNAMIC_STOP_LOSS_PCT = float(os.environ.get("MAX_DYNAMIC_STOP_LOSS_PCT", "0.02"))
TAKE_PROFIT_R_MULTIPLE = float(os.environ.get("TAKE_PROFIT_R_MULTIPLE", "2.0"))
MAX_DYNAMIC_TAKE_PROFIT_PCT = float(os.environ.get("MAX_DYNAMIC_TAKE_PROFIT_PCT", "0.03"))
MAX_TRADES_PER_SYMBOL_PER_DAY = int(os.environ.get("MAX_TRADES_PER_SYMBOL_PER_DAY", "0"))


def parse_timestamp(value):
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        return TIMEZONE.localize(timestamp)
    return timestamp.astimezone(TIMEZONE)


def parse_row(row):
    try:
        return {
            "symbol": row["symbol"].upper(),
            "timestamp": parse_timestamp(row["timestamp"]),
            "open": float(row.get("open") or row.get("o") or 0),
            "high": float(row.get("high") or row.get("h") or 0),
            "low": float(row.get("low") or row.get("l") or 0),
            "close": float(row.get("close") or row.get("c") or 0),
            "volume": float(row.get("volume") or row.get("v") or 0),
        }
    except (ValueError, TypeError, KeyError):
        return None


def reject(summary, symbol, reason):
    summary["signals_rejected"] += 1
    summary["rejections_by_reason"][reason] += 1
    summary["rejections_by_symbol"][symbol] += 1


def calculate_atr_stop_pct(range_history):
    if len(range_history) < 14:
        return STOP_LOSS_PCT
    # 14-period ATR approximation
    atr_pct = sum(range_history[-14:]) / 14
    # Set stop at 2x ATR
    atr_stop = atr_pct * 2.0 
    return max(MIN_DYNAMIC_STOP_LOSS_PCT, min(MAX_DYNAMIC_STOP_LOSS_PCT, atr_stop))


def calculate_take_profit_pct(stop_loss_pct):
    dynamic_take_profit_pct = max(TAKE_PROFIT_PCT, stop_loss_pct * TAKE_PROFIT_R_MULTIPLE)
    return min(MAX_DYNAMIC_TAKE_PROFIT_PCT, dynamic_take_profit_pct)


def close_location_ok(bar, is_long):
    bar_range = bar["high"] - bar["low"]
    if bar_range <= 0 or bar["close"] <= 0:
        return False, "invalid_bar_range"
    bar_range_pct = bar_range / bar["close"]
    if bar_range_pct > MAX_BAR_RANGE_PCT:
        return False, "bar_range_too_wide"
    close_location = (bar["close"] - bar["low"]) / bar_range
    if is_long and close_location < MIN_DIRECTIONAL_CLOSE_LOCATION:
        return False, "weak_directional_close"
    if not is_long and close_location > (1 - MIN_DIRECTIONAL_CLOSE_LOCATION):
        return False, "weak_directional_close"
    return True, None


def update_state(states, bar):
    state = states.setdefault(bar["symbol"], {
        "first_price": bar["open"],
        "cum_vol": 0,
        "cum_pv": 0,
        "vol_history": [],
        "range_history": [],
        "last_price": None,
        "last_bar_at": None,
        "last_spike_at": None,
        "last_spike_dir": None,
        "last_spike_avg_vol": None,
    })
    if state["first_price"] > 0:
        state["day_return"] = (bar["close"] - state["first_price"]) / state["first_price"]
    else:
        state["day_return"] = 0.0
    typical_price = (bar["high"] + bar["low"] + bar["close"]) / 3
    state["cum_vol"] += bar["volume"]
    state["cum_pv"] += typical_price * bar["volume"]
    state["last_price"] = bar["close"]
    state["last_bar_at"] = bar["timestamp"]
    state["vol_history"].append(bar["volume"])
    if len(state["vol_history"]) > 6:
        state["vol_history"].pop(0)
    range_pct = ((bar["high"] - bar["low"]) / bar["close"]) if bar["close"] > 0 else 0
    state["range_history"].append(range_pct)
    if len(state["range_history"]) > 15:
        state["range_history"].pop(0)
    return state


def get_spy_regime(states, now):
    spy_state = states.get("SPY")
    if not spy_state or not spy_state.get("last_bar_at") or spy_state.get("cum_vol", 0) <= 0:
        return None, None, None, "spy_regime_unavailable"
    age_seconds = (now - spy_state["last_bar_at"]).total_seconds()
    if age_seconds > SPY_REGIME_MAX_AGE_SECONDS:
        return None, None, None, "spy_regime_stale"
    spy_vwap = spy_state["cum_pv"] / spy_state["cum_vol"]
    return spy_state["last_price"], spy_vwap, spy_state["last_price"] > spy_vwap, None


def run_replay(csv_path, assumed_spread_pct):
    states = {}
    trade_counts = defaultdict(int)
    current_day = None
    summary = {
        "bars_processed": 0,
        "signals_detected": 0,
        "signals_rejected": 0,
        "candidate_entries": 0,
        "rejections_by_reason": defaultdict(int),
        "rejections_by_symbol": defaultdict(int),
        "entries_by_symbol": defaultdict(int),
        "entries": [],
    }

    with open(csv_path, "r", encoding="utf-8") as f:
        bars = [r for r in (parse_row(row) for row in csv.DictReader(f)) if r is not None]

    bars.sort(key=lambda bar: (bar["timestamp"], bar["symbol"]))

    for bar in bars:
        bar_day = bar["timestamp"].date()
        if current_day != bar_day:
            states.clear()
            trade_counts.clear()
            current_day = bar_day

        summary["bars_processed"] += 1
        state = update_state(states, bar)
        current_time = bar["timestamp"].time()
        if bar["symbol"] == "SPY" or not (START_TIME <= current_time < STOP_ENTRIES_TIME):
            continue

        vwap = state["cum_pv"] / state["cum_vol"] if state["cum_vol"] > 0 else bar["close"]
        avg_vol = sum(state["vol_history"][:-1]) / max(1, len(state["vol_history"][:-1]))
        current_vol = state["vol_history"][-1]
        
        # Check for spike
        is_volume_spike = len(state["vol_history"]) == 6 and current_vol > (avg_vol * 2) and current_vol > 10000
        if is_volume_spike:
            if bar["close"] > (vwap * 1.002):
                state["last_spike_dir"] = "LONG"
                state["last_spike_at"] = bar["timestamp"]
                state["last_spike_avg_vol"] = avg_vol
            elif bar["close"] < (vwap * 0.998):
                state["last_spike_dir"] = "SHORT"
                state["last_spike_at"] = bar["timestamp"]
                state["last_spike_avg_vol"] = avg_vol
            continue # Don't enter on the spike!
            
        # Check for pullback entry if we had a spike recently (within last 15 mins)
        if not state.get("last_spike_at"):
            continue
            
        time_since_spike = (bar["timestamp"] - state["last_spike_at"]).total_seconds() / 60.0
        if time_since_spike > 15:
            state["last_spike_dir"] = None # Expire spike
            state["last_spike_at"] = None
            state["last_spike_avg_vol"] = None
            continue
            
        # Pullback logic: Price touches VWAP on low volume
        is_pullback = False
        direction = state["last_spike_dir"]
        is_above_vwap = False
        is_below_vwap = False
        
        target_avg_vol = state["last_spike_avg_vol"] if state["last_spike_avg_vol"] is not None else avg_vol
        
        if direction == "LONG" and bar["low"] <= (vwap * 1.001) and bar["close"] >= vwap and current_vol < target_avg_vol:
            is_pullback = True
            is_above_vwap = True
        elif direction == "SHORT" and bar["high"] >= (vwap * 0.999) and bar["close"] <= vwap and current_vol < target_avg_vol:
            is_pullback = True
            is_below_vwap = True
            
        if not is_pullback:
            continue

        symbol = bar["symbol"]
        direction = "LONG" if is_above_vwap else "SHORT"
        summary["signals_detected"] += 1

        if MAX_TRADES_PER_SYMBOL_PER_DAY > 0 and trade_counts[symbol] >= MAX_TRADES_PER_SYMBOL_PER_DAY:
            reject(summary, symbol, "max_symbol_trades")
            continue

        dollar_volume = current_vol * bar["close"]
        if dollar_volume < MIN_DOLLAR_VOLUME_1M:
            reject(summary, symbol, "dollar_volume_too_low")
            continue

        ok, reason = close_location_ok(bar, is_above_vwap)
        if not ok:
            reject(summary, symbol, reason)
            continue

        if assumed_spread_pct > MAX_SPREAD_PCT:
            reject(summary, symbol, "spread_too_wide")
            continue

        spy_price, spy_vwap, spy_is_bullish, spy_error = get_spy_regime(states, bar["timestamp"])
        if spy_error:
            reject(summary, symbol, spy_error)
            continue
        if is_above_vwap and not spy_is_bullish:
            reject(summary, symbol, "spy_regime_mismatch")
            continue
        if is_below_vwap and spy_is_bullish:
            reject(summary, symbol, "spy_regime_mismatch")
            continue

        spy_state = states.get("SPY")
        if spy_state and spy_state.get("first_price") is not None and spy_state["first_price"] > 0:
            spy_return = (spy_state["last_price"] - spy_state["first_price"]) / spy_state["first_price"]
            stock_return = state["day_return"]
            if is_above_vwap and stock_return <= spy_return:
                reject(summary, symbol, "poor_relative_strength")
                continue
            if is_below_vwap and stock_return >= spy_return:
                reject(summary, symbol, "poor_relative_weakness")
                continue

        stop_loss_pct = calculate_atr_stop_pct(state["range_history"])
        take_profit_pct = calculate_take_profit_pct(stop_loss_pct)
        trade_counts[symbol] += 1
        summary["candidate_entries"] += 1
        summary["entries_by_symbol"][symbol] += 1
        summary["entries"].append({
            "timestamp": bar["timestamp"].isoformat(),
            "symbol": symbol,
            "direction": direction,
            "price": bar["close"],
            "vwap": vwap,
            "volume": current_vol,
            "avg_volume": avg_vol,
            "dollar_volume": dollar_volume,
            "spy_price": spy_price,
            "spy_vwap": spy_vwap,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
        })

        state["last_spike_dir"] = None
        state["last_spike_at"] = None
        state["last_spike_avg_vol"] = None

    summary["rejections_by_reason"] = dict(summary["rejections_by_reason"])
    summary["rejections_by_symbol"] = dict(summary["rejections_by_symbol"])
    summary["entries_by_symbol"] = dict(summary["entries_by_symbol"])
    return summary


def main():
    parser = argparse.ArgumentParser(description="Replay 1-minute CSV bars through the Alpaca bot signal filters.")
    parser.add_argument("csv", help="CSV with symbol,timestamp,open,high,low,close,volume columns")
    parser.add_argument("--assumed-spread-pct", type=float, default=0.0, help="Optional spread percentage to apply to all bars")
    parser.add_argument("--output", help="Write JSON report to this path")
    args = parser.parse_args()

    summary = run_replay(args.csv, args.assumed_spread_pct)
    output = json.dumps(summary, indent=2, sort_keys=True)
    if args.output:
        parent_dir = os.path.dirname(args.output)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
    print(output)


if __name__ == "__main__":
    main()
