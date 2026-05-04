import os
import sys
import time
import asyncio
import threading
import urllib.request
import json
import random
import traceback
import math
import requests
from datetime import datetime, time as datetime_time, timedelta
from collections import deque
import pytz
import logging

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, TakeProfitRequest, StopLossRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, QueryOrderStatus, OrderStatus, PositionSide
from alpaca.data.live import StockDataStream
from alpaca.data.models import Bar, Trade, Quote
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alpaca.trading.enums import AssetClass

try:
    from alpaca.trading.requests import TrailingStopOrderRequest
except ImportError:
    TrailingStopOrderRequest = None

try:
    from alpaca.data.requests import StockLatestQuoteRequest
except ImportError:
    StockLatestQuoteRequest = None


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Alpaca Credentials
API_KEY = os.environ.get("APCA_API_KEY_ID")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY")

if not API_KEY or not API_SECRET:
    logger.error("Alpaca API credentials not found in environment variables. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY.")
    sys.exit(1)

PAPER = True

# Initialize Clients
trading_client = TradingClient(API_KEY, API_SECRET, paper=PAPER)
data_stream = StockDataStream(API_KEY, API_SECRET)
historical_client = StockHistoricalDataClient(API_KEY, API_SECRET)

# Trading Parameters
MAX_DAILY_LOSS_PCT = 0.01
POSITION_SIZE_MIN_PCT = 0.05
POSITION_SIZE_MAX_PCT = 0.15
STOP_LOSS_PCT = 0.0075
TAKE_PROFIT_PCT = 0.015
MIN_STOCK_PRICE = 10.00
MAX_TOTAL_EXPOSURE_PCT = float(os.environ.get("MAX_TOTAL_EXPOSURE_PCT", "0.50"))
MAX_OPEN_POSITIONS = int(os.environ.get("MAX_OPEN_POSITIONS", "10"))
MAX_TRADE_RISK_PCT = float(os.environ.get("MAX_TRADE_RISK_PCT", "0.001"))
MAX_TOTAL_OPEN_RISK_PCT = float(os.environ.get("MAX_TOTAL_OPEN_RISK_PCT", "0.005"))
SPY_REGIME_MAX_AGE_SECONDS = int(os.environ.get("SPY_REGIME_MAX_AGE_SECONDS", "180"))
MAX_ENTRY_SLIPPAGE_BPS = float(os.environ.get("MAX_ENTRY_SLIPPAGE_BPS", "15"))
ENTRY_RECONCILE_TIMEOUT_SECONDS = int(os.environ.get("ENTRY_RECONCILE_TIMEOUT_SECONDS", "10"))
ENTRY_RECONCILE_POLL_SECONDS = float(os.environ.get("ENTRY_RECONCILE_POLL_SECONDS", "0.5"))
RUNNER_TRAIL_PERCENT = float(os.environ.get("RUNNER_TRAIL_PERCENT", "1.0"))
MAX_SPREAD_PCT = float(os.environ.get("MAX_SPREAD_PCT", "0.002"))
MIN_DOLLAR_VOLUME_1M = float(os.environ.get("MIN_DOLLAR_VOLUME_1M", "250000"))
MAX_BAR_RANGE_PCT = float(os.environ.get("MAX_BAR_RANGE_PCT", "0.03"))
MIN_DIRECTIONAL_CLOSE_LOCATION = float(os.environ.get("MIN_DIRECTIONAL_CLOSE_LOCATION", "0.65"))
VOLATILITY_STOP_MULTIPLIER = float(os.environ.get("VOLATILITY_STOP_MULTIPLIER", "1.25"))
MIN_DYNAMIC_STOP_LOSS_PCT = float(os.environ.get("MIN_DYNAMIC_STOP_LOSS_PCT", "0.005"))
MAX_DYNAMIC_STOP_LOSS_PCT = float(os.environ.get("MAX_DYNAMIC_STOP_LOSS_PCT", "0.02"))
TAKE_PROFIT_R_MULTIPLE = float(os.environ.get("TAKE_PROFIT_R_MULTIPLE", "2.0"))
MAX_DYNAMIC_TAKE_PROFIT_PCT = float(os.environ.get("MAX_DYNAMIC_TAKE_PROFIT_PCT", "0.03"))
SYMBOL_COOLDOWN_MINUTES = float(os.environ.get("SYMBOL_COOLDOWN_MINUTES", "30"))
MAX_TRADES_PER_SYMBOL_PER_DAY = int(os.environ.get("MAX_TRADES_PER_SYMBOL_PER_DAY", "0"))
TRADE_EVENT_LOG_FILE = os.environ.get(
    "ALPACA_TRADE_EVENT_LOG_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "trade_events.jsonl")
)
DAILY_SUMMARY_FILE = os.environ.get(
    "ALPACA_DAILY_SUMMARY_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "daily_summary.json")
)
ABNORMAL_ALERT_COOLDOWN_SECONDS = int(os.environ.get("ABNORMAL_ALERT_COOLDOWN_SECONDS", "900"))
DAILY_STATE_FILE = os.environ.get(
    "ALPACA_DAILY_STATE_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".trading_state.json")
)
TIMEZONE = pytz.timezone('America/New_York')

# Trading Hours
START_TIME = datetime_time(10, 0)
STOP_ENTRIES_TIME = datetime_time(15, 0)
FLATTEN_TIME = datetime_time(15, 45)

# Global State
initial_equity = 0.0
market_data_state = {}
asset_shortable_cache = {}
trading_halted_today = False
current_trading_day = None

# Thread safety lock for state mutated by both the websocket loop and the async loop
state_lock = threading.RLock()
observability_lock = threading.Lock()

# New state for management
micro_state = {}
position_entry_times = {}
position_hwm = {}
runner_active = {}
runner_eligible = set()
pending_entries = {}
pending_entry_values = {}
pending_entry_risks = {}
symbol_cooldowns = {}
symbol_trade_counts = {}
closing_symbols = set()
observability_stats = {}
abnormal_alert_timestamps = {}

def set_trading_halted(value=True, reason=None):
    global trading_halted_today
    with state_lock:
        trading_halted_today = value
    persist_daily_state(reason if value else None)

def read_daily_state_file():
    try:
        with open(DAILY_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.error(f"Error reading daily trading state file: {e}")
        return {}

def write_daily_state_file(payload):
    try:
        state_dir = os.path.dirname(DAILY_STATE_FILE)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
        tmp_path = f"{DAILY_STATE_FILE}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, DAILY_STATE_FILE)
    except Exception as e:
        logger.error(f"Error writing daily trading state file: {e}")

def persist_daily_state(halt_reason=None):
    with state_lock:
        trading_day = current_trading_day.isoformat() if current_trading_day else None
        equity = initial_equity
        halted = trading_halted_today

    if not trading_day:
        return

    existing_state = read_daily_state_file()
    if halt_reason is None and halted:
        halt_reason = existing_state.get("halt_reason")

    write_daily_state_file({
        "trading_day": trading_day,
        "initial_equity": equity,
        "trading_halted_today": halted,
        "halt_reason": halt_reason if halted else None,
        "updated_at": datetime.now(TIMEZONE).isoformat()
    })

def initialize_daily_state(current_equity):
    global initial_equity, trading_halted_today, current_trading_day
    today = get_current_ny_date()
    state = read_daily_state_file()
    persisted_initial_equity = safe_float(state.get("initial_equity"))
    if state.get("trading_day") == today.isoformat() and persisted_initial_equity > 0:
        reset_observability_stats()
        with state_lock:
            initial_equity = persisted_initial_equity
            trading_halted_today = bool(state.get("trading_halted_today", False))
            current_trading_day = today
        logger.info(
            f"Loaded persisted daily trading state. Initial Equity: ${initial_equity:.2f}, "
            f"Halted: {trading_halted_today}"
        )
        if trading_halted_today:
            logger.error(f"Trading is halted for {today}; reason: {state.get('halt_reason') or 'unknown'}")
        return

    reset_daily_state(current_equity)

def json_safe(value):
    if isinstance(value, (datetime, )):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if hasattr(value, "value"):
        return value.value
    return str(value)

def ensure_parent_dir(file_path):
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

def reset_observability_stats():
    with observability_lock:
        observability_stats.clear()
        observability_stats.update({
            "signals_detected": 0,
            "signals_rejected": 0,
            "entries_submitted": 0,
            "entries_confirmed": 0,
            "entries_failed": 0,
            "exits_requested": 0,
            "positions_closed": 0,
            "abnormal_alerts": 0,
            "rejections_by_reason": {},
            "entries_by_symbol": {},
            "exits_by_reason": {}
        })

def increment_observability_stat(name, amount=1):
    with observability_lock:
        observability_stats[name] = observability_stats.get(name, 0) + amount

def increment_nested_observability_stat(group, key, amount=1):
    with observability_lock:
        values = observability_stats.setdefault(group, {})
        values[key] = values.get(key, 0) + amount

def get_observability_snapshot():
    with observability_lock:
        return json.loads(json.dumps(observability_stats))

def log_trade_event(event_type, symbol=None, **fields):
    trading_day = current_trading_day.isoformat() if current_trading_day else get_current_ny_date().isoformat()
    event = {
        "timestamp": datetime.now(TIMEZONE).isoformat(),
        "trading_day": trading_day,
        "event_type": event_type
    }
    if symbol:
        event["symbol"] = symbol
    event.update(fields)

    try:
        ensure_parent_dir(TRADE_EVENT_LOG_FILE)
        with open(TRADE_EVENT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=json_safe, sort_keys=True) + "\n")
    except Exception as e:
        logger.error(f"Error writing trade event log: {e}")

