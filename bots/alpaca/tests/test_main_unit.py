from types import SimpleNamespace
from datetime import datetime as dt

import pandas as pd
import pytest

import main


def test_symbol_and_format_helpers():
    assert main.normalize_symbol(None) == ''
    assert main.normalize_symbol(' aapl ') == 'AAPL'
    assert main.dedupe_symbols(['aapl', ' AAPL ', '', None, 'msft']) == ['AAPL', 'MSFT']
    assert list(main.chunked(['A', 'B', 'C'], 2)) == [['A', 'B'], ['C']]
    assert main.format_qty(1.230000) == '1.23'
    assert main.format_price(1.235) == 1.24


def test_shutdown_cutoff_uses_eastern_time():
    before_cutoff = dt(2026, 1, 1, 15, 44, 59, tzinfo=main.EASTERN_TZ)
    at_cutoff = dt(2026, 1, 1, 15, 45, 0, tzinfo=main.EASTERN_TZ)
    after_cutoff = dt(2026, 1, 1, 15, 46, 0, tzinfo=main.EASTERN_TZ)

    assert main.is_shutdown_time(before_cutoff) is False
    assert main.is_shutdown_time(at_cutoff) is True
    assert main.is_shutdown_time(after_cutoff) is True
    assert main.seconds_until_shutdown(before_cutoff) == 1


def test_loop_sleep_is_capped_to_shutdown_deadline(monkeypatch):
    monkeypatch.setattr(main, 'LOOP_SLEEP_SECONDS', 60)
    now = dt(2026, 1, 1, 15, 44, 30, tzinfo=main.EASTERN_TZ)
    assert main.get_loop_sleep_seconds(now) == 30


def test_ensure_order_storage_creates_csv_headers(temp_bot):
    orders = pd.read_csv(temp_bot.ORDERS_FILE)
    open_orders = pd.read_csv(temp_bot.OPEN_ORDERS_FILE)
    cooldown = pd.read_csv(temp_bot.TIME_AND_COINS_FILE)
    assert list(orders.columns) == temp_bot.ORDER_COLUMNS
    assert list(open_orders.columns) == temp_bot.ORDER_COLUMNS
    assert list(cooldown.columns) == temp_bot.TIME_COLUMNS


def test_dynamic_mover_tickers_filter_to_tradable_and_price(temp_bot, fake_api, monkeypatch):
    fake_api.data_response = {
        'last_updated': 'now',
        'gainers': [{'symbol': 'aapl', 'price': 150}, {'symbol': 'penny', 'price': 2}],
        'losers': [{'symbol': 'msft', 'price': 300}, {'symbol': 'skip', 'price': 1000}],
    }
    fake_api.assets = [
        SimpleNamespace(symbol='AAPL', tradable=True),
        SimpleNamespace(symbol='MSFT', tradable=True),
        SimpleNamespace(symbol='PENNY', tradable=True),
        SimpleNamespace(symbol='SKIP', tradable=False),
    ]
    monkeypatch.setattr(temp_bot, 'dynamic_tickers_min_price', 10)
    monkeypatch.setattr(temp_bot, 'dynamic_tickers_max_price', 500)
    assert temp_bot.get_dynamic_mover_tickers() == ['AAPL', 'MSFT']


