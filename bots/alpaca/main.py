import pandas as pd
import numpy as np
import json
import math

from datetime import datetime as dt
from datetime import timedelta
import time
import os
import smtplib
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from indicator import *
from config_params import *

# Files


def load_alpaca_auth(path='AUTH/authAlpaca.txt'):
    return json.loads(open(path, 'r').read())


def create_alpaca_api(auth=None):
    import alpaca_trade_api as alpaca

    key = auth if auth is not None else load_alpaca_auth()
    return alpaca.REST(
        key['APCA-API-KEY-ID'],
        key['APCA-API-SECRET-KEY'],
        base_url=key['BASE-URL'],
        api_version='v2'
    )


class LazyAlpacaAPI:
    def __init__(self):
        self._client = None

    def client(self):
        if self._client is None:
            self._client = create_alpaca_api()
        return self._client

    def __getattr__(self, name):
        return getattr(self.client(), name)


api = LazyAlpacaAPI()
tickers = []
_equity_asset_map = None
_equity_asset_map_api_id = None

ORDERS_DIR = 'ORDERS'
ORDERS_FILE = os.path.join(ORDERS_DIR, 'Orders.csv')
OPEN_ORDERS_FILE = os.path.join(ORDERS_DIR, 'Open Orders.csv')
TIME_AND_COINS_FILE = os.path.join(ORDERS_DIR, 'Time and Coins.csv')
ORDER_FILL_TIMEOUT_SECONDS = 60
LOOP_SLEEP_SECONDS = min(max(5, int(sleep_time)), 60)
EASTERN_TZ = ZoneInfo('America/New_York')
SHUTDOWN_HOUR_ET = 15
SHUTDOWN_MINUTE_ET = 45

ORDER_COLUMNS = [
    'Time', 'Ticker', 'Type', 'Buy Price', 'Sell Price', 'Highest Price',
    'Quantity', 'Total', 'Acc Balance', 'Target Price', 'Stop Loss Price',
    'ActivateTrailingStopAt', 'Order ID', 'Order Status', 'Protective Order ID'
]
TIME_COLUMNS = ['Time', 'Ticker']


def ensure_order_storage():
    os.makedirs(ORDERS_DIR, exist_ok=True)
    ensure_csv(ORDERS_FILE, ORDER_COLUMNS)
    ensure_csv(OPEN_ORDERS_FILE, ORDER_COLUMNS)
    ensure_csv(TIME_AND_COINS_FILE, TIME_COLUMNS)


def ensure_csv(path, columns):
    if not os.path.isfile(path):
        pd.DataFrame(columns=columns).to_csv(path, index=False)
        return

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=columns)

    changed = False
    for column in columns:
        if column not in df.columns:
            df[column] = ''
            changed = True

    ordered_columns = columns + [column for column in df.columns if column not in columns]
    if changed or list(df.columns) != ordered_columns:
        df = df[ordered_columns]
        df.to_csv(path, index=False)


def read_csv(path, columns):
    ensure_order_storage()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)


def normalize_symbol(symbol):
    if symbol is None:
        return ''
    return str(symbol).upper().strip()


def to_eastern_time(now=None):
    if now is None:
        return dt.now(EASTERN_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=EASTERN_TZ)
    return now.astimezone(EASTERN_TZ)


def shutdown_time_for_day(now=None):
    eastern_now = to_eastern_time(now)
    return eastern_now.replace(
        hour=SHUTDOWN_HOUR_ET,
        minute=SHUTDOWN_MINUTE_ET,
        second=0,
        microsecond=0
    )


def is_shutdown_time(now=None):
    return to_eastern_time(now) >= shutdown_time_for_day(now)


def seconds_until_shutdown(now=None):
    eastern_now = to_eastern_time(now)
    return max(0, (shutdown_time_for_day(eastern_now) - eastern_now).total_seconds())


def get_loop_sleep_seconds(now=None):
    return min(LOOP_SLEEP_SECONDS, seconds_until_shutdown(now))


def dedupe_symbols(symbols):
    seen = set()
    normalized_symbols = []
    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_symbols.append(normalized)
    return normalized_symbols