def log_signal_rejection(symbol, reason, **fields):
    increment_observability_stat("signals_rejected")
    increment_nested_observability_stat("rejections_by_reason", reason)
    log_trade_event("signal_rejected", symbol, reason=reason, **fields)

def send_rate_limited_alert(key, message):
    now_monotonic = time.monotonic()
    with observability_lock:
        last_alert_at = abnormal_alert_timestamps.get(key, 0)
        if now_monotonic - last_alert_at < ABNORMAL_ALERT_COOLDOWN_SECONDS:
            return False
        abnormal_alert_timestamps[key] = now_monotonic
        observability_stats["abnormal_alerts"] = observability_stats.get("abnormal_alerts", 0) + 1

    log_trade_event("abnormal_state", reason=key, message=message)
    send_telegram_alert(message)
    return True

def write_daily_summary(reason, current_equity=None):
    summary = {
        "timestamp": datetime.now(TIMEZONE).isoformat(),
        "trading_day": current_trading_day.isoformat() if current_trading_day else get_current_ny_date().isoformat(),
        "reason": reason,
        "initial_equity": initial_equity,
        "current_equity": current_equity,
        "daily_pnl": (current_equity - initial_equity) if current_equity is not None and initial_equity else None,
        "daily_pnl_pct": ((current_equity - initial_equity) / initial_equity) if current_equity is not None and initial_equity else None,
        "stats": get_observability_snapshot()
    }

    try:
        ensure_parent_dir(DAILY_SUMMARY_FILE)
        with open(DAILY_SUMMARY_FILE, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, sort_keys=True, default=json_safe)
            f.write("\n")
    except Exception as e:
        logger.error(f"Error writing daily summary: {e}")

    log_trade_event("daily_summary", **summary)
    logger.info(f"Daily summary written for {summary['trading_day']} ({reason}).")

def get_account_equity_safely():
    try:
        account = trading_client.get_account()
        return float(account.equity)
    except Exception as e:
        logger.error(f"Error fetching account equity for summary: {e}")
        return None

def as_ny_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return TIMEZONE.localize(value)
    return value.astimezone(TIMEZONE)

def get_flatten_deadline(clock):
    next_close = as_ny_datetime(getattr(clock, "next_close", None))
    if next_close:
        return next_close - timedelta(minutes=15)
    today = datetime.now(TIMEZONE)
    return today.replace(hour=FLATTEN_TIME.hour, minute=FLATTEN_TIME.minute, second=0, microsecond=0)

def get_entry_stop_deadline(clock):
    next_close = as_ny_datetime(getattr(clock, "next_close", None))
    if next_close:
        return next_close - timedelta(hours=1)
    today = datetime.now(TIMEZONE)
    return today.replace(hour=STOP_ENTRIES_TIME.hour, minute=STOP_ENTRIES_TIME.minute, second=0, microsecond=0)

def get_open_orders_for_symbol(symbol):
    return trading_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol]))

def get_stock_positions():
    positions = trading_client.get_all_positions()
    return [p for p in positions if is_stock_position(p)]

def wait_until_symbol_flat(symbol, timeout_seconds=60):
    deadline = time.monotonic() + timeout_seconds
    last_positions = []
    last_orders = []
    while time.monotonic() < deadline:
        last_positions = [p for p in get_stock_positions() if p.symbol == symbol]
        last_orders = get_open_orders_for_symbol(symbol)
        if not last_positions and not last_orders:
            return True
        time.sleep(2)
    logger.error(f"{symbol} still has exposure after close attempt. Positions: {last_positions}, Orders: {last_orders}")
    return False

def wait_until_symbol_no_position(symbol, timeout_seconds=60):
    deadline = time.monotonic() + timeout_seconds
    last_positions = []
    while time.monotonic() < deadline:
        last_positions = [p for p in get_stock_positions() if p.symbol == symbol]
        if not last_positions:
            return True
        time.sleep(2)
    logger.error(f"{symbol} still has an open position after close attempt. Positions: {last_positions}")
    return False

def cancel_open_orders_for_symbol(symbol):
    canceled_order_ids = []
    try:
        open_orders = get_open_orders_for_symbol(symbol)
        for order in open_orders:
            try:
                trading_client.cancel_order_by_id(order_id=order.id)
                canceled_order_ids.append(order.id)
            except Exception as e:
                logger.error(f"Error canceling order {order.id} for {symbol}: {e}")

        if canceled_order_ids:
            for _ in range(10):
                remaining_orders = get_open_orders_for_symbol(symbol)
                if not remaining_orders:
                    break
                time.sleep(0.5)
    except Exception as e:
        logger.error(f"Error fetching/canceling orders for {symbol}: {e}")
    return canceled_order_ids

def wait_until_flat(timeout_seconds=90):
    deadline = time.monotonic() + timeout_seconds
    last_positions = []
    last_orders = []
    while time.monotonic() < deadline:
        last_positions = get_stock_positions()
        last_orders = trading_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
        if not last_positions and not last_orders:
            return True
        time.sleep(2)
    logger.error(f"Account still has exposure after flatten attempt. Positions: {last_positions}, Orders: {last_orders}")
    return False

def current_reserved_entry_value(exclude_symbol=None, live_symbols=None):
    live_symbols = live_symbols or set()
    with state_lock:
        return sum(
            value for sym, value in pending_entry_values.items()
            if sym != exclude_symbol and sym not in live_symbols
        )

def current_reserved_entry_risk(exclude_symbol=None, live_symbols=None):
    live_symbols = live_symbols or set()
    with state_lock:
        return sum(
            value for sym, value in pending_entry_risks.items()
            if sym != exclude_symbol and sym not in live_symbols
        )

def current_pending_entry_count(live_symbols=None):
    live_symbols = live_symbols or set()
    with state_lock:
        return sum(1 for sym in pending_entry_values if sym not in live_symbols)

def release_entry_reservation(symbol):
    with state_lock:
        pending_entries.pop(symbol, None)
        pending_entry_values.pop(symbol, None)
        pending_entry_risks.pop(symbol, None)

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def estimate_entry_stop_risk(target_value, current_price, stop_loss_pct=STOP_LOSS_PCT):
    current_price = safe_float(current_price)
    if current_price <= 0:
        return 0.0
    qty = int(target_value / current_price)
    return qty * current_price * stop_loss_pct

def estimate_position_stop_risk(position, open_orders):
    qty = abs(safe_float(getattr(position, "qty", None)))
    avg_entry_price = safe_float(getattr(position, "avg_entry_price", None))
    if qty <= 0 or avg_entry_price <= 0:
        return 0.0

    is_long = is_long_position(position)
    expected_stop_side = OrderSide.SELL if is_long else OrderSide.BUY
    symbol = position.symbol
    covered_qty = 0.0
    risk = 0.0

    stop_orders = [
        o for o in open_orders
        if o.symbol == symbol
        and enum_equals(getattr(o, "side", None), expected_stop_side)
        and safe_float(getattr(o, "stop_price", None)) > 0
    ]

    for order in stop_orders:
        remaining_qty = max(qty - covered_qty, 0.0)
        if remaining_qty <= 0:
            break
        order_qty = abs(safe_float(getattr(order, "qty", None), remaining_qty))
        order_qty = min(order_qty, remaining_qty)
        stop_price = safe_float(getattr(order, "stop_price", None))
        if is_long:
            risk_per_share = max(avg_entry_price - stop_price, 0.0)
        else:
            risk_per_share = max(stop_price - avg_entry_price, 0.0)
        risk += order_qty * risk_per_share
        covered_qty += order_qty

    unprotected_qty = max(qty - covered_qty, 0.0)
    if unprotected_qty > 0:
        risk += unprotected_qty * avg_entry_price * STOP_LOSS_PCT

    return risk