def test_load_tickers_falls_back_when_dynamic_loading_fails(temp_bot, monkeypatch):
    monkeypatch.setattr(temp_bot, 'dynamic_tickers_enabled', True)
    monkeypatch.setattr(temp_bot, 'read_static_tickers', lambda: ['AAPL', 'MSFT'])
    monkeypatch.setattr(temp_bot, 'get_dynamic_mover_tickers', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    assert temp_bot.load_tickers() == ['AAPL', 'MSFT']


def test_get_data_for_tickers_splits_batch_data_by_symbol(temp_bot, fake_api, monkeypatch):
    index = pd.MultiIndex.from_tuples(
        [('AAPL', pd.Timestamp('2026-01-01 09:30')), ('MSFT', pd.Timestamp('2026-01-01 09:30'))],
        names=['symbol', 'timestamp']
    )
    fake_api.bars_df = pd.DataFrame({
        'open': [100, 200],
        'high': [101, 201],
        'low': [99, 199],
        'close': [100.5, 200.5],
    }, index=index)
    monkeypatch.setattr(temp_bot, 'bar_request_chunk_size', 100)
    result = temp_bot.get_data_for_tickers(['aapl', 'msft'])
    assert set(result) == {'AAPL', 'MSFT'}
    assert list(result['AAPL'].columns) == ['Timestamp', 'Open', 'High', 'Low', 'Close']
    assert result['AAPL']['Close'].iloc[0] == 100.5
    assert result['MSFT']['Close'].iloc[0] == 200.5


def test_buy_flow_submits_market_and_protective_orders(temp_bot, fake_api):
    fake_api.latest_prices['AAPL'] = 100.0
    mail = temp_bot.buy('aapl', trade_cap_percent=5)
    assert mail == 'TRADE ALERT: BUY Order Filled for 5.0 AAPL at $100.0'
    assert fake_api.submitted_orders[0].side == 'buy'
    assert fake_api.submitted_orders[0].symbol == 'AAPL'
    protective_order = fake_api.submitted_orders[1]
    assert protective_order.side == 'sell'
    assert protective_order.order_class == 'oco'
    assert protective_order.time_in_force == 'day'
    assert protective_order.take_profit == {'limit_price': temp_bot.format_price(100 * (1 + temp_bot.limit_price * 0.01))}
    assert protective_order.stop_loss == {'stop_price': temp_bot.format_price(100 * (1 - temp_bot.stop_loss * 0.01))}
    assert not hasattr(protective_order, 'limit_price')

    orders = pd.read_csv(temp_bot.ORDERS_FILE)
    open_orders = pd.read_csv(temp_bot.OPEN_ORDERS_FILE)
    cooldown = pd.read_csv(temp_bot.TIME_AND_COINS_FILE)
    assert orders.iloc[0]['Ticker'] == 'AAPL'
    assert open_orders.iloc[0]['Ticker'] == 'AAPL'
    assert cooldown.iloc[0]['Ticker'] == 'AAPL'


def test_buy_keeps_fractional_quantity_for_fractionable_asset(temp_bot, fake_api):
    fake_api.assets = [SimpleNamespace(symbol='FRACT', tradable=True, fractionable=True)]
    fake_api.latest_prices['FRACT'] = 90.0

    temp_bot.buy('FRACT', trade_cap_percent=5)

    assert fake_api.submitted_orders[0].qty == '5.555556'


def test_buy_rounds_down_for_non_fractionable_asset(temp_bot, fake_api):
    fake_api.assets = [SimpleNamespace(symbol='WHOLE', tradable=True, fractionable=False)]
    fake_api.latest_prices['WHOLE'] = 90.0

    mail = temp_bot.buy('WHOLE', trade_cap_percent=5)

    assert mail == 'TRADE ALERT: BUY Order Filled for 5.0 WHOLE at $90.0'
    assert fake_api.submitted_orders[0].qty == '5'


def test_buy_skips_non_fractionable_asset_when_under_one_share(temp_bot, fake_api):
    fake_api.assets = [SimpleNamespace(symbol='EXPENSIVE', tradable=True, fractionable=False)]
    fake_api.latest_prices['EXPENSIVE'] = 1000.0

    assert temp_bot.buy('EXPENSIVE', trade_cap_percent=5) is None
    assert fake_api.submitted_orders == []


def test_sell_flow_cancels_protective_order_and_logs_sell(temp_bot, fake_api):
    fake_api.latest_prices['AAPL'] = 110.0
    fake_api.open_orders = [SimpleNamespace(id='protect-1', symbol='AAPL', side='sell')]
    mail = temp_bot.sell('aapl', quantity=2, buy_price=100, highest_price=112)
    assert mail == 'TRADE ALERT: SELL Order Filled for 2.0 AAPL at $110.0'
    assert fake_api.canceled_order_ids == ['protect-1']

    orders = pd.read_csv(temp_bot.ORDERS_FILE)
    assert orders.iloc[0]['Type'] == 'sell'
    assert orders.iloc[0]['Sell Price'] == 110.0


def test_flatten_all_positions_cancels_orders_closes_positions_and_clears_local_state(temp_bot, fake_api):
    row = {
        'Time': '2026-01-01 09:30:00',
        'Ticker': 'AAPL',
        'Type': 'buy',
        'Buy Price': 100.0,
        'Sell Price': '-',
        'Highest Price': 110.0,
        'Quantity': 2.0,
        'Total': 200.0,
        'Acc Balance': 10000.0,
        'Target Price': 105.0,
        'Stop Loss Price': 95.0,
        'ActivateTrailingStopAt': 101.0,
        'Order ID': 'buy-1',
        'Order Status': 'filled',
        'Protective Order ID': 'oco-1',
    }
    pd.DataFrame([row], columns=temp_bot.ORDER_COLUMNS).to_csv(temp_bot.OPEN_ORDERS_FILE, index=False)
    fake_api.positions = [SimpleNamespace(symbol='AAPL', qty='2', avg_entry_price='100')]
    fake_api.open_orders = [SimpleNamespace(id='oco-1', symbol='AAPL', side='sell')]
    fake_api.latest_prices['AAPL'] = 111.0

    closed_symbols = temp_bot.flatten_all_positions()

    assert closed_symbols == {'AAPL'}
    assert fake_api.canceled_order_ids == ['oco-1']
    assert fake_api.positions == []
    assert fake_api.submitted_orders[0].side == 'sell'
    assert fake_api.submitted_orders[0].type == 'market'

    open_orders = pd.read_csv(temp_bot.OPEN_ORDERS_FILE)
    orders = pd.read_csv(temp_bot.ORDERS_FILE)
    assert open_orders.empty
    assert orders.iloc[0]['Type'] == 'shutdown_sell'
    assert orders.iloc[0]['Ticker'] == 'AAPL'


def test_buy_skips_after_shutdown_cutoff(temp_bot, monkeypatch):
    monkeypatch.setattr(temp_bot, 'is_shutdown_time', lambda *args, **kwargs: True)
    assert temp_bot.buy('AAPL') is None


def test_run_bot_cycle_skips_buy_generation_after_shutdown_cutoff(temp_bot, monkeypatch):
    monkeypatch.setattr(temp_bot, 'is_shutdown_time', lambda *args, **kwargs: True)
    monkeypatch.setattr(temp_bot, 'check_params', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('should not run')))

    temp_bot.run_bot_cycle()


