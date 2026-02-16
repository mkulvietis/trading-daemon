import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from .models import TradeSetup, TradeStatus
import pytz

NY_TZ = pytz.timezone('America/New_York')

logger = logging.getLogger("TradeManager")

class TradeManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.setups: Dict[str, TradeSetup] = {}
        # Simple history to avoid re-adding same ID if we wanted, 
        # but for now we just rely on current backlog
    
    def add_setups(self, new_setups: List[TradeSetup]):
        """Adds new setups to the backlog."""
        with self._lock:
            for setup in new_setups:
                # If setup ID already exists, update it or skip? 
                # For now, let's assume unique IDs per inference or overwrite if same ID
                if setup.id in self.setups:
                    logger.info(f"Updating existing setup {setup.id}")
                    # Preserve status if it was already progressing, unless it was just NEW/MONITORING
                    existing = self.setups[setup.id]
                    if existing.status in [TradeStatus.TRADING, TradeStatus.PROFIT, TradeStatus.STOP_LOSS]:
                        continue # Don't overwrite active trades with new plan
                
                self.setups[setup.id] = setup
                logger.info(f"Added setup: {setup.id} ({setup.direction} @ {setup.entry.price})")

    def get_active_setups(self) -> List[TradeSetup]:
        """Returns list of all setups in backlog."""
        with self._lock:
            # Return sorted by creation time desc
            return sorted(self.setups.values(), key=lambda x: x.created_at, reverse=True)

    def prune_backlog(self, max_age_minutes: int = 30):
        """Removes all setups older than max_age_minutes regardless of status."""
        with self._lock:
            now = datetime.now(NY_TZ)
            ids_to_remove = []
            for start_id, setup in self.setups.items():
                age = now - setup.created_at
                
                if age > timedelta(minutes=max_age_minutes):
                    ids_to_remove.append(start_id)
            
            for i in ids_to_remove:
                del self.setups[i]
                logger.info(f"Pruned old setup ({i}): age > {max_age_minutes}m")

    def update_setups(self, current_price: float):
        """
        Monitors all setups against current price and updates status.
        """
        with self._lock:
            for setup in self.setups.values():
                self._check_setup(setup, current_price)

    def _check_setup(self, setup: TradeSetup, price: float):
        # 1. NEW -> MONITORING (Immediate transition usually)
        if setup.status == TradeStatus.NEW:
            setup.status = TradeStatus.MONITORING

        # 2. MONITORING -> CLOSE_TO_ENTRY
        # Define "Close" as within ~3 points (12 ticks) for ES
        CLOSE_THRESHOLD = 3.0 
        
        if setup.status == TradeStatus.MONITORING:
            dist = abs(price - setup.entry.price)
            if dist <= CLOSE_THRESHOLD:
                setup.status = TradeStatus.CLOSE_TO_ENTRY
        
        # 3. CLOSE_TO_ENTRY -> MONITORING (if moved away)
        elif setup.status == TradeStatus.CLOSE_TO_ENTRY:
            dist = abs(price - setup.entry.price)
            if dist > CLOSE_THRESHOLD:
                setup.status = TradeStatus.MONITORING

        # 4. MONITORING/CLOSE -> TRADING (Simulated Fill)
        # For LONG: Price drops to entry (limit buy)
        # For SHORT: Price rallies to entry (limit sell)
        # Simplification: If price crosses or touches entry level
        if setup.status in [TradeStatus.MONITORING, TradeStatus.CLOSE_TO_ENTRY]:
            if setup.direction == "LONG":
                # Assuming we want to buy close to entry. 
                # If price is at or below entry, we are filled.
                # But careful not to fill immediately if current price << entry (that means we missed it or it gaped)
                # For this simple monitor: if price is effectively at entry.
                if price <= setup.entry.price:
                     setup.status = TradeStatus.TRADING
            elif setup.direction == "SHORT":
                if price >= setup.entry.price:
                    setup.status = TradeStatus.TRADING

        # 5. TRADING -> PROFIT / STOP_LOSS
        if setup.status == TradeStatus.TRADING:
            # Check SL
            if setup.direction == "LONG":
                if price <= setup.stop_loss.price:
                    setup.status = TradeStatus.STOP_LOSS
                # Check Targets (any target hit = Profit for visualization)
                for t in setup.targets:
                    if price >= t.price:
                        setup.status = TradeStatus.PROFIT
            
            elif setup.direction == "SHORT":
                if price >= setup.stop_loss.price:
                    setup.status = TradeStatus.STOP_LOSS
                for t in setup.targets:
                    if price <= t.price:
                        setup.status = TradeStatus.PROFIT