def estimate_total_open_stop_risk(stock_positions, open_orders):
    return sum(estimate_position_stop_risk(p, open_orders) for p in stock_positions)

def is_symbol_trade_allowed(symbol, now=None):
    now = now or datetime.now(TIMEZONE)
    with state_lock:
        cooldown_until = symbol_cooldowns.get(symbol)
        trade_count = symbol_trade_counts.get(symbol, 0)

    if cooldown_until and now < as_ny_datetime(cooldown_until):
        logger.info(f"Skipping {symbol} signal - symbol cooldown active until {as_ny_datetime(cooldown_until)}.")
        log_signal_rejection(symbol, "symbol_cooldown", cooldown_until=as_ny_datetime(cooldown_until))
        return False

    if MAX_TRADES_PER_SYMBOL_PER_DAY > 0 and trade_count >= MAX_TRADES_PER_SYMBOL_PER_DAY:
        logger.info(f"Skipping {symbol} signal - max daily symbol trades reached ({MAX_TRADES_PER_SYMBOL_PER_DAY}).")
        log_signal_rejection(symbol, "max_symbol_trades", trade_count=trade_count, max_trades=MAX_TRADES_PER_SYMBOL_PER_DAY)
        return False

    return True

def register_symbol_entry(symbol):
    with state_lock:
        symbol_trade_counts[symbol] = symbol_trade_counts.get(symbol, 0) + 1
        trade_count = symbol_trade_counts[symbol]
    increment_nested_observability_stat("entries_by_symbol", symbol)
    log_trade_event("symbol_entry_registered", symbol, trade_count=trade_count)

def register_symbol_exit(symbol, reason="trade_completed"):
    cooldown_until = None
    if SYMBOL_COOLDOWN_MINUTES > 0:
        cooldown_until = datetime.now(TIMEZONE) + timedelta(minutes=SYMBOL_COOLDOWN_MINUTES)
        with state_lock:
            symbol_cooldowns[symbol] = cooldown_until
        logger.info(f"Cooldown set for {symbol} until {cooldown_until} after {reason}.")
    increment_observability_stat("positions_closed")
    increment_nested_observability_stat("exits_by_reason", reason)
    log_trade_event("symbol_exit_registered", symbol, reason=reason, cooldown_until=cooldown_until)

def normalize_enum_value(value):
    if value is None:
        return ""
    raw_value = getattr(value, "value", value)
    return str(raw_value).lower()

def enum_equals(value, expected):
    return normalize_enum_value(value) == normalize_enum_value(expected)

def is_stock_position(position):
    return enum_equals(getattr(position, "asset_class", None), AssetClass.US_EQUITY)

def is_long_position(position):
    return enum_equals(getattr(position, "side", None), PositionSide.LONG)

def is_filled_order(order):
    return enum_equals(getattr(order, "status", None), OrderStatus.FILLED)

def is_order_accepted(order):
    if not getattr(order, "id", None):
        return False
    status = normalize_enum_value(getattr(order, "status", None))
    if not status:
        return True
    return status in {
        "accepted",
        "accepted_for_bidding",
        "new",
        "pending_new",
        "partially_filled",
        "filled"
    }

def order_qty(order, default=0.0):
    return abs(safe_float(getattr(order, "qty", None), default))

def entry_limit_price(current_price, is_long):
    slippage_multiplier = MAX_ENTRY_SLIPPAGE_BPS / 10000
    if is_long:
        return round(current_price * (1 + slippage_multiplier), 2)
    return round(current_price * (1 - slippage_multiplier), 2)

def reconcile_submitted_entry(symbol, entry_side, expected_qty, timeout_seconds=ENTRY_RECONCILE_TIMEOUT_SECONDS):
    deadline = time.monotonic() + timeout_seconds
    last_position_qty = 0.0
    last_open_entry_qty = 0.0

    while time.monotonic() < deadline:
        try:
            positions = [p for p in get_stock_positions() if p.symbol == symbol]
            open_orders = get_open_orders_for_symbol(symbol)
        except Exception as e:
            logger.error(f"Error reconciling submitted entry for {symbol}: {e}")
            time.sleep(ENTRY_RECONCILE_POLL_SECONDS)
            continue

        last_position_qty = sum(abs(safe_float(getattr(p, "qty", None))) for p in positions)
        last_open_entry_qty = sum(
            order_qty(o)
            for o in open_orders
            if normalize_enum_value(o.side) == normalize_enum_value(entry_side)
            and getattr(o, "limit_price", None) is not None
        )

        if last_position_qty + last_open_entry_qty >= expected_qty:
            return True

        time.sleep(ENTRY_RECONCILE_POLL_SECONDS)

    logger.error(
        f"Entry reconciliation failed for {symbol}. Expected qty: {expected_qty}, "
        f"Position qty: {last_position_qty}, Open entry qty: {last_open_entry_qty}"
    )
    return False

def is_trailing_stop_order(order):
    order_type = normalize_enum_value(getattr(order, "type", None))
    return (
        "trailing" in order_type
        or getattr(order, "trail_percent", None) is not None
        or getattr(order, "trail_price", None) is not None
    )

def position_has_protective_order(position, open_orders):
    required_qty = abs(safe_float(getattr(position, "qty", None)))
    if required_qty <= 0:
        return False

    is_long = is_long_position(position)
    exit_side = OrderSide.SELL if is_long else OrderSide.BUY
    covered_qty = 0.0
    for order in open_orders:
        if order.symbol != position.symbol:
            continue
        if normalize_enum_value(order.side) != normalize_enum_value(exit_side):
            continue
        if getattr(order, "stop_price", None) is not None or is_trailing_stop_order(order):
            covered_qty += order_qty(order)
    return covered_qty >= required_qty

def promote_runner_to_native_trailing_stop(symbol, position, open_orders):
    if TrailingStopOrderRequest is None:
        logger.warning("Native trailing stop request is unavailable in this Alpaca SDK version; using programmatic runner stop.")
        return False, False

    qty = abs(safe_float(getattr(position, "qty", None)))
    if qty <= 0:
        return False, False

    is_long = is_long_position(position)
    exit_side = OrderSide.SELL if is_long else OrderSide.BUY
    symbol_orders = [
        o for o in open_orders
        if o.symbol == symbol and normalize_enum_value(o.side) == normalize_enum_value(exit_side)
    ]

    if any(is_trailing_stop_order(o) for o in symbol_orders):
        return True, False

    static_stop_orders = [
        o for o in symbol_orders
        if getattr(o, "stop_price", None) is not None and not is_trailing_stop_order(o)
    ]
    has_existing_protection = position_has_protective_order(position, open_orders)

    try:
        trailing_req = TrailingStopOrderRequest(
            symbol=symbol,
            qty=qty,
            side=exit_side,
            time_in_force=TimeInForce.DAY,
            trail_percent=RUNNER_TRAIL_PERCENT
        )
        submitted = trading_client.submit_order(order_data=trailing_req)
        if not is_order_accepted(submitted):
            logger.error(f"Native trailing stop for {symbol} was not accepted: {submitted}")
            return False, not has_existing_protection

        for order in static_stop_orders:
            try:
                trading_client.cancel_order_by_id(order_id=order.id)
            except Exception as e_cancel:
                logger.error(f"Error canceling replaced static stop {order.id} for {symbol}: {e_cancel}")
                send_telegram_alert(f"Native trailing stop is active for {symbol}, but static stop {order.id} could not be canceled: {e_cancel}")

        logger.info(f"Native trailing stop submitted for {symbol} runner. Qty: {qty:g}, Trail: {RUNNER_TRAIL_PERCENT:.2f}%")
        return True, False
    except Exception as e:
        logger.error(f"Error promoting {symbol} runner to native trailing stop: {e}")
        send_telegram_alert(f"Failed to protect {symbol} runner with native trailing stop: {e}")
        return False, not has_existing_protection

def mark_symbol_closing(symbol):
    with state_lock:
        if symbol in closing_symbols:
            return False
        closing_symbols.add(symbol)
        return True

def release_symbol_closing(symbol):
    with state_lock:
        closing_symbols.discard(symbol)

def create_background_task(coro, description):
    task = asyncio.create_task(coro)
    def log_task_result(done_task):
        try:
            done_task.result()
        except Exception as e:
            logger.error(f"Background task failed ({description}): {e}")
    task.add_done_callback(log_task_result)
    return task

