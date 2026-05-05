import pytest

import main

from test_integration_readonly import paper_auth_or_skip


@pytest.mark.integration
def test_paper_limit_order_can_be_submitted_and_canceled():
    auth = paper_auth_or_skip('ALPACA_ENABLE_ORDER_TESTS')
    api = main.create_alpaca_api(auth)

    order = api.submit_order(
        symbol='AAPL',
        qty='1',
        side='buy',
        type='limit',
        time_in_force='day',
        limit_price=1,
    )
    try:
        api.cancel_order(order.id)
        canceled = api.get_order(order.id)
        assert str(canceled.status).lower() in ('canceled', 'pending_cancel', 'accepted', 'new')
    finally:
        try:
            api.cancel_order(order.id)
        except Exception:
            pass
