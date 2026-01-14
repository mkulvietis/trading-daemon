import unittest
from datetime import datetime, time
from unittest.mock import MagicMock, patch
import pytz
from src.market import is_market_open, MARKET_OPEN, MARKET_CLOSE
from src.state import DaemonState

class TestMarketDaemon(unittest.TestCase):

    def test_market_hours_open(self):
        # Mock datetime to be a Monday at 10:00 AM NY time
        ny_tz = pytz.timezone('America/New_York')
        mock_now = datetime(2023, 10, 23, 10, 0, 0) # Oct 23 2023 is Monday
        
        with patch('src.market.datetime') as mock_date:
            mock_date.now.return_value = ny_tz.localize(mock_now)
            mock_date.side_effect = lambda *args, **kw: datetime(*args, **kw)
            self.assertTrue(is_market_open())

    def test_market_hours_closed_weekend(self):
        # Mock datetime to be a Saturday
        ny_tz = pytz.timezone('America/New_York')
        mock_now = datetime(2023, 10, 21, 10, 0, 0) # Oct 21 2023 is Saturday
        
        with patch('src.market.datetime') as mock_date:
            mock_date.now.return_value = ny_tz.localize(mock_now)
            self.assertFalse(is_market_open())

    def test_market_hours_closed_evening(self):
        # Mock datetime to be a Monday at 18:00 (6 PM)
        ny_tz = pytz.timezone('America/New_York')
        mock_now = datetime(2023, 10, 23, 18, 0, 0)
        
        with patch('src.market.datetime') as mock_date:
            mock_date.now.return_value = ny_tz.localize(mock_now)
            self.assertFalse(is_market_open())

    def test_state_updates(self):
        state = DaemonState()
        state.update_output("test output")
        self.assertEqual(state.last_output, "test output")
        self.assertIsNotNone(state.last_updated)

if __name__ == '__main__':
    unittest.main()