def schedule_symbol_close(symbol):
    if not mark_symbol_closing(symbol):
        logger.info(f"Close already in progress for {symbol}; skipping duplicate close request.")
        return False
    try:
        create_background_task(
            asyncio.to_thread(lambda s=symbol: close_position_and_cancel_orders(s)),
            f"close {symbol}"
        )
        return True
    except Exception:
        release_symbol_closing(symbol)
        raise

def daily_loss_breached(current_equity):
    if initial_equity <= 0:
        logger.error(f"initial_equity is {initial_equity} (<= 0). Halting trading out of an abundance of caution.")
        return True
    return ((initial_equity - current_equity) / initial_equity) >= MAX_DAILY_LOSS_PCT

def take_profit_filled_today(symbol, is_long, now, entry_time=None):
    expected_tp_side = OrderSide.SELL if is_long else OrderSide.BUY
    entry_time = as_ny_datetime(entry_time) if entry_time else None
    req = GetOrdersRequest(
        status=QueryOrderStatus.CLOSED,
        symbols=[symbol],
        limit=100,
        after=now.replace(hour=0, minute=0, second=0, microsecond=0)
    )
    closed_orders = trading_client.get_orders(req)
    return any(
        is_filled_order(o)
        and enum_equals(getattr(o, "side", None), expected_tp_side)
        and getattr(o, "limit_price", None) is not None
        and getattr(o, "filled_at", None)
        and (entry_time is None or as_ny_datetime(o.filled_at) >= entry_time)
        for o in closed_orders
    )

def close_position_and_cancel_orders(symbol):
    logger.info(f"Closing position for {symbol}...")
    increment_observability_stat("exits_requested")
    log_trade_event("exit_requested", symbol, reason="close_position_and_cancel_orders")
    try:
        close_requested = False
        positions = [p for p in get_stock_positions() if p.symbol == symbol]

        if positions:
            try:
                # Try closing first so protective orders are not removed unless Alpaca requires it.
                trading_client.close_position(symbol_or_asset_id=symbol)
                close_requested = True
            except Exception as e_close:
                logger.error(f"Initial close failed for {symbol}; canceling orders before retry: {e_close}")
                cancel_open_orders_for_symbol(symbol)
                time.sleep(1)

                positions = [p for p in get_stock_positions() if p.symbol == symbol]
                if positions:
                    trading_client.close_position(symbol_or_asset_id=symbol)
                    close_requested = True
                else:
                    logger.info(f"No position remains for {symbol} after cancel attempt; verifying flat state.")
        else:
            logger.info(f"No open position for {symbol}; canceling any open orders.")

        if close_requested and not wait_until_symbol_no_position(symbol):
            send_telegram_alert(f"Failed to verify {symbol} position is closed; leaving protective orders intact.")
            return

        cancel_open_orders_for_symbol(symbol)

        if wait_until_symbol_flat(symbol, timeout_seconds=15):
            release_entry_reservation(symbol)
            with state_lock:
                position_entry_times.pop(symbol, None)
                position_hwm.pop(symbol, None)
                runner_active.pop(symbol, None)
                runner_eligible.discard(symbol)
            register_symbol_exit(symbol, "manual_or_risk_close")
            log_trade_event("position_closed", symbol, reason="manual_or_risk_close")
            logger.info(f"Position for {symbol} closed and orders canceled.")
        else:
            log_trade_event("exit_failed", symbol, reason="flat_verification_failed")
            send_telegram_alert(f"Failed to verify {symbol} is flat after close attempt.")
    except Exception as e:
        logger.error(f"Error closing position for {symbol}: {e}")
        log_trade_event("exit_failed", symbol, reason="close_exception", error=str(e))
        send_telegram_alert(f"Error closing {symbol}: {e}")
    finally:
        release_symbol_closing(symbol)

async def reserve_symbol_for_entry(symbol, target_size_pct, current_price, stop_loss_pct):
    global trading_halted_today
    with state_lock:
        if trading_halted_today:
            logger.info(f"Skipping {symbol} signal - trading is halted for the day.")
            log_signal_rejection(symbol, "trading_halted")
            return False
        if symbol in pending_entries:
            logger.info(f"Skipping {symbol} signal - entry already pending.")
            log_signal_rejection(symbol, "entry_already_pending")
            return False

    try:
        positions, symbol_open_orders, all_open_orders = await asyncio.gather(
            asyncio.to_thread(trading_client.get_all_positions),
            asyncio.to_thread(trading_client.get_orders, GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])),
            asyncio.to_thread(trading_client.get_orders, GetOrdersRequest(status=QueryOrderStatus.OPEN))
        )
    except Exception as e:
        logger.error(f"Error checking existing exposure for {symbol}: {e}")
        log_signal_rejection(symbol, "exposure_check_failed", error=str(e))
        return False

    has_position = any(p.symbol == symbol for p in positions)
    if has_position or symbol_open_orders:
        logger.info(f"Skipping {symbol} signal - existing position or open order found.")
        log_signal_rejection(symbol, "existing_exposure")
        return False

    try:
        account, clock = await asyncio.gather(
            asyncio.to_thread(trading_client.get_account),
            asyncio.to_thread(trading_client.get_clock)
        )
        current_equity = float(account.equity)
        available_buying_power = float(account.daytrading_buying_power) if float(account.daytrading_buying_power) > 0 else float(account.buying_power)
    except Exception as e:
        logger.error(f"Error checking account or clock for {symbol}: {e}")
        log_signal_rejection(symbol, "account_clock_check_failed", error=str(e))
        return False

    now_dt = datetime.now(TIMEZONE)
    if not clock.is_open or now_dt >= get_entry_stop_deadline(clock):
        logger.info(f"Skipping {symbol} signal - entry window is closed.")
        log_signal_rejection(symbol, "entry_window_closed")
        return False
    if now_dt >= get_flatten_deadline(clock):
        logger.info(f"Skipping {symbol} signal - flatten deadline has passed.")
        log_signal_rejection(symbol, "flatten_deadline_passed")
        return False
    if daily_loss_breached(current_equity):
        logger.error(f"Skipping {symbol} signal - daily loss limit already breached.")
        set_trading_halted(True, "daily_loss")
        log_signal_rejection(symbol, "daily_loss_breached", current_equity=current_equity, initial_equity=initial_equity)
        return False

    target_value = min(current_equity * target_size_pct, available_buying_power)
    stock_positions = [p for p in positions if is_stock_position(p)]
    current_exposure = sum(abs(float(p.market_value)) for p in stock_positions)
    reserved_exposure = current_reserved_entry_value()
    max_exposure = current_equity * MAX_TOTAL_EXPOSURE_PCT
    entry_stop_risk = estimate_entry_stop_risk(target_value, current_price, stop_loss_pct)
    current_stop_risk = estimate_total_open_stop_risk(stock_positions, all_open_orders)
    reserved_stop_risk = current_reserved_entry_risk()
    max_trade_risk = current_equity * MAX_TRADE_RISK_PCT
    max_total_open_risk = current_equity * MAX_TOTAL_OPEN_RISK_PCT

    if entry_stop_risk <= 0:
        logger.info(f"Skipping {symbol} signal - estimated entry risk is zero or price is invalid.")
        log_signal_rejection(symbol, "invalid_entry_risk", entry_stop_risk=entry_stop_risk, current_price=current_price)
        return False

    if entry_stop_risk > max_trade_risk:
        logger.info(
            f"Skipping {symbol} signal - per-trade risk cap reached. "
            f"Risk: ${entry_stop_risk:.2f}, Cap: ${max_trade_risk:.2f}"
        )
        log_signal_rejection(symbol, "trade_risk_cap", entry_stop_risk=entry_stop_risk, max_trade_risk=max_trade_risk)
        return False

    if current_stop_risk + reserved_stop_risk + entry_stop_risk > max_total_open_risk:
        logger.info(
            f"Skipping {symbol} signal - aggregate stop-risk cap reached. "
            f"Current: ${current_stop_risk:.2f}, Reserved: ${reserved_stop_risk:.2f}, "
            f"Entry: ${entry_stop_risk:.2f}, Cap: ${max_total_open_risk:.2f}"
        )
        log_signal_rejection(
            symbol,
            "aggregate_risk_cap",
            current_stop_risk=current_stop_risk,
            reserved_stop_risk=reserved_stop_risk,
            entry_stop_risk=entry_stop_risk,
            max_total_open_risk=max_total_open_risk
        )
        return False

    if len(stock_positions) + current_pending_entry_count() >= MAX_OPEN_POSITIONS:
        logger.info(f"Skipping {symbol} signal - max open positions reached ({MAX_OPEN_POSITIONS}).")
        log_signal_rejection(symbol, "max_open_positions", max_open_positions=MAX_OPEN_POSITIONS)
        return False

    if current_exposure + reserved_exposure + target_value > max_exposure:
        logger.info(
            f"Skipping {symbol} signal - exposure cap reached. "
            f"Current: ${current_exposure:.2f}, Reserved: ${reserved_exposure:.2f}, "
            f"Target: ${target_value:.2f}, Cap: ${max_exposure:.2f}"
        )
        log_signal_rejection(symbol, "exposure_cap", current_exposure=current_exposure, reserved_exposure=reserved_exposure, target_value=target_value, max_exposure=max_exposure)
        return False

    with state_lock:
        if symbol in pending_entries:
            logger.info(f"Skipping {symbol} signal - entry already pending.")
            log_signal_rejection(symbol, "entry_already_pending")
            return False
        latest_pending_count = len(pending_entry_values)
        if latest_pending_count + len(stock_positions) >= MAX_OPEN_POSITIONS:
            logger.info(f"Skipping {symbol} signal - max open positions reached ({MAX_OPEN_POSITIONS}).")
            log_signal_rejection(symbol, "max_open_positions", max_open_positions=MAX_OPEN_POSITIONS)
            return False
        latest_reserved_exposure = sum(pending_entry_values.values())
        if current_exposure + latest_reserved_exposure + target_value > max_exposure:
            logger.info(f"Skipping {symbol} signal - exposure cap reached during reservation.")
            log_signal_rejection(symbol, "exposure_cap_during_reservation", current_exposure=current_exposure, reserved_exposure=latest_reserved_exposure, target_value=target_value, max_exposure=max_exposure)
            return False
        latest_reserved_stop_risk = sum(pending_entry_risks.values())
        if current_stop_risk + latest_reserved_stop_risk + entry_stop_risk > max_total_open_risk:
            logger.info(f"Skipping {symbol} signal - aggregate stop-risk cap reached during reservation.")
            log_signal_rejection(symbol, "aggregate_risk_cap_during_reservation", current_stop_risk=current_stop_risk, reserved_stop_risk=latest_reserved_stop_risk, entry_stop_risk=entry_stop_risk, max_total_open_risk=max_total_open_risk)
            return False
        pending_entries[symbol] = datetime.now(TIMEZONE)
        pending_entry_values[symbol] = target_value
        pending_entry_risks[symbol] = entry_stop_risk
    return True

