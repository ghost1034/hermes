import copy

import pytest

import config_params


@pytest.fixture
def valid_config():
    return copy.deepcopy(config_params.config)


def test_parse_start_date_days_accepts_supported_formats():
    assert config_params._parse_start_date_days(10) == 10
    assert config_params._parse_start_date_days('10') == 10
    assert config_params._parse_start_date_days('10 days ago') == 10
    assert config_params._parse_start_date_days('1 day ago') == 1


def test_validate_config_rejects_bad_market_data_feed(valid_config):
    valid_config['market_data_feed'] = 'bad-feed'
    with pytest.raises(ValueError, match='market_data_feed'):
        config_params._validate_config(valid_config)


def test_validate_config_rejects_bad_dynamic_price_range(valid_config):
    valid_config['dynamic_tickers']['min_price'] = 50
    valid_config['dynamic_tickers']['max_price'] = 10
    with pytest.raises(ValueError, match='min_price'):
        config_params._validate_config(valid_config)


def test_validate_config_rejects_disabled_gainers_and_losers(valid_config):
    valid_config['dynamic_tickers']['include_gainers'] = False
    valid_config['dynamic_tickers']['include_losers'] = False
    with pytest.raises(ValueError, match='gainers, losers'):
        config_params._validate_config(valid_config)


def test_validate_config_rejects_invalid_indicator_source(valid_config):
    valid_config['indicators']['EMA_params']['source'] = 'Volume'
    with pytest.raises(ValueError, match='EMA_params.source'):
        config_params._validate_config(valid_config)
