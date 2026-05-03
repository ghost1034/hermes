import asyncio
import importlib
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytz


class EnumValue(str):
    @property
    def value(self):
        return str(self)


class RequestStub:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TradingClientStub:
    def __init__(self, *args, **kwargs):
        pass

    def get_account(self):
        return SimpleNamespace(equity="10000")


class StockDataStreamStub:
    def __init__(self, *args, **kwargs):
        pass

    def subscribe_bars(self, *args, **kwargs):
        pass

    def run(self):
        pass


class StockHistoricalDataClientStub:
    def __init__(self, *args, **kwargs):
        pass


def install_fake_alpaca_modules():
    alpaca = types.ModuleType("alpaca")
    trading = types.ModuleType("alpaca.trading")
    trading_client = types.ModuleType("alpaca.trading.client")
    trading_requests = types.ModuleType("alpaca.trading.requests")
    trading_enums = types.ModuleType("alpaca.trading.enums")
    data = types.ModuleType("alpaca.data")
    data_live = types.ModuleType("alpaca.data.live")
    data_models = types.ModuleType("alpaca.data.models")
    data_historical = types.ModuleType("alpaca.data.historical")
    data_requests = types.ModuleType("alpaca.data.requests")
    data_timeframe = types.ModuleType("alpaca.data.timeframe")

    trading_client.TradingClient = TradingClientStub
    for name in (
        "LimitOrderRequest",
        "TakeProfitRequest",
        "StopLossRequest",
        "GetOrdersRequest",
        "TrailingStopOrderRequest",
    ):
        setattr(trading_requests, name, RequestStub)

    trading_enums.OrderSide = types.SimpleNamespace(BUY=EnumValue("buy"), SELL=EnumValue("sell"))
    trading_enums.TimeInForce = types.SimpleNamespace(DAY=EnumValue("day"))
    trading_enums.OrderClass = types.SimpleNamespace(BRACKET=EnumValue("bracket"), OTO=EnumValue("oto"))
    trading_enums.QueryOrderStatus = types.SimpleNamespace(OPEN=EnumValue("open"), CLOSED=EnumValue("closed"))
    trading_enums.OrderStatus = types.SimpleNamespace(FILLED=EnumValue("filled"))
    trading_enums.PositionSide = types.SimpleNamespace(LONG=EnumValue("long"), SHORT=EnumValue("short"))
    trading_enums.AssetClass = types.SimpleNamespace(US_EQUITY=EnumValue("us_equity"))

    data_live.StockDataStream = StockDataStreamStub
    data_models.Bar = object
    data_historical.StockHistoricalDataClient = StockHistoricalDataClientStub
    data_requests.StockBarsRequest = RequestStub
    data_requests.StockLatestQuoteRequest = RequestStub
    data_timeframe.TimeFrame = types.SimpleNamespace(Minute=EnumValue("1Min"))

    sys.modules.update({
        "alpaca": alpaca,
        "alpaca.trading": trading,
        "alpaca.trading.client": trading_client,
        "alpaca.trading.requests": trading_requests,
        "alpaca.trading.enums": trading_enums,
        "alpaca.data": data,
        "alpaca.data.live": data_live,
        "alpaca.data.models": data_models,
        "alpaca.data.historical": data_historical,
        "alpaca.data.requests": data_requests,
        "alpaca.data.timeframe": data_timeframe,
    })


def import_daytrader():
    os.environ.setdefault("APCA_API_KEY_ID", "test-key")
    os.environ.setdefault("APCA_API_SECRET_KEY", "test-secret")
    install_fake_alpaca_modules()
    sys.modules.pop("daytrader", None)
    return importlib.import_module("daytrader")


class DaytraderLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dt = import_daytrader()
        cls.default_trading_client = cls.dt.trading_client
        cls.default_send_telegram_alert = cls.dt.send_telegram_alert

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.dt.DAILY_STATE_FILE = os.path.join(self.tmpdir.name, "state.json")
        self.dt.TRADE_EVENT_LOG_FILE = os.path.join(self.tmpdir.name, "events.jsonl")
        self.dt.DAILY_SUMMARY_FILE = os.path.join(self.tmpdir.name, "summary.json")
        self.dt.initial_equity = 0.0
        self.dt.trading_halted_today = False
        self.dt.current_trading_day = None
        self.dt.trading_client = self.default_trading_client
        self.dt.send_telegram_alert = self.default_send_telegram_alert
        self.dt.market_data_state.clear()
        self.dt.position_entry_times.clear()
        self.dt.position_hwm.clear()
        self.dt.runner_active.clear()
        self.dt.runner_eligible.clear()
        self.dt.pending_entries.clear()
        self.dt.pending_entry_values.clear()
        self.dt.pending_entry_risks.clear()
        self.dt.symbol_cooldowns.clear()
        self.dt.symbol_trade_counts.clear()
        self.dt.reset_observability_stats()

    def test_persisted_daily_halt_survives_restart(self):
        today = self.dt.get_current_ny_date()
        self.dt.current_trading_day = today
        self.dt.initial_equity = 10000.0
        self.dt.set_trading_halted(True, "daily_loss")

        self.dt.initial_equity = 0.0
        self.dt.trading_halted_today = False
        self.dt.current_trading_day = None
        self.dt.initialize_daily_state(9000.0)

        self.assertEqual(self.dt.initial_equity, 10000.0)
        self.assertTrue(self.dt.trading_halted_today)
        self.assertEqual(self.dt.current_trading_day, today)

    def test_spy_regime_fails_closed_when_missing_or_stale(self):
        _, _, _, error = self.dt.get_fresh_spy_regime()
        self.assertIn("missing", error)

        now = datetime.now(self.dt.TIMEZONE)
        self.dt.market_data_state["SPY"] = {
            "last_price": 401.0,
            "cum_vol": 100,
            "cum_pv": 40000.0,
            "last_bar_at": now - timedelta(seconds=self.dt.SPY_REGIME_MAX_AGE_SECONDS + 1),
        }
        _, _, _, error = self.dt.get_fresh_spy_regime(now=now)
        self.assertIn("stale", error)

        self.dt.market_data_state["SPY"]["last_bar_at"] = now
        price, vwap, bullish, error = self.dt.get_fresh_spy_regime(now=now)
        self.assertEqual(price, 401.0)
        self.assertEqual(vwap, 400.0)
        self.assertTrue(bullish)
        self.assertIsNone(error)

    def test_dynamic_stop_and_take_profit_bounds(self):
        self.assertEqual(self.dt.calculate_dynamic_stop_pct([0.001, 0.002]), self.dt.STOP_LOSS_PCT)
        self.assertEqual(self.dt.calculate_dynamic_stop_pct([0.05]), self.dt.MAX_DYNAMIC_STOP_LOSS_PCT)
        self.assertEqual(self.dt.calculate_take_profit_pct(0.02), self.dt.MAX_DYNAMIC_TAKE_PROFIT_PCT)

    def test_risk_estimate_uses_dynamic_stop_pct(self):
        self.assertEqual(self.dt.estimate_entry_stop_risk(10000, 100, 0.02), 200)

    def test_symbol_cooldown_and_trade_count_gates(self):
        now = datetime.now(self.dt.TIMEZONE)
        self.dt.symbol_cooldowns["AAPL"] = now + timedelta(minutes=5)
        self.assertFalse(self.dt.is_symbol_trade_allowed("AAPL", now=now))

        self.dt.symbol_cooldowns.clear()
        self.dt.symbol_trade_counts["AAPL"] = self.dt.MAX_TRADES_PER_SYMBOL_PER_DAY
        self.assertFalse(self.dt.is_symbol_trade_allowed("AAPL", now=now))

        self.dt.symbol_trade_counts["AAPL"] = self.dt.MAX_TRADES_PER_SYMBOL_PER_DAY - 1
        self.assertTrue(self.dt.is_symbol_trade_allowed("AAPL", now=now))

    def test_bar_quality_filter_requires_directional_close(self):
        strong_long = SimpleNamespace(symbol="AAPL", high=101.0, low=100.0, close=100.8)
        weak_long = SimpleNamespace(symbol="AAPL", high=101.0, low=100.0, close=100.2)
        strong_short = SimpleNamespace(symbol="AAPL", high=101.0, low=100.0, close=100.2)

        self.assertTrue(self.dt.passes_bar_quality_filter(strong_long, is_long=True))
        self.assertFalse(self.dt.passes_bar_quality_filter(weak_long, is_long=True))
        self.assertTrue(self.dt.passes_bar_quality_filter(strong_short, is_long=False))

    def test_entry_limit_price_uses_slippage_guardrail(self):
        self.assertGreater(self.dt.entry_limit_price(100.0, is_long=True), 100.0)
        self.assertLess(self.dt.entry_limit_price(100.0, is_long=False), 100.0)

    def test_replay_trade_count_default_matches_live(self):
        replay = importlib.import_module("replay_backtest")

        self.assertEqual(replay.MAX_TRADES_PER_SYMBOL_PER_DAY, self.dt.MAX_TRADES_PER_SYMBOL_PER_DAY)

    def test_enum_helpers_accept_raw_strings(self):
        position = SimpleNamespace(asset_class="us_equity", side="long")
        order = SimpleNamespace(status="filled")

        self.assertTrue(self.dt.is_stock_position(position))
        self.assertTrue(self.dt.is_long_position(position))
        self.assertTrue(self.dt.is_filled_order(order))

    def test_protective_order_requires_full_quantity_coverage(self):
        position = SimpleNamespace(symbol="AAPL", qty="10", side="long")
        partial_stop = SimpleNamespace(symbol="AAPL", qty="5", side="sell", stop_price="99")
        full_stop = SimpleNamespace(symbol="AAPL", qty="10", side="sell", stop_price="99")

        self.assertFalse(self.dt.position_has_protective_order(position, [partial_stop]))
        self.assertTrue(self.dt.position_has_protective_order(position, [full_stop]))

    def test_cleanup_skips_state_when_open_orders_unreliable(self):
        now = datetime.now(self.dt.TIMEZONE)
        old_time = now - timedelta(minutes=5)
        self.dt.position_entry_times["AAPL"] = old_time
        self.dt.position_hwm["AAPL"] = 101.0
        self.dt.runner_active["AAPL"] = True
        self.dt.runner_eligible.add("AAPL")
        self.dt.pending_entries["AAPL"] = old_time
        self.dt.pending_entry_values["AAPL"] = 1000.0
        self.dt.pending_entry_risks["AAPL"] = 10.0

        closed = self.dt.cleanup_trade_state_after_order_snapshot([], [], False, now)

        self.assertEqual(closed, [])
        self.assertIn("AAPL", self.dt.position_entry_times)
        self.assertIn("AAPL", self.dt.position_hwm)
        self.assertIn("AAPL", self.dt.runner_active)
        self.assertIn("AAPL", self.dt.runner_eligible)
        self.assertIn("AAPL", self.dt.pending_entries)

    def test_cleanup_releases_reservation_when_position_live_without_open_entry(self):
        now = datetime.now(self.dt.TIMEZONE)
        position = SimpleNamespace(symbol="AAPL", side="long")
        self.dt.pending_entries["AAPL"] = now - timedelta(minutes=2)
        self.dt.pending_entry_values["AAPL"] = 1000.0
        self.dt.pending_entry_risks["AAPL"] = 10.0
        stop_order = SimpleNamespace(symbol="AAPL", side="sell")

        self.dt.cleanup_trade_state_after_order_snapshot([position], [stop_order], True, now)

        self.assertIn("AAPL", self.dt.pending_entries)
        self.assertNotIn("AAPL", self.dt.pending_entry_values)
        self.assertNotIn("AAPL", self.dt.pending_entry_risks)

    def test_runner_promotion_submits_trailing_before_canceling_static_stop(self):
        calls = []

        class Client:
            def submit_order(self, order_data):
                calls.append("submit")
                return SimpleNamespace(id="trail-1", status="accepted")

            def cancel_order_by_id(self, order_id):
                calls.append(f"cancel:{order_id}")

        self.dt.trading_client = Client()
        position = SimpleNamespace(symbol="AAPL", qty="10", side="long")
        static_stop = SimpleNamespace(symbol="AAPL", qty="10", side="sell", stop_price="99", id="stop-1")

        active, close_runner = self.dt.promote_runner_to_native_trailing_stop("AAPL", position, [static_stop])

        self.assertTrue(active)
        self.assertFalse(close_runner)
        self.assertEqual(calls, ["submit", "cancel:stop-1"])

    def test_runner_promotion_keeps_static_stop_on_submit_failure(self):
        calls = []

        class Client:
            def submit_order(self, order_data):
                calls.append("submit")
                raise RuntimeError("rejected")

            def cancel_order_by_id(self, order_id):
                calls.append(f"cancel:{order_id}")

        self.dt.trading_client = Client()
        self.dt.send_telegram_alert = lambda message: None
        position = SimpleNamespace(symbol="AAPL", qty="10", side="long")
        static_stop = SimpleNamespace(symbol="AAPL", qty="10", side="sell", stop_price="99", id="stop-1")

        active, close_runner = self.dt.promote_runner_to_native_trailing_stop("AAPL", position, [static_stop])

        self.assertFalse(active)
        self.assertFalse(close_runner)
        self.assertEqual(calls, ["submit"])

    def test_reserve_symbol_handles_account_clock_failure(self):
        timezone = self.dt.TIMEZONE

        class Client:
            def get_all_positions(self):
                return []

            def get_orders(self, request):
                return []

            def get_account(self):
                raise RuntimeError("account unavailable")

            def get_clock(self):
                return SimpleNamespace(is_open=True, next_close=datetime.now(timezone) + timedelta(hours=1))

        self.dt.trading_client = Client()

        allowed = asyncio.run(self.dt.reserve_symbol_for_entry("AAPL", 0.05, 100.0, 0.01))

        self.assertFalse(allowed)
        self.assertNotIn("AAPL", self.dt.pending_entries)


if __name__ == "__main__":
    unittest.main()