def get_current_ny_time():
    return datetime.now(TIMEZONE).time()

def get_current_ny_date():
    return datetime.now(TIMEZONE).date()

def get_bar_timestamp(bar):
    timestamp = getattr(bar, "timestamp", None)
    if timestamp:
        return as_ny_datetime(timestamp)
    return datetime.now(TIMEZONE)

def get_fresh_spy_regime(now=None):
    now = now or datetime.now(TIMEZONE)
    with state_lock:
        spy_state = market_data_state.get("SPY")
        if not spy_state:
            return None, None, None, "missing SPY state"

        spy_price = spy_state.get("last_price")
        spy_cum_vol = spy_state.get("cum_vol", 0)
        spy_cum_pv = spy_state.get("cum_pv", 0)
        spy_last_bar_at = spy_state.get("last_bar_at")

    if not spy_price or spy_cum_vol <= 0:
        return None, None, None, "missing SPY VWAP inputs"
    if not spy_last_bar_at:
        return None, None, None, "missing SPY timestamp"

    spy_last_bar_at = as_ny_datetime(spy_last_bar_at)
    age_seconds = (now - spy_last_bar_at).total_seconds()
    if age_seconds > SPY_REGIME_MAX_AGE_SECONDS:
        return None, None, None, f"stale SPY data ({age_seconds:.0f}s old)"

    spy_vwap = spy_cum_pv / spy_cum_vol
    return spy_price, spy_vwap, spy_price > spy_vwap, None

def get_dynamic_watchlist(api_key, api_secret, target_count=14, min_price=10.0):
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }
    url_active = "https://data.alpaca.markets/v1beta1/screener/stocks/most-actives?by=volume&top=100"
    try:
        res = requests.get(url_active, headers=headers, timeout=10)
        res.raise_for_status()
        active_symbols = [item["symbol"] for item in res.json().get("most_actives", [])]
    except Exception as e:
        logger.error(f"Failed to fetch most active symbols: {e}")
        return ["SPY", "QQQ", "IWM", "DIA"]
        
    if not active_symbols:
        return ["SPY", "QQQ"]
        
    chunk_str = ",".join(active_symbols)
    url_snapshots = f"https://data.alpaca.markets/v2/stocks/snapshots?symbols={chunk_str}"
    
    valid_symbols = []
    try:
        snap_res = requests.get(url_snapshots, headers=headers, timeout=10)
        snap_res.raise_for_status()
        snapshots = snap_res.json()
        
        for sym in active_symbols:
            data = snapshots.get(sym)
            if data and data.get("latestTrade"):
                price = data["latestTrade"].get("p", 0.0)
                if price >= min_price:
                    valid_symbols.append(sym)
                    if len(valid_symbols) == target_count:
                        break
    except Exception as e:
        logger.error(f"Failed to fetch snapshots: {e}")
        return active_symbols[:target_count]
        
    return valid_symbols

def reset_daily_state(current_equity):
    global initial_equity, market_data_state, trading_halted_today, current_trading_day
    global position_entry_times, position_hwm, runner_active, runner_eligible, pending_entries, pending_entry_values, pending_entry_risks, symbol_cooldowns, symbol_trade_counts, closing_symbols
    logger.info("Executing daily state reset...")
    reset_observability_stats()
    with state_lock:
        initial_equity = current_equity
        market_data_state.clear()
        position_entry_times.clear()
        position_hwm.clear()
        runner_active.clear()
        runner_eligible.clear()
        pending_entries.clear()
        pending_entry_values.clear()
        pending_entry_risks.clear()
        symbol_cooldowns.clear()
        symbol_trade_counts.clear()
        closing_symbols.clear()
        trading_halted_today = False
        current_trading_day = get_current_ny_date()
    persist_daily_state()

def flatten_all():
    logger.info("Flattening all positions...")
    increment_observability_stat("exits_requested")
    log_trade_event("flatten_requested")
    trading_client.close_all_positions(cancel_orders=True)
    if wait_until_flat():
        with state_lock:
            position_entry_times.clear()
            position_hwm.clear()
            runner_active.clear()
            runner_eligible.clear()
            pending_entries.clear()
            pending_entry_values.clear()
            pending_entry_risks.clear()
            symbol_cooldowns.clear()
            closing_symbols.clear()
        logger.info("All positions closed.")
        log_trade_event("flatten_confirmed")
        return True
    log_trade_event("flatten_failed", reason="flat_verification_failed")
    send_telegram_alert("Failed to verify account is flat after flatten_all().")
    return False

def cleanup_trade_state_after_order_snapshot(stock_positions, all_pending_orders, open_orders_reliable, now):
    if not open_orders_reliable:
        return []

    current_positions = {p.symbol for p in stock_positions}
    position_side_by_symbol = {p.symbol: p.side for p in stock_positions}
    open_order_symbols = {o.symbol for o in all_pending_orders}
    closed_symbols_for_cooldown = []

    with state_lock:
        # Clean up closed positions only when the open-order snapshot is reliable.
        for sym in list(position_entry_times.keys()):
            if sym not in current_positions and sym not in open_order_symbols:
                entry_t = as_ny_datetime(position_entry_times[sym])
                if (now - entry_t).total_seconds() > 30:
                    del position_entry_times[sym]
                    closed_symbols_for_cooldown.append(sym)
        for sym in list(position_hwm.keys()):
            if sym not in current_positions and sym not in open_order_symbols:
                del position_hwm[sym]
        for sym in list(runner_active.keys()):
            if sym not in current_positions and sym not in open_order_symbols:
                del runner_active[sym]
        for sym in list(runner_eligible):
            if sym not in current_positions and sym not in open_order_symbols:
                runner_eligible.discard(sym)
        for sym, pending_at in list(pending_entries.items()):
            if sym in current_positions:
                position_side = position_side_by_symbol.get(sym)
                entry_side = OrderSide.BUY if enum_equals(position_side, PositionSide.LONG) else OrderSide.SELL
                has_open_entry_order = any(
                    o.symbol == sym and normalize_enum_value(o.side) == normalize_enum_value(entry_side)
                    for o in all_pending_orders
                )
                if not has_open_entry_order:
                    pending_entry_values.pop(sym, None)
                    pending_entry_risks.pop(sym, None)
            elif sym not in open_order_symbols:
                if (now - pending_at).total_seconds() > 60:
                    del pending_entries[sym]
                    pending_entry_values.pop(sym, None)
                    pending_entry_risks.pop(sym, None)

    return closed_symbols_for_cooldown