def chunked(items, chunk_size):
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def read_static_tickers():
    try:
        with open('AUTH/Tickers.txt', 'r') as ticker_file:
            return dedupe_symbols(ticker_file.read().split())
    except Exception as e:
        print('Error reading AUTH/Tickers.txt:', e)
        return []


def price_passes_dynamic_filter(price):
    if price is None:
        return True
    try:
        price = float(price)
    except Exception:
        return False
    if dynamic_tickers_min_price is not None and price < dynamic_tickers_min_price:
        return False
    if dynamic_tickers_max_price is not None and price > dynamic_tickers_max_price:
        return False
    return True


def get_equity_asset_map():
    global _equity_asset_map
    global _equity_asset_map_api_id

    current_api_id = id(api)
    if _equity_asset_map is not None and _equity_asset_map_api_id == current_api_id:
        return _equity_asset_map

    try:
        assets = api.list_assets(status='active', asset_class='us_equity')
    except Exception as e:
        print('Error fetching Alpaca asset metadata; using symbols without asset filtering:', e)
        return None

    _equity_asset_map = {}
    for asset in assets:
        symbol = normalize_symbol(getattr(asset, 'symbol', ''))
        if symbol:
            _equity_asset_map[symbol] = asset
    _equity_asset_map_api_id = current_api_id
    return _equity_asset_map


def get_equity_asset(symbol):
    asset_map = get_equity_asset_map()
    if asset_map is None:
        return None
    return asset_map.get(normalize_symbol(symbol))


def get_tradable_equity_symbols():
    asset_map = get_equity_asset_map()
    if asset_map is None:
        return None

    tradable_symbols = set()
    for symbol, asset in asset_map.items():
        if getattr(asset, 'tradable', False):
            tradable_symbols.add(symbol)
    return tradable_symbols


def get_dynamic_mover_tickers():
    response = api.data_get(
        '/screener/stocks/movers',
        data={'top': dynamic_tickers_top_per_side},
        api_version='v1beta1'
    )
    tradable_symbols = get_tradable_equity_symbols()
    movers = []
    if dynamic_tickers_include_gainers:
        movers.extend(response.get('gainers', []))
    if dynamic_tickers_include_losers:
        movers.extend(response.get('losers', []))

    selected_symbols = []
    for mover in movers:
        symbol = normalize_symbol(mover.get('symbol'))
        if not symbol:
            continue
        if tradable_symbols is not None and symbol not in tradable_symbols:
            continue
        if not price_passes_dynamic_filter(mover.get('price')):
            continue
        selected_symbols.append(symbol)

    selected_symbols = dedupe_symbols(selected_symbols)
    print('Loaded {} dynamic tickers from Alpaca market movers updated at {}'.format(
        len(selected_symbols), response.get('last_updated', 'unknown time')
    ))
    print('Dynamic tickers:', selected_symbols)
    return selected_symbols


def load_tickers():
    fallback_tickers = read_static_tickers()
    if not dynamic_tickers_enabled:
        print('Dynamic tickers disabled; using static tickers:', fallback_tickers)
        return fallback_tickers

    try:
        dynamic_symbols = get_dynamic_mover_tickers()
    except Exception as e:
        print('Error fetching Alpaca market movers; using static fallback tickers:', e)
        return fallback_tickers

    if not dynamic_symbols:
        print('No dynamic tickers returned; using static fallback tickers:', fallback_tickers)
        return fallback_tickers
    return dynamic_symbols


def format_qty(quantity):
    return f'{float(quantity):.6f}'.rstrip('0').rstrip('.')


def format_price(price):
    return round(float(price), 2)


def prepare_buy_quantity(symbol, quantity):
    quantity = float(quantity)
    if quantity <= 0:
        return 0

    asset = get_equity_asset(symbol)
    if asset is None or getattr(asset, 'fractionable', False):
        return quantity

    whole_share_quantity = math.floor(quantity)
    if whole_share_quantity <= 0:
        print(f'Skipping {normalize_symbol(symbol)}; asset is not fractionable and buy amount is below one share')
        return 0

    if whole_share_quantity != quantity:
        print(
            f'Adjusting {normalize_symbol(symbol)} quantity from {format_qty(quantity)} '
            f'to {whole_share_quantity}; asset does not support fractional trading'
        )
    return float(whole_share_quantity)


def get_account_float(attribute):
    account = api.get_account()
    return float(getattr(account, attribute))


