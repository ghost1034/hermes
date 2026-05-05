import numpy as np
import pandas as pd

from indicator import implement_ema_strategy, rsi, stochastic


def make_ohlc(close_values):
    close = pd.Series(close_values, dtype=float)
    return pd.DataFrame({
        'Timestamp': pd.date_range('2026-01-01', periods=len(close), freq='min'),
        'Open': close,
        'High': close + 1,
        'Low': close - 1,
        'Close': close,
    })


def test_ema_strategy_marks_cross_above_signal():
    df = make_ohlc([10, 10, 10, 12, 14])
    result = implement_ema_strategy(df, period=3, source='Close', smoothing=2)
    assert list(result['EMA Above']) == [0.0, 0.0, 0.0, 1.0, 1.0]
    assert list(result['EMA Signal']) == [0.0, 0.0, 0.0, 1.0, 0.0]


def test_rsi_adds_rsi_column_with_expected_bounds():
    df = make_ohlc(np.linspace(10, 30, 30))
    result = rsi(df, period=14, source='Close')
    assert 'RSI' in result.columns
    assert result['RSI'].dropna().between(0, 100).all()


def test_stochastic_handles_flat_prices_without_signal():
    df = make_ohlc([10] * 30)
    result = stochastic(df, period=14, smoothK=3, smoothD=3, TYPE='Stoch')
    assert 'Stoch Signal' in result.columns
    assert result['Stoch Signal'].sum() == 0


def test_stoch_rsi_handles_insufficient_history_without_signal():
    df = rsi(make_ohlc([10, 11, 12, 13, 14]), period=14, source='Close')
    result = stochastic(df, TYPE='StochRSI', period_stochRSI=14)
    assert 'StochRSI Signal' in result.columns
    assert result['StochRSI Signal'].sum() == 0
