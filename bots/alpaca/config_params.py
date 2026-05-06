#### config_params.py

import json
import re

config = json.loads(open('AUTH/ConfigFile.txt', 'r').read()) # Config File with All Parameters


PRICE_SOURCES = ('Open', 'High', 'Low', 'Close')
MARKET_DATA_FEEDS = ('iex', 'sip', 'delayed_sip')


def _require_number(name, value, minimum=None, maximum=None):
    if not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a number')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name} must be >= {minimum}')
    if maximum is not None and value > maximum:
        raise ValueError(f'{name} must be <= {maximum}')


def _require_int(name, value, minimum=None, maximum=None):
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f'{name} must be an integer')
    _require_number(name, value, minimum, maximum)


def _require_bool(name, value):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')


def _optional_bool(config_section, key, default):
    value = config_section.get(key, default)
    _require_bool(key, value)
    return value


def _optional_int(config_section, key, default, minimum=None, maximum=None):
    value = config_section.get(key, default)
    _require_int(key, value, minimum, maximum)
    return value


def _optional_number(config_section, key, default, minimum=None, maximum=None):
    value = config_section.get(key, default)
    if value is None:
        return value
    _require_number(key, value, minimum, maximum)
    return value


def _require_keys(name, value, required_keys):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object')
    missing = [key for key in required_keys if key not in value]
    if missing:
        raise ValueError(f'Missing {name} keys: {", ".join(missing)}')


def _require_source(name, value):
    if value not in PRICE_SOURCES:
        raise ValueError(f'{name} must be one of: {", ".join(PRICE_SOURCES)}')