def test_wait_for_order_fill_raises_for_rejected_order(temp_bot, fake_api):
    fake_api.orders_by_id['bad-order'] = SimpleNamespace(status='rejected', filled_qty='0')
    with pytest.raises(RuntimeError, match='rejected'):
        temp_bot.wait_for_order_fill('bad-order')


def test_run_bot_cycle_sells_when_target_hit(temp_bot, fake_api, monkeypatch):
    row = {
        'Time': '2026-01-01 09:30:00',
        'Ticker': 'AAPL',
        'Type': 'buy',
        'Buy Price': 100.0,
        'Sell Price': '-',
        'Highest Price': 100.0,
        'Quantity': 2.0,
        'Total': 200.0,
        'Acc Balance': 10000.0,
        'Target Price': 105.0,
        'Stop Loss Price': 95.0,
        'ActivateTrailingStopAt': 101.0,
        'Order ID': 'buy-1',
        'Order Status': 'filled',
        'Protective Order ID': 'oco-1',
    }
    pd.DataFrame([row], columns=temp_bot.ORDER_COLUMNS).to_csv(temp_bot.OPEN_ORDERS_FILE, index=False)
    fake_api.positions = [SimpleNamespace(symbol='AAPL', qty='2')]
    fake_api.latest_prices['AAPL'] = 106.0
    monkeypatch.setattr(temp_bot, 'get_open_exposure_count', lambda: temp_bot.max_trades)

    temp_bot.run_bot_cycle()

    open_orders = pd.read_csv(temp_bot.OPEN_ORDERS_FILE)
    orders = pd.read_csv(temp_bot.ORDERS_FILE)
    assert open_orders.empty
    assert orders.iloc[0]['Type'] == 'sell'


def test_run_bot_cycle_updates_trailing_stop_without_selling(temp_bot, fake_api, monkeypatch):
    row = {
        'Time': '2026-01-01 09:30:00',
        'Ticker': 'AAPL',
        'Type': 'buy',
        'Buy Price': 100.0,
        'Sell Price': '-',
        'Highest Price': 100.0,
        'Quantity': 2.0,
        'Total': 200.0,
        'Acc Balance': 10000.0,
        'Target Price': 200.0,
        'Stop Loss Price': 95.0,
        'ActivateTrailingStopAt': 101.0,
        'Order ID': 'buy-1',
        'Order Status': 'filled',
        'Protective Order ID': 'oco-1',
    }
    pd.DataFrame([row], columns=temp_bot.ORDER_COLUMNS).to_csv(temp_bot.OPEN_ORDERS_FILE, index=False)
    fake_api.positions = [SimpleNamespace(symbol='AAPL', qty='2')]
    fake_api.latest_prices['AAPL'] = 110.0
    monkeypatch.setattr(temp_bot, 'get_open_exposure_count', lambda: temp_bot.max_trades)

    temp_bot.run_bot_cycle()

    open_orders = pd.read_csv(temp_bot.OPEN_ORDERS_FILE)
    assert open_orders.iloc[0]['Highest Price'] == 110.0
    assert open_orders.iloc[0]['Stop Loss Price'] > 100
