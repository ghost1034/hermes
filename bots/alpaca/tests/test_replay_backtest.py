import pytest
from datetime import datetime
import pytz
from bots.alpaca.replay_backtest import (
    calculate_atr_stop_pct,
    calculate_take_profit_pct,
    close_location_ok,
    update_state,
    get_spy_regime,
    parse_timestamp,
    TIMEZONE,
    STOP_LOSS_PCT,
    VOLATILITY_STOP_MULTIPLIER,
    MIN_DYNAMIC_STOP_LOSS_PCT,
    MAX_DYNAMIC_STOP_LOSS_PCT,
)

def test_parse_timestamp():
    ts = parse_timestamp("2023-01-01T09:30:00Z")
    assert ts.tzinfo is not None
    assert ts.tzinfo.zone == TIMEZONE.zone
    
def test_calculate_atr_stop_pct():
    # Empty or zero ranges should return STOP_LOSS_PCT
    assert calculate_atr_stop_pct([]) == STOP_LOSS_PCT
    assert calculate_atr_stop_pct([0, 0]) == STOP_LOSS_PCT
    
    # Less than 14 valid ranges should return STOP_LOSS_PCT
    ranges = [0.01] * 10
    assert calculate_atr_stop_pct(ranges) == STOP_LOSS_PCT

    # 14 or more valid ranges
    ranges = [0.01] * 14 # atr = 0.01
    expected = 0.01 * 2.0
    expected = max(MIN_DYNAMIC_STOP_LOSS_PCT, min(MAX_DYNAMIC_STOP_LOSS_PCT, expected))
    assert calculate_atr_stop_pct(ranges) == pytest.approx(expected)

def test_calculate_take_profit_pct():
    stop_pct = 0.01
    from bots.alpaca.replay_backtest import TAKE_PROFIT_PCT, TAKE_PROFIT_R_MULTIPLE, MAX_DYNAMIC_TAKE_PROFIT_PCT
    expected = max(TAKE_PROFIT_PCT, stop_pct * TAKE_PROFIT_R_MULTIPLE)
    expected = min(MAX_DYNAMIC_TAKE_PROFIT_PCT, expected)
    assert calculate_take_profit_pct(stop_pct) == expected

def test_close_location_ok():
    # Long test
    bar = {
        "high": 100,
        "low": 98,
        "close": 99.5 # range = 2, close = 99.5. pct = 2/99.5 = 0.02. close loc = 1.5 / 2 = 0.75
    }
    from bots.alpaca.replay_backtest import MIN_DIRECTIONAL_CLOSE_LOCATION
    assert 0.75 >= MIN_DIRECTIONAL_CLOSE_LOCATION
    ok, reason = close_location_ok(bar, True)
    assert ok is True
    
    # Short test
    bar["close"] = 98.2 # close location = 0.2 / 2 = 0.1
    ok, reason = close_location_ok(bar, False)
    assert ok is True

def test_update_state():
    states = {}
    bar = {
        "symbol": "AAPL",
        "timestamp": parse_timestamp("2023-01-01T09:30:00Z"),
        "open": 100,
        "high": 101,
        "low": 99,
        "close": 100.5,
        "volume": 1000
    }
    state = update_state(states, bar)
    assert state["first_price"] == 100
    assert state["cum_vol"] == 1000
    assert len(state["vol_history"]) == 1
    assert state["last_price"] == 100.5
    
def test_get_spy_regime():
    states = {
        "SPY": {
            "last_bar_at": parse_timestamp("2023-01-01T09:30:00Z"),
            "cum_vol": 1000,
            "cum_pv": 100000, # vwap = 100
            "last_price": 101
        }
    }
    now = parse_timestamp("2023-01-01T09:31:00Z")
    price, vwap, is_bullish, error = get_spy_regime(states, now)
    assert error is None
    assert price == 101
    assert vwap == 100
    assert is_bullish is True
    
    # Stale test
    now_stale = parse_timestamp("2023-01-01T10:31:00Z")
    price, vwap, is_bullish, error = get_spy_regime(states, now_stale)
    assert error == "spy_regime_stale"
