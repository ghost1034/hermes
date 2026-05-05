import pandas as pd
import numpy as np
import json

from datetime import datetime as dt
from datetime import timedelta
import time
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import alpaca_trade_api as alpaca
from indicator import *
from config_params import *

# Files
key = json.loads(open('AUTH/authAlpaca.txt', 'r').read())
api = alpaca.REST(key['APCA-API-KEY-ID'], key['APCA-API-SECRET-KEY'], base_url= key['BASE-URL'], api_version = 'v2')
tickers = open('AUTH/Tickers.txt', 'r').read() # Tickers
tickers = tickers.split()

ORDERS_DIR = 'ORDERS'
ORDERS_FILE = os.path.join(ORDERS_DIR, 'Orders.csv')
OPEN_ORDERS_FILE = os.path.join(ORDERS_DIR, 'Open Orders.csv')
TIME_AND_COINS_FILE = os.path.join(ORDERS_DIR, 'Time and Coins.csv')
ORDER_FILL_TIMEOUT_SECONDS = 60
LOOP_SLEEP_SECONDS = min(max(5, int(sleep_time)), 60)

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
    return str(symbol).upper().strip()


def format_qty(quantity):
    return f'{float(quantity):.6f}'.rstrip('0').rstrip('.')


def format_price(price):
    return round(float(price), 2)


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

# Function to fetch data
def get_data(ticker, timeframe= timeframe, start_date = int(start_date)):
    try:
        # TimeFrame mapping
        from alpaca_trade_api.rest import TimeFrame
        tf_map = {
            "1Minute": TimeFrame.Minute,
            "1Hour": TimeFrame.Hour,
            "1Day": TimeFrame.Day
        }
        tf = tf_map.get(timeframe, TimeFrame.Minute)
        
        start_dt = (dt.now() - timedelta(days = start_date)).strftime("%Y-%m-%d")
        if str(end_date).lower() in ('now', 'today'):
            end_dt = dt.now().strftime("%Y-%m-%d")
        else:
            end_dt = pd.to_datetime(end_date).strftime("%Y-%m-%d")
        df = api.get_bars(ticker, tf, start_dt, end_dt, adjustment='raw').df
        if not df.empty:
            df.reset_index(inplace = True)
            df = df[['timestamp', 'open', 'high', 'low', 'close']]
            df.columns = ['Timestamp', 'Open', 'High', 'Low', 'Close']
        return df
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()

