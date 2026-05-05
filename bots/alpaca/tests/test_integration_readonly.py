import os
from datetime import datetime as dt
from datetime import timedelta

import pytest

import main


def paper_auth_or_skip(env_var):
    if os.getenv(env_var) != '1':
        pytest.skip(f'set {env_var}=1 to run this Alpaca integration test')

    auth = main.load_alpaca_auth()
    base_url = auth.get('BASE-URL', '')
    if 'paper-api.alpaca.markets' not in base_url:
        pytest.fail('integration tests refuse to run unless BASE-URL points to Alpaca paper API')
    return auth


@pytest.mark.integration
def test_alpaca_readonly_smoke_checks():
    auth = paper_auth_or_skip('ALPACA_RUN_READONLY_SMOKE')
    api = main.create_alpaca_api(auth)

    account = api.get_account()
    assert getattr(account, 'id', None) or getattr(account, 'account_number', None)

    assert isinstance(api.list_positions(), list)
    assert isinstance(api.list_orders(status='open', direction='desc'), list)
    assert api.list_assets(status='active', asset_class='us_equity')

    trade = api.get_latest_trade('AAPL', feed=main.market_data_feed)
    assert float(trade.p) > 0

    start = (dt.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    end = dt.now().strftime('%Y-%m-%d')
    bars = api.get_bars('AAPL', main.get_timeframe('1Day'), start, end, adjustment='raw', feed=main.market_data_feed).df
    assert not bars.empty

    movers = api.data_get('/screener/stocks/movers', data={'top': 1}, api_version='v1beta1')
    assert 'gainers' in movers or 'losers' in movers
