import unittest
from datetime import datetime, timedelta
from src.models import TradeSetup, TradeStatus, EntryRule, StopLossRule, TargetRule
from src.trade_manager import TradeManager

class TestTradeManager(unittest.TestCase):
    def setUp(self):
        self.manager = TradeManager()
        self.long_setup = TradeSetup(
            id="long_1",
            symbol="@ES",
            direction="LONG",
            status=TradeStatus.NEW,
            entry=EntryRule(price=5000.0, condition="test"),
            stop_loss=StopLossRule(price=4990.0),
            targets=[TargetRule(price=5010.0), TargetRule(price=5020.0)],
            rules_text="test rules"
        )
        self.short_setup = TradeSetup(
            id="short_1",
            symbol="@ES",
            direction="SHORT",
            status=TradeStatus.NEW,
            entry=EntryRule(price=5000.0, condition="test"),
            stop_loss=StopLossRule(price=5010.0),
            targets=[TargetRule(price=4990.0)],
            rules_text="test rules"
        )

    def test_add_setup(self):
        self.manager.add_setups([self.long_setup])
        setups = self.manager.get_active_setups()
        self.assertEqual(len(setups), 1)
        self.assertEqual(setups[0].id, "long_1")

    def test_prune_backlog(self):
        old_setup = self.long_setup.model_copy()
        old_setup.id = "old_1"
        old_setup.created_at = datetime.now() - timedelta(minutes=31)
        
        self.manager.add_setups([old_setup])
        self.manager.prune_backlog(max_age_minutes=30)
        self.assertEqual(len(self.manager.get_active_setups()), 0)

    def test_monitoring_transition_long(self):
        self.manager.add_setups([self.long_setup])
        
        # 1. NEW -> MONITORING (Price above entry)
        self.manager.update_setups(5010.0) 
        self.assertEqual(self.manager.setups["long_1"].status, TradeStatus.MONITORING)
        
        # 2. MONITORING -> CLOSE_TO_ENTRY (within 3 points of 5000)
        self.manager.update_setups(5002.0)
        self.assertEqual(self.manager.setups["long_1"].status, TradeStatus.CLOSE_TO_ENTRY)
        
        # 3. CLOSE -> MONITORING (moved away)
        self.manager.update_setups(5010.0)
        self.assertEqual(self.manager.setups["long_1"].status, TradeStatus.MONITORING)
        
        # 4. MONITORING -> TRADING (Hit entry 5000)
        self.manager.update_setups(5000.0)
        self.assertEqual(self.manager.setups["long_1"].status, TradeStatus.TRADING)
        
        # 5. TRADING -> PROFIT (Hit Target 5010)
        self.manager.update_setups(5010.0)
        self.assertEqual(self.manager.setups["long_1"].status, TradeStatus.PROFIT)

    def test_monitoring_transition_short(self):
        self.manager.add_setups([self.short_setup])
        
        # 1. NEW -> MONITORING
        self.manager.update_setups(4980.0)
        self.assertEqual(self.manager.setups["short_1"].status, TradeStatus.MONITORING)
        
        # 2. Hit Entry (>= 5000)
        self.manager.update_setups(5000.0)
        self.assertEqual(self.manager.setups["short_1"].status, TradeStatus.TRADING)
        
        # 3. Hit SL (>= 5010)
        self.manager.update_setups(5010.5)
        self.assertEqual(self.manager.setups["short_1"].status, TradeStatus.STOP_LOSS)

if __name__ == '__main__':
    unittest.main()