def submit_bracket_order(symbol, current_price, target_size_pct, stop_loss_pct=STOP_LOSS_PCT, take_profit_pct=TAKE_PROFIT_PCT, is_long=True):
    global trading_halted_today
    account = trading_client.get_account()
    current_equity = float(account.equity)
    if daily_loss_breached(current_equity):
        set_trading_halted(True, "daily_loss")
        logger.error(f"Aborting {symbol} order - daily loss limit already breached.")
        return False
    
    # Use buying_power or daytrading_buying_power instead of cash to account for margin
    available_buying_power = float(account.daytrading_buying_power) if float(account.daytrading_buying_power) > 0 else float(account.buying_power)
    
    target_value = current_equity * target_size_pct
    if target_value > available_buying_power:
        logger.info(f"Capping order size to avoid margin issues. Target: ${target_value:.2f}, Buying Power: ${available_buying_power:.2f}")
        target_value = available_buying_power
        
    if current_price <= 0:
        logger.warning(f"Invalid price for {symbol}: {current_price}. Aborting order.")
        return False
        
    qty = int(target_value / current_price)
    
    if qty <= 0:
        logger.warning(f"Not enough buying power or quantity too low to trade {symbol}. Qty: {qty}")
        return False

    if qty == 1:
        qty1 = 1
        qty2 = 0
    else:
        qty1 = qty // 2
        qty2 = qty - qty1

    if is_long:
        take_profit_price = round(current_price * (1 + take_profit_pct), 2)
        stop_loss_price = round(current_price * (1 - stop_loss_pct), 2)
        side = OrderSide.BUY
    else:
        take_profit_price = round(current_price * (1 - take_profit_pct), 2)
        stop_loss_price = round(current_price * (1 + stop_loss_pct), 2)
        side = OrderSide.SELL
    limit_price = entry_limit_price(current_price, is_long)

    # Order 1: 50% with TP and SL. Marketable limit guards against excessive slippage.
    req1 = LimitOrderRequest(
        symbol=symbol,
        qty=qty1,
        side=side,
        limit_price=limit_price,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=take_profit_price),
        stop_loss=StopLossRequest(stop_price=stop_loss_price)
    )

    try:
        submitted_qty = qty1
        order1 = trading_client.submit_order(order_data=req1)
        if not is_order_accepted(order1):
            logger.error(f"Primary entry order for {symbol} was not accepted: {order1}")
            increment_observability_stat("entries_failed")
            log_trade_event("entry_failed", symbol, reason="primary_order_not_accepted", order=order1)
            return False
        order_ids = [getattr(order1, "id", None)]
        increment_observability_stat("entries_submitted")
        with state_lock:
            position_entry_times[symbol] = datetime.now(TIMEZONE)
        runner_enabled = False
        if qty2 > 0:
            # Order 2: 50% with just SL (OTO), profit handled by trailing stop logic after first TP fills.
            req2 = LimitOrderRequest(
                symbol=symbol,
                qty=qty2,
                side=side,
                limit_price=limit_price,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.OTO,
                stop_loss=StopLossRequest(stop_price=stop_loss_price)
            )
            try:
                order2 = trading_client.submit_order(order_data=req2)
                if is_order_accepted(order2):
                    submitted_qty += qty2
                    runner_enabled = True
                    order_ids.append(getattr(order2, "id", None))
                else:
                    logger.error(f"Runner entry order for {symbol} was not accepted: {order2}. Continuing with req1 only; runner disabled.")
                    log_trade_event("entry_warning", symbol, reason="runner_order_not_accepted", order=order2)
                    send_telegram_alert(f"Runner entry order for {symbol} was not accepted; runner disabled.")
            except Exception as e2:
                logger.error(f"Error submitting req2 for {symbol}: {e2}. Continuing with req1 only; runner disabled.")
                log_trade_event("entry_warning", symbol, reason="runner_order_submit_error", error=str(e2))
                send_telegram_alert(f"Error submitting runner entry for {symbol}; runner disabled: {e2}")

        if not reconcile_submitted_entry(symbol, side, submitted_qty):
            increment_observability_stat("entries_failed")
            log_trade_event("entry_failed", symbol, reason="reconciliation_failed", expected_qty=submitted_qty, order_ids=order_ids)
            send_telegram_alert(f"Entry reconciliation failed for {symbol}; flattening/canceling symbol exposure.")
            close_position_and_cancel_orders(symbol)
            return False

        action = "Buy" if is_long else "Short"
        logger.info(
            f"EXECUTED: Split {action} {submitted_qty} {symbol} near {current_price}. "
            f"Entry Limit: {limit_price}, TP: {take_profit_price}, SL: {stop_loss_price}"
        )
        increment_observability_stat("entries_confirmed")
        log_trade_event(
            "entry_confirmed",
            symbol,
            side=side,
            submitted_qty=submitted_qty,
            signal_price=current_price,
            entry_limit_price=limit_price,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            target_size_pct=target_size_pct,
            runner_enabled=runner_enabled,
            order_ids=order_ids
        )
        with state_lock:
            pending_entry_values[symbol] = current_price * submitted_qty
            pending_entry_risks[symbol] = submitted_qty * current_price * stop_loss_pct
            if runner_enabled:
                runner_eligible.add(symbol)
            else:
                runner_eligible.discard(symbol)
        register_symbol_entry(symbol)
        return True
    except Exception as e:
        logger.error(f"Error submitting order for {symbol}: {e}")
        increment_observability_stat("entries_failed")
        log_trade_event("entry_failed", symbol, reason="submit_exception", error=str(e))
        return False

HFT_MIN_BURST_VOLUME = int(os.environ.get("HFT_MIN_BURST_VOLUME", "5000"))
HFT_IMBALANCE_THRESHOLD = float(os.environ.get("HFT_IMBALANCE_THRESHOLD", "0.80"))
HFT_TAKE_PROFIT_PCT = float(os.environ.get("HFT_TAKE_PROFIT_PCT", "0.002")) # 0.2%
HFT_STOP_LOSS_PCT = float(os.environ.get("HFT_STOP_LOSS_PCT", "0.002"))   # 0.1%

MAX_ORDERS_PER_MINUTE = 20
order_timestamps = deque(maxlen=MAX_ORDERS_PER_MINUTE)

def submit_hft_bracket_order(symbol, side, qty, limit_price, tp_price, sl_price, current_equity):
        
    req = LimitOrderRequest(
        symbol=symbol,
        qty=qty,
        side=side,
        limit_price=limit_price,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=tp_price),
        stop_loss=StopLossRequest(stop_price=sl_price)
    )

    try:
        order = trading_client.submit_order(order_data=req)
        if not is_order_accepted(order):
            logger.error(f"HFT entry order for {symbol} was not accepted: {order}")
            increment_observability_stat("entries_failed")
            log_trade_event("hft_entry_failed", symbol, reason="order_not_accepted", order=order)
            return False
            
        increment_observability_stat("entries_submitted")
        with state_lock:
            position_entry_times[symbol] = datetime.now(TIMEZONE)
            
        return True
    except Exception as e:
        logger.error(f"Error submitting HFT order for {symbol}: {e}")
        increment_observability_stat("entries_failed")
        log_trade_event("hft_entry_failed", symbol, reason="submit_exception", error=str(e))
        return False

