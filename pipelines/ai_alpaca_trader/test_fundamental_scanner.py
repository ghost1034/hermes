import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from fundamental_scanner import fetch_ticker_data, get_portfolio, scan_fundamentals

def test_fetch_ticker_data_valid():
    with patch('fundamental_scanner.yf.Ticker') as mock_ticker:
        mock_info = {
            'currentPrice': 150.0,
            'trailingPE': 15.5,
            'forwardPE': 12.0,
            'pegRatio': 1.2,
            'priceToBook': 3.0
        }
        mock_ticker.return_value.info = mock_info
        
        result = fetch_ticker_data('AAPL', 10.0)
        assert result is not None
        assert result['Symbol'] == 'AAPL'
        assert result['Price'] == 150.0
        assert result['P/E'] == 15.5
        assert result['PEG'] == 1.2

def test_fetch_ticker_data_low_price():
    with patch('fundamental_scanner.yf.Ticker') as mock_ticker:
        mock_info = {'currentPrice': 5.0}
        mock_ticker.return_value.info = mock_info
        
        result = fetch_ticker_data('PENNY', 10.0)
        assert result is None

@patch('fundamental_scanner.tradeapi.REST')
def test_get_portfolio(mock_rest, capsys):
    mock_api = MagicMock()
    mock_rest.return_value = mock_api
    
    mock_account = MagicMock()
    mock_account.buying_power = "1000.00"
    mock_account.portfolio_value = "5000.00"
    mock_api.get_account.return_value = mock_account
    
    mock_api.list_positions.return_value = []
    mock_api.list_orders.return_value = []
    
    get_portfolio()
    
    captured = capsys.readouterr()
    assert "Buying Power: $1000.00" in captured.out
    assert "None" in captured.out

@patch('fundamental_scanner.requests.get')
@patch('fundamental_scanner.os.environ.get')
def test_scan_fundamentals_no_creds(mock_env_get, mock_get, capsys):
    mock_env_get.return_value = None
    df = scan_fundamentals()
    assert df.empty
    
    captured = capsys.readouterr()
    assert "Error: Alpaca API credentials not found" in captured.out