def get_alpaca_positions():
    try:
        return {normalize_symbol(position.symbol): position for position in api.list_positions()}
    except Exception as e:
        print('Error fetching Alpaca positions:', e)
        return {}


def get_open_order_symbols(side=None):
    try:
        orders = api.list_orders(status='open', direction='desc')
    except Exception as e:
        print('Error fetching Alpaca open orders:', e)
        return set()

    symbols = set()
    for order in orders:
        if side is None or str(order.side).lower() == side:
            symbols.add(normalize_symbol(order.symbol))
    return symbols


def cancel_all_open_orders():
    try:
        orders = api.list_orders(status='open', direction='desc')
    except Exception as e:
        print('Error fetching Alpaca open orders for shutdown:', e)
        return 0

    canceled_count = 0
    for order in orders:
        try:
            api.cancel_order(order.id)
            canceled_count += 1
        except Exception as e:
            print(f'Error canceling open order {order.id} for shutdown:', e)
    return canceled_count


def get_local_open_symbols():
    df = read_csv(OPEN_ORDERS_FILE, ORDER_COLUMNS)
    if df.empty or 'Ticker' not in df.columns:
        return set()
    return {normalize_symbol(symbol) for symbol in df['Ticker'].dropna()}


def has_open_exposure(symbol):
    symbol = normalize_symbol(symbol)
    return (
        symbol in get_alpaca_positions()
        or symbol in get_open_order_symbols('buy')
        or symbol in get_local_open_symbols()
    )


def get_open_exposure_count():
    return len(
        set(get_alpaca_positions())
        | get_open_order_symbols('buy')
        | get_local_open_symbols()
    )


def cancel_open_sell_orders(symbol):
    symbol = normalize_symbol(symbol)
    try:
        orders = api.list_orders(status='open', direction='desc')
    except Exception as e:
        print(f'Error fetching open sell orders for {symbol}:', e)
        return

    for order in orders:
        if normalize_symbol(order.symbol) == symbol and str(order.side).lower() == 'sell':
            try:
                api.cancel_order(order.id)
            except Exception as e:
                print(f'Error canceling protective sell order {order.id} for {symbol}:', e)


def get_account_cash_value():
    try:
        return api.get_account().cash
    except Exception as e:
        print('Error fetching account cash for order log:', e)
        return ''


def get_local_open_order_value(local_open_orders, symbol, column, default='-'):
    if local_open_orders.empty or column not in local_open_orders.columns:
        return default

    ticker_matches = local_open_orders['Ticker'].map(normalize_symbol) == symbol
    matching_rows = local_open_orders[ticker_matches]
    if matching_rows.empty:
        return default

    value = matching_rows.iloc[0][column]
    if pd.isna(value) or value == '':
        return default
    return value


def parse_optional_float(value, default=None):
    if value is None or value == '' or value == '-':
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return default


def remove_closed_local_open_orders(closed_symbols):
    if not closed_symbols:
        return

    df = read_csv(OPEN_ORDERS_FILE, ORDER_COLUMNS)
    if df.empty or 'Ticker' not in df.columns:
        return

    keep_rows = ~df['Ticker'].map(normalize_symbol).isin(closed_symbols)
    df.loc[keep_rows].to_csv(OPEN_ORDERS_FILE, index=False)


def log_shutdown_order(position, filled_order, side, filled_qty, filled_price, local_open_orders):
    symbol = normalize_symbol(position.symbol)
    buy_price = get_local_open_order_value(local_open_orders, symbol, 'Buy Price')
    if buy_price == '-':
        buy_price = getattr(position, 'avg_entry_price', '-')

    highest_price = get_local_open_order_value(local_open_orders, symbol, 'Highest Price', buy_price)
    total = '-'
    if filled_price is not None:
        total = filled_qty * filled_price

    row = {
        'Time': dt.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Ticker': symbol,
        'Type': f'shutdown_{side}',
        'Buy Price': buy_price,
        'Sell Price': filled_price if filled_price is not None else '-',
        'Highest Price': highest_price,
        'Quantity': filled_qty,
        'Total': total,
        'Acc Balance': get_account_cash_value(),
        'Target Price': '-',
        'Stop Loss Price': '-',
        'ActivateTrailingStopAt': '-',
        'Order ID': filled_order.id,
        'Order Status': filled_order.status,
        'Protective Order ID': '-',
    }

    df = read_csv(ORDERS_FILE, ORDER_COLUMNS)
    df.loc[len(df.index)] = [row.get(column, '') for column in ORDER_COLUMNS]
    df.to_csv(ORDERS_FILE, index=False)


