#### config_params.py

import json

config = json.loads(open('AUTH/ConfigFile.txt', 'r').read()) # Config File with All Parameters


def _require_number(name, value, minimum=None, maximum=None):
    if not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a number')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name} must be >= {minimum}')
    if maximum is not None and value > maximum:
        raise ValueError(f'{name} must be <= {maximum}')


def _require_bool_string(name, value):
    if value not in ('True', 'False'):
        raise ValueError(f'{name} must be "True" or "False"')


def _validate_config(config):
    required_keys = [
        'investment_amount', 'max_trades_active', 'trade_capital_percent',
        'stop_loss', 'trailing_stop', 'limit_price',
        'activate_trailing_stop_loss_at', 'sleep_time_between_trades',
        'start_date', 'timeframe', 'indicators'
    ]
    missing = [key for key in required_keys if key not in config]
    if missing:
        raise ValueError(f'Missing config keys: {", ".join(missing)}')

    _require_number('investment_amount', config['investment_amount'], minimum=0)
    _require_number('max_trades_active', config['max_trades_active'], minimum=1)
    _require_number('trade_capital_percent', config['trade_capital_percent'], minimum=0, maximum=100)
    _require_number('stop_loss', config['stop_loss'], minimum=0)
    _require_number('trailing_stop', config['trailing_stop'], minimum=0)
    _require_number('limit_price', config['limit_price'], minimum=0)
    _require_number('activate_trailing_stop_loss_at', config['activate_trailing_stop_loss_at'], minimum=0)
    _require_number('sleep_time_between_trades', config['sleep_time_between_trades'], minimum=1)

    if config['timeframe'] not in ('1Minute', '1Hour', '1Day'):
        raise ValueError('timeframe must be one of: 1Minute, 1Hour, 1Day')

    indicators = config['indicators']
    for name in ('EMA', 'stochRSI', 'stoch'):
        _require_bool_string(f'indicators.{name}', indicators.get(name))


_validate_config(config)

# setting up parameters
# Order Params
global max_trades
global trade_capital_percent
global stop_loss
global trailing_stop
investment_amount = config["investment_amount"]
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
start_date = int(start_date.split()[0])
# start_date = int(start_date)

end_date = config["end_date"]
timeframe = config["timeframe"]

# Technical Indicator (TI) Params
ema = config['indicators']['EMA']
stoch_rsi = config['indicators']['stochRSI']
stoch = config['indicators']['stoch']
ema_params = config['indicators']['EMA_params'] # EMA_Params: Period, Source (Close)
stoch_params = config['indicators']['stoch_params'] # Stoch_Params: K_Length, Lower Band, smooth_D, smooth_K
stochRSI_params = config['indicators']['stochRSI_params'] # StochRSI_Params: K, D, Lower Band, RSI Length, Source (Close)

ema_period = ema_params['ema_period']
ema_smoothing = ema_params['smoothing']
# ema_fast = ema_params['fast_period']
# ema_slow = ema_params['slow_period']

stoch_upper_band = stoch_params['upper_band']
stoch_lower_band= stoch_params['lower_band']
stoch_klength = stoch_params['K_Length']
stoch_smoothk = stoch_params['smooth_K']
stoch_smoothd = stoch_params['smooth_D']

stochRSI_length = stochRSI_params['stoch_length']
stochRSI_rsi_length = stochRSI_params['rsi_length']
stochRSI_upper_band = stochRSI_params['upper_band']
stochRSI_lower_band = stochRSI_params['lower_band']
stochRSI_k = stochRSI_params['K']
stochRSI_d = stochRSI_params['D']