def check_params(tickers, run):
    tickers_check = tickers

    for ticker in tickers_check:
        print("Fetching Data for:", ticker)
        if run == False:
            break
        df = get_data(ticker)
        if df.empty:
            print(f'No data returned for {ticker}; skipping')
            continue
        print(df.tail())

        if stoch == 'True' and stoch_rsi == 'False' and ema == 'False': # Stoch
            df = stochastic(df, TYPE = 'Stoch')
            print("Calculating Signals for Stoch")
            signal_list = list(df['Stoch Signal'].iloc[ -lookback_period : ])

            signal_count = 0
            for signal in signal_list:
                signal_count += 1
                
                if signal == 1:
                    run = place_buy_signal(ticker)
                    break
            if signal_count == lookback_period:
                print('No Buy Signal Found for Stoch')
                    
        elif stoch == 'False' and stoch_rsi == 'True' and ema == 'False': # StochRSI
            print("Calculating Signals for StochRSI")
            df = rsi(df)
            df = stochastic(df, TYPE = 'StochRSI')

            signal_list = list(df['StochRSI Signal'].iloc[ -lookback_period : ])

            signal_count = 0
            for signal in signal_list:
                signal_count += 1
                # print(signal)
                if signal == 1:
                    run = place_buy_signal(ticker)
                    break
            if signal_count == lookback_period:
                print('No Buy Signal Found for StochRSI')

        elif stoch == 'False' and stoch_rsi == 'False' and ema == 'True': # EMA
            print("Calculating Signals for EMA")
            df = implement_ema_strategy(df)

            signal_list = list(df['EMA Signal'].iloc[ -lookback_period : ])

            signal_count = 0

            for signal in signal_list:
                signal_count += 1
                if signal == 1:
                    run = place_buy_signal(ticker)
                    break
            if signal_count == lookback_period:
                print('No Buy Signal found for EMA')

        elif stoch == 'True' and stoch_rsi == 'True' and ema == 'True': # All 3
            print("Calculating Signals for Stoch + StochRSI + EMA")
            df = stochastic(df, TYPE = 'Stoch')
            
            df = rsi(df)
            df = stochastic(df, TYPE = 'StochRSI')
            df = implement_ema_strategy(df)

            stoch_signal_list = list(df['Stoch Signal'].iloc[ -lookback_period : ])
            stochRSI_signal_list = list(df['StochRSI Signal'].iloc[ -lookback_period : ])
            ema_signal_list = list(df['EMA Signal'].iloc[ -lookback_period : ])

            trade_decision_list = []

            for signal in stoch_signal_list:
                if signal == 1:
                    trade_decision_list.append(signal)
                    break
            for signal in stochRSI_signal_list:
                if signal == 1:
                    trade_decision_list.append(signal)
                    break
            for signal in ema_signal_list:
                if signal == 1:
                    trade_decision_list.append(signal)
                    break

            if len(trade_decision_list) == 3:
                run = place_buy_signal(ticker)
            # elif len(trade_decision_list) < 3:
            else:
                print('No Buy Signal Found for Stoch + StochRSI + EMA')
                continue


        elif stoch == 'True' and stoch_rsi == 'True' and ema == 'False': # Stoch + StochRSI
            print("Calculating Signals for Stoch + StochRSI")
            df = stochastic(df, TYPE = 'Stoch')
            df = rsi(df)
            df = stochastic(df, TYPE = 'StochRSI')

            stoch_signal_list = list(df['Stoch Signal'].iloc[ -lookback_period : ])
            stochRSI_signal_list = list(df['StochRSI Signal'].iloc[ -lookback_period : ])

            trade_decision_list = []

            for signal in stoch_signal_list:
                if signal == 1:
                    trade_decision_list.append(signal)
                    break
            for signal in stochRSI_signal_list:
                if signal == 1:
                    trade_decision_list.append(signal)
                    break

            if len(trade_decision_list) == 2:
                run = place_buy_signal(ticker)
            # elif len(trade_decision_list) < 3:
            else:
                print("No Buy Signal Found for Stoch + StochRSI")
                continue


        elif stoch_rsi == 'True' and ema == 'True' and stoch == 'False': # StochRSI + EMA
            print("Calculating Signals for StochRSI + EMA")
            df = rsi(df)
            df = stochastic(df, TYPE = 'StochRSI')

            df = implement_ema_strategy(df)

            stochRSI_signal_list = list(df['StochRSI Signal'].iloc[ -lookback_period : ])
            ema_signal_list = list(df['EMA Signal'].iloc[ -lookback_period : ])

            trade_decision_list = []

            for signal in stochRSI_signal_list:
                if signal == 1:
                    trade_decision_list.append(signal)
                    break
            for signal in ema_signal_list:
                if signal == 1:
                    trade_decision_list.append(signal)
                    break

            if len(trade_decision_list) == 2:
                run = place_buy_signal(ticker)
            else:
                print('No Buy Signal Found for StochRSI + EMA')
                continue

                
        elif stoch_rsi == 'False' and ema == 'True' and stoch == 'True': # EMA + Stoch
            print("Calculating Signals for EMA + Stoch")
            df = stochastic(df, TYPE = "Stoch")
            df = implement_ema_strategy(df)

            stoch_signal_list = list(df['Stoch Signal'].iloc[ -lookback_period : ])
            ema_signal_list = list(df['EMA Signal'].iloc[ -lookback_period : ])

            trade_decision_list = []

            for signal in stoch_signal_list:
                if signal == 1:
                    trade_decision_list.append(signal)
                    break
            for signal in ema_signal_list:
                if signal == 1:
                    trade_decision_list.append(signal)
                    break

            if len(trade_decision_list) == 2:
                run = place_buy_signal(ticker)
            else:
                print('No Buy Signal Found for EMA + Stoch')
                continue

        else:
            print('Please select any 1 indicator by changing indicator setting to "True"')

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

    if has_open_exposure(coin_to_buy):
        print(f'Skipping {coin_to_buy}; Alpaca or local state already has exposure')
        return None

    cash_available = min(
        investment_amount,
        get_account_float('cash'),
        get_account_float('buying_power')
    )
    buy_amount = cash_available * (trade_cap_percent * 0.01)
    if buy_amount <= 0:
        print(f'Skipping {coin_to_buy}; no cash available for trade')
        return None

    estimated_price = api.get_latest_trade(coin_to_buy).p
    targetPositionSize = float(buy_amount) / float(estimated_price)
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
    sell_price = api.get_latest_trade(str(current_coin)).p

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

def mainNEW():
        try:
            ensure_order_storage()
            api.list_positions()
        except Exception as e:
            print("Error connecting to Alpaca API:", e)
            return

        mail_alert("The Bot Started Running on {} at {}".format(dt.now().strftime("%Y-%m-%d"), dt.now().strftime("%H:%M:%S")), 0)
        while True:
            try:
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
                        curr_price = api.get_latest_trade(ticker).p
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
            except Exception as e:
                print(e)
                try:
                    mail_alert("The Bot Stopped Running on {} at {}".format(dt.now().strftime("%Y-%m-%d"), dt.now().strftime("%H:%M:%S")), 0)
                except Exception as mail_err:
                    print("Could not send alert mail:", mail_err)
                print("Sleeping before retrying...")
                time.sleep(30)
            finally:
                time.sleep(LOOP_SLEEP_SECONDS)
            
if __name__ == "__main__":
    mainNEW()