async def evaluate_hft_entry(symbol, signal, price, quote):
    now = datetime.now(TIMEZONE)
    with state_lock:
        # Check API spam limits
        if len(order_timestamps) == MAX_ORDERS_PER_MINUTE:
            if (now - order_timestamps[0]).total_seconds() < 60:
                logger.info(f"Skipping HFT SIGNAL for {symbol} - rate limited.")
                return # Rate limited
                
        # Existing checks (e.g. max exposure, daily limits, symbol cooldowns)
        if not is_symbol_trade_allowed(symbol, now):
            return
            
        if symbol in pending_entries:
            logger.info(f"Skipping HFT {symbol} signal - entry already pending.")
            return

        # Temporarily lock symbol to prevent duplicate firing on the same tick burst
        symbol_cooldowns[symbol] = now + timedelta(seconds=15)
        order_timestamps.append(now)
        
    logger.info(f"HFT SIGNAL: {signal} {symbol} at {price}")
    
    try:
        positions, symbol_open_orders = await asyncio.gather(
            asyncio.to_thread(trading_client.get_all_positions),
            asyncio.to_thread(trading_client.get_orders, GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol]))
        )
    except Exception as e:
        logger.error(f"Error checking existing exposure for {symbol} HFT: {e}")
        return

    has_position = any(p.symbol == symbol for p in positions)
    if has_position or symbol_open_orders:
        logger.info(f"Skipping {symbol} HFT signal - existing position or open order found.")
        return
        
    stock_positions = [p for p in positions if is_stock_position(p)]
    if len(stock_positions) + current_pending_entry_count() >= MAX_OPEN_POSITIONS:
        logger.info(f"Skipping {symbol} HFT signal - max open positions reached.")
        return

    if signal == "SHORT":
        if not asset_shortable_cache.get(symbol, False):
            logger.info(f"Skipping HFT short signal for {symbol} - not shortable or not easy to borrow.")
            return
    
    # Calculate position size
    try:
        account = await asyncio.to_thread(trading_client.get_account)
    except Exception as e:
        logger.error(f"Error checking account for {symbol} HFT: {e}")
        return
        
    current_equity = float(account.equity)
    if daily_loss_breached(current_equity):
        set_trading_halted(True, "daily_loss")
        logger.error(f"Aborting {symbol} HFT order - daily loss limit already breached.")
        return
    target_value = current_equity * POSITION_SIZE_MIN_PCT
    available_buying_power = float(account.daytrading_buying_power) if float(account.daytrading_buying_power) > 0 else float(account.buying_power)
    
    if target_value > available_buying_power:
        target_value = available_buying_power
        
    qty = int(target_value / price)
    if qty <= 0:
        return

    # Marketable Limit: Limit price slightly worse than current quote to ensure fill, but cap slippage
    # Ensure quotes are valid and not crossed
    if quote.ask_price is None or quote.bid_price is None or math.isnan(quote.ask_price) or math.isnan(quote.bid_price):
        logger.info(f"Skipping {symbol} HFT signal - missing or NaN quotes.")
        return

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

    if sl_price <= 0 or tp_price <= 0:
        logger.info(f"Skipping {symbol} HFT signal - calculated SL/TP price is zero or negative.")
        return

    with state_lock:
        pending_entries[symbol] = now
        pending_entry_values[symbol] = qty * limit_price
        pending_entry_risks[symbol] = qty * min_clearance
        
    def place_order():
        try:
            success = submit_hft_bracket_order(symbol, side, qty, limit_price, tp_price, sl_price, current_equity)
        except Exception as e:
            logger.error(f"Unhandled order placement error for {symbol} HFT: {e}")
            success = False
        if not success:
            release_entry_reservation(symbol)

    # We use place_order in a background thread to prevent blocking
    asyncio.create_task(asyncio.to_thread(place_order))