def _parse_start_date_days(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
        match = re.fullmatch(r'(\d+)\s+days?\s+ago', stripped, re.IGNORECASE)
        if match:
            return int(match.group(1))
    raise ValueError('start_date must be an integer day count or a string like "10 days ago"')


def _validate_config(config):
    required_keys = [
        'max_investment_amount', 'max_trades_active', 'trade_capital_percent',
        'stop_loss', 'trailing_stop', 'limit_price',
        'activate_trailing_stop_loss_at', 'sleep_time_between_trades',
        'start_date', 'end_date', 'timeframe', 'candle_lookback_period', 'indicators'
    ]
    missing = [key for key in required_keys if key not in config]
    if missing:
        raise ValueError(f'Missing config keys: {", ".join(missing)}')

    _require_number('max_investment_amount', config['max_investment_amount'], minimum=0)
    _require_int('max_trades_active', config['max_trades_active'], minimum=1)
    _require_number('trade_capital_percent', config['trade_capital_percent'], minimum=0, maximum=100)
    _require_number('stop_loss', config['stop_loss'], minimum=0)
    _require_number('trailing_stop', config['trailing_stop'], minimum=0)
    _require_number('limit_price', config['limit_price'], minimum=0)
    _require_number('activate_trailing_stop_loss_at', config['activate_trailing_stop_loss_at'], minimum=0)
    _require_int('sleep_time_between_trades', config['sleep_time_between_trades'], minimum=1)
    _require_int('candle_lookback_period', config['candle_lookback_period'], minimum=1)
    _parse_start_date_days(config['start_date'])
    if not isinstance(config['end_date'], str):
        raise ValueError('end_date must be a string')

    if config['timeframe'] not in ('1Minute', '1Hour', '1Day'):
        raise ValueError('timeframe must be one of: 1Minute, 1Hour, 1Day')

    market_data_feed = str(config.get('market_data_feed', 'iex')).lower()
    if market_data_feed not in MARKET_DATA_FEEDS:
        raise ValueError(f'market_data_feed must be one of: {", ".join(MARKET_DATA_FEEDS)}')

    dynamic_tickers = config.get('dynamic_tickers', {})
    if not isinstance(dynamic_tickers, dict):
        raise ValueError('dynamic_tickers must be an object')
    _optional_bool(dynamic_tickers, 'enabled', True)
    _optional_bool(dynamic_tickers, 'include_gainers', True)
    _optional_bool(dynamic_tickers, 'include_losers', True)
    _optional_int(dynamic_tickers, 'top_per_side', 50, minimum=1, maximum=100)
    _optional_int(dynamic_tickers, 'bar_request_chunk_size', 100, minimum=1, maximum=200)
    min_price = _optional_number(dynamic_tickers, 'min_price', None, minimum=0)
    max_price = _optional_number(dynamic_tickers, 'max_price', None, minimum=0)
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValueError('dynamic_tickers.min_price must be <= dynamic_tickers.max_price')
    if not dynamic_tickers.get('include_gainers', True) and not dynamic_tickers.get('include_losers', True):
        raise ValueError('dynamic_tickers must include gainers, losers, or both')

    indicators = config['indicators']
    _require_keys('indicators', indicators, ['EMA', 'stochRSI', 'stoch', 'EMA_params', 'stoch_params', 'stochRSI_params'])
    for name in ('EMA', 'stochRSI', 'stoch'):
        _require_bool(f'indicators.{name}', indicators.get(name))

    ema_params = indicators['EMA_params']
    _require_keys('indicators.EMA_params', ema_params, ['ema_period', 'source', 'smoothing'])
    _require_int('indicators.EMA_params.ema_period', ema_params['ema_period'], minimum=1)
    _require_source('indicators.EMA_params.source', ema_params['source'])
    _require_number('indicators.EMA_params.smoothing', ema_params['smoothing'], minimum=0)
    if ema_params['smoothing'] <= 0:
        raise ValueError('indicators.EMA_params.smoothing must be > 0')
    if ema_params['smoothing'] > ema_params['ema_period'] + 1:
        raise ValueError('indicators.EMA_params.smoothing must be <= ema_period + 1')

    stoch_params = indicators['stoch_params']
    _require_keys('indicators.stoch_params', stoch_params, ['lower_band', 'upper_band', 'K_Length', 'smooth_K', 'smooth_D', 'source'])
    _require_number('indicators.stoch_params.lower_band', stoch_params['lower_band'], minimum=0, maximum=100)
    _require_number('indicators.stoch_params.upper_band', stoch_params['upper_band'], minimum=0, maximum=100)
    if stoch_params['lower_band'] >= stoch_params['upper_band']:
        raise ValueError('indicators.stoch_params.lower_band must be below upper_band')
    _require_int('indicators.stoch_params.K_Length', stoch_params['K_Length'], minimum=1)
    _require_int('indicators.stoch_params.smooth_K', stoch_params['smooth_K'], minimum=1)
    _require_int('indicators.stoch_params.smooth_D', stoch_params['smooth_D'], minimum=1)
    _require_source('indicators.stoch_params.source', stoch_params['source'])

    stochRSI_params = indicators['stochRSI_params']
    _require_keys('indicators.stochRSI_params', stochRSI_params, ['lower_band', 'upper_band', 'K', 'D', 'rsi_length', 'stoch_length', 'source'])
    _require_number('indicators.stochRSI_params.lower_band', stochRSI_params['lower_band'], minimum=0, maximum=100)
    _require_number('indicators.stochRSI_params.upper_band', stochRSI_params['upper_band'], minimum=0, maximum=100)
    if stochRSI_params['lower_band'] >= stochRSI_params['upper_band']:
        raise ValueError('indicators.stochRSI_params.lower_band must be below upper_band')
    _require_int('indicators.stochRSI_params.K', stochRSI_params['K'], minimum=1)
    _require_int('indicators.stochRSI_params.D', stochRSI_params['D'], minimum=1)
    _require_int('indicators.stochRSI_params.rsi_length', stochRSI_params['rsi_length'], minimum=1)
    _require_int('indicators.stochRSI_params.stoch_length', stochRSI_params['stoch_length'], minimum=1)
    _require_source('indicators.stochRSI_params.source', stochRSI_params['source'])


_validate_config(config)

# setting up parameters
# Order Params
global max_trades
global trade_capital_percent
global stop_loss
global trailing_stop
max_investment_amount = config["max_investment_amount"]
max_trades = config["max_trades_active"]
trade_capital_percent = config["trade_capital_percent"]
stop_loss = config["stop_loss"]
trailing_stop = config["trailing_stop"]
limit_price = config["limit_price"]
lookback_period = config["candle_lookback_period"]
activate_trailing_stop_loss_at = config["activate_trailing_stop_loss_at"]
sleep_time = config["sleep_time_between_trades"]

# Data Collection Params
global start_date
global end_date
global timeframe
start_date = config["start_date"]
start_date = _parse_start_date_days(start_date)

end_date = config["end_date"]
timeframe = config["timeframe"]
market_data_feed = str(config.get('market_data_feed', 'iex')).lower()

dynamic_tickers_config = config.get('dynamic_tickers', {})
dynamic_tickers_enabled = dynamic_tickers_config.get('enabled', True)
dynamic_tickers_include_gainers = dynamic_tickers_config.get('include_gainers', True)
dynamic_tickers_include_losers = dynamic_tickers_config.get('include_losers', True)
dynamic_tickers_top_per_side = dynamic_tickers_config.get('top_per_side', 50)
dynamic_tickers_min_price = dynamic_tickers_config.get('min_price')
dynamic_tickers_max_price = dynamic_tickers_config.get('max_price')
bar_request_chunk_size = dynamic_tickers_config.get('bar_request_chunk_size', 100)

# Technical Indicator (TI) Params
ema = config['indicators']['EMA']
stoch_rsi = config['indicators']['stochRSI']
stoch = config['indicators']['stoch']
ema_params = config['indicators']['EMA_params'] # EMA_Params: Period, Source (Close)
stoch_params = config['indicators']['stoch_params'] # Stoch_Params: K_Length, Lower Band, smooth_D, smooth_K
stochRSI_params = config['indicators']['stochRSI_params'] # StochRSI_Params: K, D, Lower Band, RSI Length, Source (Close)

ema_period = ema_params['ema_period']
ema_source = ema_params['source']
ema_smoothing = ema_params['smoothing']
# ema_fast = ema_params['fast_period']
# ema_slow = ema_params['slow_period']

stoch_upper_band = stoch_params['upper_band']
stoch_lower_band= stoch_params['lower_band']
stoch_klength = stoch_params['K_Length']
stoch_smoothk = stoch_params['smooth_K']
stoch_smoothd = stoch_params['smooth_D']
stoch_source = stoch_params['source']

stochRSI_length = stochRSI_params['stoch_length']
stochRSI_rsi_length = stochRSI_params['rsi_length']
stochRSI_upper_band = stochRSI_params['upper_band']
stochRSI_lower_band = stochRSI_params['lower_band']
stochRSI_k = stochRSI_params['K']
stochRSI_d = stochRSI_params['D']
stochRSI_source = stochRSI_params['source']