def flatten_all_positions():
    ensure_order_storage()
    canceled_count = cancel_all_open_orders()
    if canceled_count:
        print(f'Canceled {canceled_count} open Alpaca orders before shutdown flatten')

    try:
        positions = api.list_positions()
    except Exception as e:
        print('Error fetching Alpaca positions for shutdown:', e)
        return set()

    local_open_orders = read_csv(OPEN_ORDERS_FILE, ORDER_COLUMNS)
    attempted_symbols = set()

    for position in list(positions):
        symbol = normalize_symbol(position.symbol)
        quantity = parse_optional_float(getattr(position, 'qty', None), 0)
        if not symbol or quantity == 0:
            continue

        side = 'sell' if quantity > 0 else 'buy'
        close_qty = abs(quantity)
        attempted_symbols.add(symbol)
        try:
            order = api.submit_order(
                symbol=symbol,
                qty=format_qty(close_qty),
                side=side,
                type='market',
                time_in_force='day'
            )
            filled_order = wait_for_order_fill(order.id)
            filled_qty = parse_optional_float(getattr(filled_order, 'filled_qty', None), close_qty)
            filled_price = parse_optional_float(getattr(filled_order, 'filled_avg_price', None))
            log_shutdown_order(position, filled_order, side, filled_qty, filled_price, local_open_orders)
            print(f'Shutdown flatten order filled for {filled_qty} {symbol}')
        except Exception as e:
            print(f'Error flattening {symbol} during shutdown:', e)

    try:
        remaining_symbols = {normalize_symbol(position.symbol) for position in api.list_positions()}
    except Exception as e:
        print('Error verifying positions after shutdown flatten:', e)
        remaining_symbols = attempted_symbols

    closed_symbols = attempted_symbols - remaining_symbols
    remove_closed_local_open_orders(closed_symbols)
    return closed_symbols


def wait_for_order_fill(order_id, timeout_seconds=ORDER_FILL_TIMEOUT_SECONDS):
    deadline = time.time() + timeout_seconds
    last_order = None

    while time.time() < deadline:
        last_order = api.get_order(order_id)
        status = str(last_order.status).lower()
        filled_qty = float(last_order.filled_qty or 0)

        if status == 'filled':
            return last_order
        if filled_qty > 0 and status in ('canceled', 'expired'):
            return last_order
        if status in ('rejected', 'canceled', 'expired'):
            raise RuntimeError(f'Order {order_id} ended with status {status}')
        time.sleep(1)

    try:
        api.cancel_order(order_id)
    except Exception as e:
        print(f'Order {order_id} did not fill before timeout and could not be canceled:', e)

    last_order = api.get_order(order_id)
    if float(last_order.filled_qty or 0) > 0:
        return last_order
    raise TimeoutError(f'Order {order_id} did not fill within {timeout_seconds} seconds')


def submit_protective_order(symbol, quantity, target_price, stop_loss_price):
    try:
        order = api.submit_order(
            symbol=symbol,
            qty=format_qty(quantity),
            side='sell',
            type='limit',
            time_in_force='gtc',
            limit_price=format_price(target_price),
            order_class='oco',
            stop_loss={'stop_price': format_price(stop_loss_price)}
        )
        return order.id
    except Exception as e:
        print(f'Could not place broker-native protective order for {symbol}; local polling remains active:', e)
        return ''


def reconcile_open_orders_with_alpaca():
    df = read_csv(OPEN_ORDERS_FILE, ORDER_COLUMNS)
    if df.empty:
        return df

    positions = get_alpaca_positions()
    keep_indexes = []
    for i in list(df.index):
        ticker = normalize_symbol(df.loc[i, 'Ticker'])
        position = positions.get(ticker)
        if position is None:
            print(f'Removing stale local open order for {ticker}; no Alpaca position exists')
            continue
        df.loc[i, 'Quantity'] = float(position.qty)
        keep_indexes.append(i)

    df = df.loc[keep_indexes]
    df.to_csv(OPEN_ORDERS_FILE, index=False)
    return df