async def handle_trade(trade: Trade):
    with state_lock:
        state = micro_state.setdefault(trade.symbol, {
            "latest_quote": None,
            "recent_trades": deque(),
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
        
        if direction == "BUY":
            state["buy_vol_10s"] += trade.size
        elif direction == "SELL":
            state["sell_vol_10s"] += trade.size
        
        # Prune trades older than 10 seconds
        cutoff = trade.timestamp - timedelta(seconds=10)
        while state["recent_trades"] and state["recent_trades"][0]["timestamp"] < cutoff:
            popped = state["recent_trades"].popleft()
            if popped["direction"] == "BUY":
                state["buy_vol_10s"] -= popped["size"]
            elif popped["direction"] == "SELL":
                state["sell_vol_10s"] -= popped["size"]

        # Prevent negative volumes due to floating point inaccuracies
        state["buy_vol_10s"] = max(0.0, state["buy_vol_10s"])
        state["sell_vol_10s"] = max(0.0, state["sell_vol_10s"])

        buy_vol = state["buy_vol_10s"]
        sell_vol = state["sell_vol_10s"]
        total_vol = buy_vol + sell_vol
        
        if total_vol >= HFT_MIN_BURST_VOLUME:
            buy_ratio = buy_vol / total_vol if total_vol > 0 else 0
            sell_ratio = sell_vol / total_vol if total_vol > 0 else 0
            
            signal = None
            if buy_ratio >= HFT_IMBALANCE_THRESHOLD:
                signal = "LONG"
            elif sell_ratio >= HFT_IMBALANCE_THRESHOLD:
                signal = "SHORT"
                
            if signal:
                quote = state["latest_quote"]
                if quote is None:
                    logger.warning(f"Skipping HFT SIGNAL for {trade.symbol} - no recent quote available.")
                    return
                # Need to use asyncio to not block the stream thread, or call directly if we know it's safe.
                asyncio.create_task(evaluate_hft_entry(trade.symbol, signal, trade.price, quote))

async def handle_quote(quote: Quote):
    with state_lock:
        state = micro_state.setdefault(quote.symbol, {
            "latest_quote": None,
            "recent_trades": deque(),
            "buy_vol_10s": 0.0,
            "sell_vol_10s": 0.0
        })
        state["latest_quote"] = quote

async def risk_manager():
    global initial_equity, trading_halted_today, current_trading_day
    global position_entry_times, position_hwm, runner_active, runner_eligible, pending_entries, pending_entry_values, pending_entry_risks
    
    while True:
        try:
            today = get_current_ny_date()
            if current_trading_day != today:
                account = await asyncio.to_thread(trading_client.get_account)
                reset_daily_state(float(account.equity))

            clock = await asyncio.to_thread(trading_client.get_clock)
            if not clock.is_open:
                positions = await asyncio.to_thread(get_stock_positions)
                if positions:
                    logger.error(f"Market is closed with open positions: {[p.symbol for p in positions]}")
                    send_telegram_alert(f"Market is closed with open Alpaca positions: {[p.symbol for p in positions]}")
                await asyncio.sleep(60)
                continue

            current_time = get_current_ny_time()
            now_dt = datetime.now(TIMEZONE)
            account = await asyncio.to_thread(trading_client.get_account)
            current_equity = float(account.equity)

            flatten_deadline = get_flatten_deadline(clock)
            if now_dt >= flatten_deadline or current_time >= FLATTEN_TIME:
                logger.info(f"Flatten deadline reached ({flatten_deadline}). Flattening book.")
                set_trading_halted(True, "flatten_deadline")
                flattened = await asyncio.to_thread(flatten_all)
                if flattened:
                    write_daily_summary("flatten_deadline", current_equity=current_equity)
                    logger.info("Exiting script for the day. Cron will restart it tomorrow.")
                    os._exit(0)
                logger.error("Flatten verification failed. Exiting with crash code after alert.")
                write_daily_summary("flatten_failed", current_equity=current_equity)
                os._exit(99)
                
            if daily_loss_breached(current_equity):
                loss = (initial_equity - current_equity) / initial_equity
                set_trading_halted(True, "daily_loss")
                logger.error(f"KILL SWITCH TRIGGERED! Daily loss: {loss*100:.2f}%")
                flattened = await asyncio.to_thread(flatten_all)
                if flattened:
                    write_daily_summary("daily_loss", current_equity=current_equity)
                    logger.info("Exiting script due to max daily loss. Cron will restart it tomorrow.")
                    os._exit(0)
                logger.error("Kill-switch flatten verification failed. Exiting with crash code after alert.")
                write_daily_summary("daily_loss_flatten_failed", current_equity=current_equity)
                os._exit(99)

            # Evaluate positions for Time-Based Stop and Trailing Stop
            positions = await asyncio.to_thread(trading_client.get_all_positions)
            stock_positions = [p for p in positions if is_stock_position(p)]
            
            try:
                # Need to check open orders (includes HELD legs for bracket orders)
                all_open_orders_req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
                all_pending_orders = await asyncio.to_thread(trading_client.get_orders, all_open_orders_req)
                open_orders_reliable = True
            except Exception as e:
                logger.error(f"Error fetching open orders: {e}")
                all_pending_orders = []
                open_orders_reliable = False
                send_rate_limited_alert("open_orders_unavailable", f"Alpaca bot could not fetch open orders for risk checks: {e}")
                
            now = datetime.now(TIMEZONE)

            if open_orders_reliable:
                with state_lock:
                    entry_times_snapshot = dict(position_entry_times)
                for position in stock_positions:
                    entry_time = as_ny_datetime(entry_times_snapshot.get(position.symbol))
                    if entry_time and (now - entry_time).total_seconds() < 60:
                        continue
                    if not position_has_protective_order(position, all_pending_orders):
                        message = f"Alpaca bot detected {position.symbol} position without a protective stop/trailing order."
                        logger.error(message)
                        log_trade_event("unprotected_position", position.symbol, qty=getattr(position, "qty", None), side=getattr(position, "side", None))
                        send_rate_limited_alert(f"unprotected_position:{position.symbol}", message)

            closed_symbols_for_cooldown = cleanup_trade_state_after_order_snapshot(
                stock_positions,
                all_pending_orders,
                open_orders_reliable,
                now
            )

            for sym in closed_symbols_for_cooldown:
                register_symbol_exit(sym, "position_closed")

            with state_lock:
                missing_syms = [p.symbol for p in stock_positions if p.symbol not in position_entry_times]
            if missing_syms:
                try:
                    position_by_symbol = {p.symbol: p for p in stock_positions}
                    req = GetOrdersRequest(
                        status=QueryOrderStatus.CLOSED,
                        symbols=missing_syms,
                        limit=500,
                        after=now.replace(hour=0, minute=0, second=0, microsecond=0)
                    )
                    recent_orders = await asyncio.to_thread(trading_client.get_orders, req)
                    filled_orders = [o for o in recent_orders if is_filled_order(o) and o.filled_at]
                    with state_lock:
                        for sym in missing_syms:
                            pos = position_by_symbol.get(sym)
                            opening_side = OrderSide.BUY if pos and is_long_position(pos) else OrderSide.SELL
                            sym_orders = [
                                o for o in filled_orders
                                if o.symbol == sym and normalize_enum_value(o.side) == normalize_enum_value(opening_side)
                            ]
                            if sym_orders:
                                sym_orders.sort(key=lambda x: x.filled_at)
                                position_entry_times[sym] = as_ny_datetime(sym_orders[-1].filled_at)
                            else:
                                position_entry_times[sym] = now
                except Exception as e:
                    logger.error(f"Error querying bulk fill times: {e}")
                    with state_lock:
                        for sym in missing_syms:
                            position_entry_times[sym] = now

            for p in stock_positions:
                sym = p.symbol
                with state_lock:
                    # Use live websocket price if available, fallback to REST API price
                    live_price = market_data_state.get(sym, {}).get("last_price")
                current_price = float(live_price) if live_price is not None else float(p.current_price)
                entry_price = float(p.avg_entry_price)
                qty = float(p.qty)
                is_long = is_long_position(p)

                with state_lock:
                    if sym not in position_hwm:
                        position_hwm[sym] = current_price
                    else:
                        if is_long:
                            position_hwm[sym] = max(position_hwm[sym], current_price)
                        else:
                            position_hwm[sym] = min(position_hwm[sym], current_price)
                            
                    entry_time = position_entry_times.get(sym)
                    
                if entry_time:
                    held_duration = (datetime.now(TIMEZONE) - as_ny_datetime(entry_time)).total_seconds() / 60
                    unrealized_plpc = float(p.unrealized_plpc)
                    if held_duration > 15 and unrealized_plpc < 0:
                        logger.info(f"Time stop hit for {sym}. Held > 15m and PnL negative. Closing.")
                        log_trade_event("exit_signal", sym, reason="time_stop", held_minutes=held_duration, unrealized_plpc=unrealized_plpc)
                        schedule_symbol_close(sym)
                        continue

                with state_lock:
                    if is_long:
                        hwm = position_hwm[sym]
                    else:
                        lwm = position_hwm[sym]
                    is_runner_active = runner_active.get(sym)
                    is_runner_eligible = sym in runner_eligible

                # Check if TP is hit or runner is already active
                if is_runner_eligible and not is_runner_active:
                    try:
                        if not open_orders_reliable:
                            logger.warning(f"Skipping runner activation check for {sym}; open order data was unavailable.")
                            continue
                        expected_tp_side = OrderSide.SELL if is_long else OrderSide.BUY
                        sym_open_orders = [o for o in all_pending_orders if o.symbol == sym]
                        tp_pending = any(
                            normalize_enum_value(o.side) == normalize_enum_value(expected_tp_side)
                            and getattr(o, "limit_price", None) is not None
                            for o in sym_open_orders
                        )
                        
                        if not tp_pending:
                            tp_filled = await asyncio.to_thread(take_profit_filled_today, sym, is_long, now, entry_time)
                            if tp_filled:
                                native_trailing_active, close_runner = await asyncio.to_thread(
                                    promote_runner_to_native_trailing_stop,
                                    sym,
                                    p,
                                    all_pending_orders
                                )
                                if close_runner:
                                    logger.error(f"Could not protect {sym} runner after TP fill; closing runner.")
                                    schedule_symbol_close(sym)
                                    continue

                                with state_lock:
                                    runner_active[sym] = True
                                    is_runner_active = True
                                stop_mode = "native + programmatic" if native_trailing_active else "programmatic"
                                log_trade_event("runner_activated", sym, stop_mode=stop_mode)
                                logger.info(f"Confirmed take-profit fill for {sym}. Activating {stop_mode} trailing stop on runner.")
                            else:
                                logger.warning(f"No pending TP and no confirmed TP fill for {sym}; leaving runner inactive.")
                    except Exception as e:
                        logger.error(f"Error checking open orders for {sym}: {e}")
                
                if is_runner_active:
                    if is_long:
                        trail_stop_price = hwm * (1 - (RUNNER_TRAIL_PERCENT / 100))
                        if current_price <= trail_stop_price:
                            logger.info(f"Programmatic trailing stop triggered for {sym} at {current_price}. HWM: {hwm}. Closing runner.")
                            log_trade_event("exit_signal", sym, reason="programmatic_trailing_stop", current_price=current_price, trail_stop_price=trail_stop_price, hwm=hwm)
                            schedule_symbol_close(sym)
                    else:
                        trail_stop_price = lwm * (1 + (RUNNER_TRAIL_PERCENT / 100))
                        if current_price >= trail_stop_price:
                            logger.info(f"Programmatic trailing stop triggered for {sym} at {current_price}. LWM: {lwm}. Closing runner.")
                            log_trade_event("exit_signal", sym, reason="programmatic_trailing_stop", current_price=current_price, trail_stop_price=trail_stop_price, lwm=lwm)
                            schedule_symbol_close(sym)

        except Exception as e:
            logger.error(f"Risk Manager Error: {e}")
            
        await asyncio.sleep(15)

async def main():
    global initial_equity, current_trading_day
    account = await asyncio.to_thread(trading_client.get_account)
    initialize_daily_state(float(account.equity))
    logger.info(f"Starting High-Volume Day Trading Bot. Initial Equity: ${initial_equity}")

    logger.info("Fetching dynamic watchlist of top movers > $10...")
    dynamic_watchlist = get_dynamic_watchlist(API_KEY, API_SECRET, target_count=14, min_price=10.0)
    
    if "SPY" not in dynamic_watchlist:
        dynamic_watchlist.append("SPY")
        
    logger.info(f"Dynamic Watchlist Generated: {len(dynamic_watchlist)} symbols. {dynamic_watchlist[:5]}...")

    try:
        logger.info("Building shortable asset cache...")
        from alpaca.trading.requests import GetAssetsRequest
        from alpaca.trading.enums import AssetClass
        req = GetAssetsRequest(asset_class=AssetClass.US_EQUITY)
        assets = await asyncio.to_thread(trading_client.get_all_assets, req)
        for asset in assets:
            if asset.tradable:
                asset_shortable_cache[asset.symbol] = asset.shortable and asset.easy_to_borrow
        logger.info(f"Cached shortable status for {len(asset_shortable_cache)} assets.")
    except Exception as e:
        logger.error(f"Failed to build shortable asset cache: {e}")

    data_stream.subscribe_trades(handle_trade, *dynamic_watchlist)
    data_stream.subscribe_quotes(handle_quote, *dynamic_watchlist)
    
    asyncio.create_task(risk_manager())
    
    logger.info("Waiting for market data...")
    # Run stream asynchronously with auto-reconnect
    while True:
        try:
            logger.info("Starting data stream...")
            await asyncio.to_thread(data_stream.run)
            logger.warning("Stream ended gracefully. Reconnecting in 5 seconds...")
        except Exception as e:
            logger.error(f"Stream error: {e}. Reconnecting in 5 seconds...")
        await asyncio.sleep(5)

def send_telegram_alert(message):
    try:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_HOME_CHANNEL")
        if not bot_token or not chat_id:
            logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_HOME_CHANNEL is not set; alert not sent.")
            return
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": f"🚨 Alpaca Bot Alert:\n\n{message}"
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                logger.error(f"Failed to send Telegram alert. Status: {response.status}")
    except Exception as e:
        logger.error(f"Error sending Telegram alert: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
        write_daily_summary("manual_stop", current_equity=get_account_equity_safely())
        send_telegram_alert("Bot stopped manually (KeyboardInterrupt).")
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Bot crashed: {e}\n{tb}")
        log_trade_event("bot_crashed", error=str(e), traceback=tb)
        write_daily_summary("crash", current_equity=get_account_equity_safely())
        send_telegram_alert(f"Bot crashed: {e}\n{tb}")
        sys.exit(99)
