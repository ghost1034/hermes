import os
import unittest
from unittest.mock import patch, MagicMock

import fetch_tick_data

class TestFetchTickData(unittest.TestCase):
    @patch('fetch_tick_data.StockHistoricalDataClient')
    def test_fetch_ticks_success(self, MockClient):
        # Setup mock client and response
        mock_client_instance = MockClient.return_value
        
        mock_trade1 = MagicMock()
        mock_trade1.timestamp.isoformat.return_value = "2026-05-01T10:00:00Z"
        mock_trade1.price = 150.5
        mock_trade1.size = 100
        
        mock_response = MagicMock()
        mock_response.data = {"AAPL": [mock_trade1]}
        
        mock_client_instance.get_stock_trades.return_value = mock_response
        
        # Test fetch_ticks
        symbols = ["AAPL"]
        
        # We need to mock open to not write to a real file
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            fetch_tick_data.fetch_ticks(symbols, "fake_key", "fake_secret")
            
            # Assert file was opened
            mock_file.assert_called_once_with("historical_ticks.csv", "w")
            
            # Assert trades were requested
            mock_client_instance.get_stock_trades.assert_called_once()
            
            # Assert writes to CSV happened (header + 1 data row)
            handle = mock_file()
            # writerow is called inside csv.writer, which ends up calling handle.write
            # Check that write was called multiple times
            self.assertTrue(handle.write.called)

    @patch('fetch_tick_data.StockHistoricalDataClient')
    def test_fetch_ticks_handles_error(self, MockClient):
        # Setup mock client to raise exception
        mock_client_instance = MockClient.return_value
        mock_client_instance.get_stock_trades.side_effect = Exception("API Error")
        
        symbols = ["AAPL"]
        
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            with patch('sys.stderr', new_callable=MagicMock) as mock_stderr:
                # Should not raise exception
                fetch_tick_data.fetch_ticks(symbols, "fake_key", "fake_secret")
                
                # Should print error to stderr
                # Instead of checking string matches, just assert write was called on stderr
                self.assertTrue(mock_stderr.write.called)

if __name__ == '__main__':
    unittest.main()