def place_buy_signal(ticker):
    if is_shutdown_time():
        print('Shutdown cutoff reached; skipping new buy signal')
        return False

    mail_content = buy(ticker)
    if mail_content:
        mail_alert(mail_content, 0)
    return get_open_exposure_count() < max_trades


def update_ticker_cooldown():
    df = read_csv(TIME_AND_COINS_FILE, TIME_COLUMNS)
    if df.empty:
        return set()

    keep_indexes = []
    for i in list(df.index):
        try:
            prev_time = dt.strptime(df.loc[i, 'Time'], "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
        if (dt.now() - prev_time).total_seconds() < sleep_time:
            keep_indexes.append(i)

    df = df.loc[keep_indexes]
    df.to_csv(TIME_AND_COINS_FILE, index=False)
    return {normalize_symbol(symbol) for symbol in df['Ticker'].dropna()}

def get_timeframe(timeframe):
    try:
        from alpaca_trade_api.rest import TimeFrame
    except ImportError:
        return timeframe

    tf_map = {
        "1Minute": TimeFrame.Minute,
        "1Hour": TimeFrame.Hour,
        "1Day": TimeFrame.Day
    }
    return tf_map.get(timeframe, TimeFrame.Minute)


def get_data_window(start_date):
    start_dt = (dt.now() - timedelta(days=start_date)).strftime("%Y-%m-%d")
    if str(end_date).lower() in ('now', 'today'):
        end_dt = dt.now().strftime("%Y-%m-%d")
    else:
        end_dt = pd.to_datetime(end_date).strftime("%Y-%m-%d")
    return start_dt, end_dt


def normalize_bars_dataframe(df, fallback_symbol=None):
    if df.empty:
        return df

    df.reset_index(inplace=True)
    rename_columns = {
        'timestamp': 'Timestamp',
        'symbol': 'Symbol',
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close'
    }
    df.rename(columns=rename_columns, inplace=True)
    if 'Symbol' not in df.columns and fallback_symbol is not None:
        df['Symbol'] = fallback_symbol
    return df


# Function to fetch data
def get_data(ticker, timeframe= timeframe, start_date = int(start_date)):
    try:
        tf = get_timeframe(timeframe)
        start_dt, end_dt = get_data_window(start_date)
        df = api.get_bars(ticker, tf, start_dt, end_dt, adjustment='raw', feed=market_data_feed).df
        if not df.empty:
            df = normalize_bars_dataframe(df, normalize_symbol(ticker))
            df = df[['Timestamp', 'Open', 'High', 'Low', 'Close']]
        return df
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()


def get_data_for_tickers(tickers, timeframe=timeframe, start_date=int(start_date)):
    ticker_list = dedupe_symbols(tickers)
    data_by_ticker = {ticker: pd.DataFrame() for ticker in ticker_list}
    if not ticker_list:
        return data_by_ticker

    tf = get_timeframe(timeframe)
    start_dt, end_dt = get_data_window(start_date)

    for ticker_batch in chunked(ticker_list, bar_request_chunk_size):
        try:
            df = api.get_bars(ticker_batch, tf, start_dt, end_dt, adjustment='raw', feed=market_data_feed).df
        except Exception as e:
            print(f"Error fetching batch data for {ticker_batch}: {e}")
            continue

        if df.empty:
            continue

        df = normalize_bars_dataframe(df)
        if 'Symbol' not in df.columns:
            if len(ticker_batch) == 1:
                df['Symbol'] = ticker_batch[0]
            else:
                print(f"Batch data did not include symbols for {ticker_batch}; skipping batch")
                continue

        for ticker, ticker_df in df.groupby('Symbol'):
            ticker = normalize_symbol(ticker)
            data_by_ticker[ticker] = ticker_df[['Timestamp', 'Open', 'High', 'Low', 'Close']].copy()

    return data_by_ticker

def has_recent_signal(df, column):
    if column not in df.columns:
        return False
    return 1 in list(df[column].fillna(0).iloc[-lookback_period:])


def check_params(tickers, run):
    tickers_check = dedupe_symbols(tickers)
    data_by_ticker = get_data_for_tickers(tickers_check)

    for ticker in tickers_check:
        print("Fetching Data for:", ticker)
        if run == False or is_shutdown_time():
            break
        df = data_by_ticker.get(ticker, pd.DataFrame())
        if df.empty:
            print(f'No data returned for {ticker}; skipping')
            continue
        print(df.tail())

        signal_columns = []
        enabled_indicators = []

        if stoch:
            print("Calculating Signals for Stoch")
            df = stochastic(df, TYPE='Stoch')
            signal_columns.append(('Stoch', 'Stoch Signal'))
            enabled_indicators.append('Stoch')

        if stoch_rsi:
            print("Calculating Signals for StochRSI")
            df = rsi(df)
            df = stochastic(df, TYPE='StochRSI')
            signal_columns.append(('StochRSI', 'StochRSI Signal'))
            enabled_indicators.append('StochRSI')

        if ema:
            print("Calculating Signals for EMA")
            df = implement_ema_strategy(df)
            enabled_indicators.append('EMA')

        if not enabled_indicators:
            print('Please enable at least one indicator in ConfigFile.txt')
            continue

        if ema and not signal_columns:
            signal_columns.append(('EMA', 'EMA Signal'))

        missing_signals = [name for name, column in signal_columns if not has_recent_signal(df, column)]
        ema_filter_passes = True
        if ema and any(name != 'EMA' for name, _ in signal_columns):
            ema_filter_passes = bool(df['EMA Above'].fillna(0).iloc[-1] == 1)

        if not missing_signals and ema_filter_passes:
            run = place_buy_signal(ticker)
            continue

        reason_parts = []
        if missing_signals:
            reason_parts.append('missing recent signal from {}'.format(', '.join(missing_signals)))
        if not ema_filter_passes:
            reason_parts.append('price is not above EMA')
        print('No Buy Signal Found for {} ({})'.format(' + '.join(enabled_indicators), '; '.join(reason_parts)))

def order_files(coin_to_buy, price_coin, highest_price, targetPositionSize, target_price,
                stop_loss_price, ActivateTrailingStopAt, order_id='', order_status='',
                protective_order_id=''):
    ensure_order_storage()
    row = {
        'Time': dt.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Ticker': normalize_symbol(coin_to_buy),
        'Type': 'buy',
        'Buy Price': price_coin,
        'Sell Price': '-',
        'Highest Price': highest_price,
        'Quantity': targetPositionSize,
        'Total': targetPositionSize * price_coin,
        'Acc Balance': api.get_account().cash,
        'Target Price': target_price,
        'Stop Loss Price': stop_loss_price,
        'ActivateTrailingStopAt': ActivateTrailingStopAt,
        'Order ID': order_id,
        'Order Status': order_status,
        'Protective Order ID': protective_order_id,
    }

    df = read_csv(ORDERS_FILE, ORDER_COLUMNS)
    df.loc[len(df.index)] = [row.get(column, '') for column in ORDER_COLUMNS]
    df.to_csv(ORDERS_FILE, index=False)

    df1 = read_csv(TIME_AND_COINS_FILE, TIME_COLUMNS)
    df1.loc[len(df1.index)] = [row['Time'], row['Ticker']]
    df1.to_csv(TIME_AND_COINS_FILE, index=False)

    df2 = read_csv(OPEN_ORDERS_FILE, ORDER_COLUMNS)
    df2.loc[len(df2.index)] = [row.get(column, '') for column in ORDER_COLUMNS]
    df2.to_csv(OPEN_ORDERS_FILE, index=False)


def buy(coin_to_buy: str, trade_cap_percent=trade_capital_percent):
    ensure_order_storage()
    coin_to_buy = normalize_symbol(coin_to_buy)

    if is_shutdown_time():
        print(f'Skipping {coin_to_buy}; shutdown cutoff has been reached')
        return None

    if has_open_exposure(coin_to_buy):
        print(f'Skipping {coin_to_buy}; Alpaca or local state already has exposure')
        return None

    cash_available = min(
        max_investment_amount,
        get_account_float('cash'),
        get_account_float('buying_power')
    )
    buy_amount = cash_available * (trade_cap_percent * 0.01)
    if buy_amount <= 0:
        print(f'Skipping {coin_to_buy}; no cash available for trade')
        return None

    estimated_price = api.get_latest_trade(coin_to_buy, feed=market_data_feed).p
    targetPositionSize = float(buy_amount) / float(estimated_price)
    targetPositionSize = prepare_buy_quantity(coin_to_buy, targetPositionSize)
    if targetPositionSize <= 0:
        print(f'Skipping {coin_to_buy}; calculated quantity is zero')
        return None

    print(coin_to_buy, targetPositionSize)
    order = api.submit_order(
        symbol=coin_to_buy,
        qty=format_qty(targetPositionSize),
        side='buy',
        type='market',
        time_in_force='day'
    )
    filled_order = wait_for_order_fill(order.id)
    filled_qty = float(filled_order.filled_qty or targetPositionSize)
    price_coin = float(filled_order.filled_avg_price or estimated_price)

    if filled_qty <= 0:
        raise RuntimeError(f'Buy order {order.id} for {coin_to_buy} completed without a fill')

    stop_loss_price = price_coin * (1 - (stop_loss * 0.01))
    ActivateTrailingStopAt = price_coin * (1 + (activate_trailing_stop_loss_at * 0.01))
    target_price = price_coin * (1 + (limit_price * 0.01))
    highest_price = price_coin
    protective_order_id = submit_protective_order(coin_to_buy, filled_qty, target_price, stop_loss_price)

    mail_content = '''TRADE ALERT: BUY Order Filled for {} {} at ${}'''.format(filled_qty, coin_to_buy, price_coin)
    print(mail_content)

    order_files(
        coin_to_buy, price_coin, highest_price, filled_qty, target_price,
        stop_loss_price, ActivateTrailingStopAt, filled_order.id, filled_order.status,
        protective_order_id
    )

    return mail_content


def sell(current_coin, quantity, buy_price, highest_price):
    current_coin = normalize_symbol(current_coin)
    cancel_open_sell_orders(current_coin)
    sell_price = api.get_latest_trade(str(current_coin), feed=market_data_feed).p

    order = api.submit_order(
        symbol=current_coin,
        qty=format_qty(quantity),
        side='sell',
        type='market',
        time_in_force='day'
    )
    filled_order = wait_for_order_fill(order.id)
    filled_qty = float(filled_order.filled_qty or quantity)
    filled_price = float(filled_order.filled_avg_price or sell_price)
    mail_content = '''TRADE ALERT: SELL Order Filled for {} {} at ${}'''.format(filled_qty, current_coin, filled_price)
    df = read_csv(ORDERS_FILE, ORDER_COLUMNS)

    row = {
        'Time': dt.now().strftime("%Y-%m-%d %H:%M:%S"),
        'Ticker': current_coin,
        'Type': 'sell',
        'Buy Price': buy_price,
        'Sell Price': filled_price,
        'Highest Price': highest_price,
        'Quantity': filled_qty,
        'Total': filled_qty * filled_price,
        'Acc Balance': api.get_account().cash,
        'Target Price': '-',
        'Stop Loss Price': '-',
        'ActivateTrailingStopAt': '-',
        'Order ID': filled_order.id,
        'Order Status': filled_order.status,
        'Protective Order ID': '-',
    }
    df.loc[len(df.index)] = [row.get(column, '') for column in ORDER_COLUMNS]
    df.to_csv(ORDERS_FILE, index=False)
    return mail_content


def mail_alert(mail_content, sleep_time):
    # The mail addresses and password
    sender_address = 'sender_address'
    sender_pass = 'sender_pass'
    receiver_address = 'receiver_address'

    if sender_address == 'sender_address':
        print("Mail alert not configured, skipping:", mail_content)
        return

    try:
        # Setup MIME
        message = MIMEMultipart()
        message['From'] = 'Trading Bot'
        message['To'] = receiver_address
        message['Subject'] = 'Technical Trading Bot'
        
        # The body and the attachments for the mail
        message.attach(MIMEText(mail_content, 'plain'))

        # Create SMTP session for sending the mail
        session = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
        session.starttls()  # enable security

        # login with mail_id and password
        session.login(sender_address, sender_pass)
        text = message.as_string()
        session.sendmail(sender_address, receiver_address, text)
        session.quit()
    except Exception as e:
        print("Failed to send email:", e)
    finally:
        time.sleep(sleep_time)

def initialize_bot():
    global tickers
    ensure_order_storage()
    api.list_positions()
    tickers = load_tickers()
    mail_alert(
        "The Bot Started Running on {} at {} with {} tickers".format(
            dt.now().strftime("%Y-%m-%d"),
            dt.now().strftime("%H:%M:%S"),
            len(tickers)
        ),
        0
    )


def run_bot_cycle():
    df = reconcile_open_orders_with_alpaca()
    if df.empty:
        print("No Open Positions, Generating Signals")
    else:
        print('Checking Returns')
        positions = get_alpaca_positions()
        for i in list(df.index):
            ticker = normalize_symbol(df.loc[i, 'Ticker'])
            position = positions.get(ticker)
            if position is None:
                continue

            quantity = float(position.qty)
            curr_price = api.get_latest_trade(ticker, feed=market_data_feed).p
            trailingStopActivatePrice = float(df.loc[i, 'ActivateTrailingStopAt'])
            target_price = float(df.loc[i, 'Target Price'])
            highest_price_since_buy = float(df.loc[i, 'Highest Price'])
            buy_price = float(df.loc[i, 'Buy Price'])

            if (curr_price >= trailingStopActivatePrice) and (curr_price > highest_price_since_buy):
                new_stop_loss = curr_price * (1 - (trailing_stop * 0.01))
                df.loc[i, 'Stop Loss Price'] = new_stop_loss
                df.loc[i, 'Highest Price'] = curr_price
                highest_price_since_buy = curr_price

            lower_limit_price = float(df.loc[i, 'Stop Loss Price'])

            if (curr_price <= lower_limit_price) or (curr_price >= target_price):
                mail_content = sell(ticker, quantity, buy_price, highest_price_since_buy)
                mail_alert(mail_content, 0)
                df.drop(index=i, inplace=True)

        df.to_csv(OPEN_ORDERS_FILE, index=False)
        print("Returns Checked")

    open_positions = get_open_exposure_count()

    print("Open_Positions < Max_Trades", open_positions < max_trades)
    print("Open Positions:", open_positions)
    print("Max Trades:", max_trades)

    if is_shutdown_time():
        print('Shutdown cutoff reached; skipping new buy generation')
        return

    if open_positions < max_trades:
        run = True
        cooldown_tickers = update_ticker_cooldown()
        held_tickers = set(get_alpaca_positions()) | get_open_order_symbols('buy') | get_local_open_symbols()
        tickers_check = [
            ticker for ticker in tickers
            if normalize_symbol(ticker) not in cooldown_tickers
            and normalize_symbol(ticker) not in held_tickers
        ]

        print("Checking Params for {}".format(tickers_check))
        check_params(tickers_check, run)


def handle_cycle_error(error):
    print(error)
    try:
        mail_alert("The Bot Stopped Running on {} at {}".format(dt.now().strftime("%Y-%m-%d"), dt.now().strftime("%H:%M:%S")), 0)
    except Exception as mail_err:
        print("Could not send alert mail:", mail_err)
    print("Sleeping before retrying...")
    retry_sleep_seconds = min(30, seconds_until_shutdown())
    if retry_sleep_seconds > 0:
        time.sleep(retry_sleep_seconds)


def perform_scheduled_shutdown():
    print('Scheduled shutdown cutoff reached; flattening all Alpaca positions')
    closed_symbols = flatten_all_positions()
    mail_alert(
        "The Bot Flattened {} positions and Stopped Running on {} at {} ET".format(
            len(closed_symbols),
            dt.now(EASTERN_TZ).strftime("%Y-%m-%d"),
            dt.now(EASTERN_TZ).strftime("%H:%M:%S")
        ),
        0
    )
    print('Scheduled shutdown complete')


def mainNEW():
    try:
        initialize_bot()
    except Exception as e:
        print("Error connecting to Alpaca API:", e)
        return

    while True:
        try:
            if is_shutdown_time():
                perform_scheduled_shutdown()
                return
            run_bot_cycle()
        except Exception as e:
            handle_cycle_error(e)
        finally:
            sleep_seconds = get_loop_sleep_seconds()
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            
if __name__ == "__main__":
    mainNEW()
