from types import SimpleNamespace

import pandas as pd
import pytest

import main


class FakeAPI:
    def __init__(self):
        self.account = SimpleNamespace(cash='10000', buying_power='10000')
        self.positions = []
        self.open_orders = []
        self.assets = []
        self.latest_prices = {}
        self.data_response = {'gainers': [], 'losers': [], 'last_updated': 'test'}
        self.bars_df = pd.DataFrame()
        self.submitted_orders = []
        self.canceled_order_ids = []
        self.orders_by_id = {}

    def get_account(self):
        return self.account

    def list_positions(self):
        return self.positions

    def list_orders(self, status='open', direction='desc'):
        return self.open_orders

    def list_assets(self, status='active', asset_class='us_equity'):
        return self.assets

    def data_get(self, path, data=None, api_version=None):
        return self.data_response

    def get_latest_trade(self, symbol, feed=None):
        return SimpleNamespace(p=self.latest_prices.get(symbol, 100.0))

    def get_bars(self, symbols, timeframe, start, end, adjustment='raw', feed=None):
        return SimpleNamespace(df=self.bars_df.copy())

    def submit_order(self, **kwargs):
        order_id = f'order-{len(self.submitted_orders) + 1}'
        order = SimpleNamespace(id=order_id, status='accepted', **kwargs)
        self.submitted_orders.append(order)

        side = kwargs.get('side')
        symbol = kwargs.get('symbol')
        qty = kwargs.get('qty', '1')
        fill_price = self.latest_prices.get(symbol, 100.0)
        self.orders_by_id[order_id] = SimpleNamespace(
            id=order_id,
            status='filled',
            side=side,
            symbol=symbol,
            filled_qty=str(qty),
            filled_avg_price=str(fill_price),
        )
        return order

    def get_order(self, order_id):
        return self.orders_by_id[order_id]

    def cancel_order(self, order_id):
        self.canceled_order_ids.append(order_id)
        if order_id in self.orders_by_id:
            self.orders_by_id[order_id].status = 'canceled'


@pytest.fixture
def fake_api():
    return FakeAPI()


@pytest.fixture
def temp_bot(monkeypatch, tmp_path, fake_api):
    orders_dir = tmp_path / 'ORDERS'
    monkeypatch.setattr(main, 'ORDERS_DIR', str(orders_dir))
    monkeypatch.setattr(main, 'ORDERS_FILE', str(orders_dir / 'Orders.csv'))
    monkeypatch.setattr(main, 'OPEN_ORDERS_FILE', str(orders_dir / 'Open Orders.csv'))
    monkeypatch.setattr(main, 'TIME_AND_COINS_FILE', str(orders_dir / 'Time and Coins.csv'))
    monkeypatch.setattr(main, 'api', fake_api)
    monkeypatch.setattr(main, 'mail_alert', lambda *args, **kwargs: None)
    monkeypatch.setattr(main, 'tickers', [])
    main.ensure_order_storage()
    return main
