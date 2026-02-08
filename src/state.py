import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import pytz
from .trade_manager import TradeManager

NY_TZ = pytz.timezone('America/New_York')


class InferenceStatus(Enum):
    """Status of the inference process."""
    NONE = "none"           # No inference has been requested
    RUNNING = "running"     # Inference is in progress
    COMPLETE = "complete"   # Inference completed successfully
    ERROR = "error"         # Inference failed with an error


@dataclass
class InferenceState:
    """Holds the current inference state."""
    status: InferenceStatus = InferenceStatus.NONE
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Optional[str] = None


@dataclass
class DaemonState:
    is_running: bool = False
    last_output: str = "Daemon initializing..."
    current_interval: int = 120
    last_updated: Optional[datetime] = None
    last_price: Optional[float] = None
    
    # Auto-inference interval (600 = 10 minutes default, 0 = disabled)
    auto_inference_interval: int = 600
    
    # Current inference state
    inference: InferenceState = field(default_factory=InferenceState)
    
    # Trade Management
    trade_manager: TradeManager = field(default_factory=TradeManager)
    
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update_output(self, output: str):
        with self._lock:
            self.last_output = output
            # Store time as aware datetime in NY timezone
            self.last_updated = datetime.now(NY_TZ)

    def set_running(self, running: bool):
        with self._lock:
            self.is_running = running

    def set_interval(self, interval: int):
        with self._lock:
            self.current_interval = interval

    def set_auto_inference_interval(self, interval: int):
        """Set automatic inference interval. 0 = disabled."""
        with self._lock:
            self.auto_inference_interval = max(0, interval)

    def get_auto_inference_interval(self) -> int:
        with self._lock:
            return self.auto_inference_interval

    def start_inference(self, context: str = None):
        """Mark inference as started."""
        with self._lock:
            self.inference = InferenceState(
                status=InferenceStatus.RUNNING,
                started_at=datetime.now(NY_TZ),
                context=context
            )

    def complete_inference(self, result: str):
        """Mark inference as complete with result."""
        with self._lock:
            self.inference.status = InferenceStatus.COMPLETE
            self.inference.result = result
            self.inference.error = None
            self.inference.completed_at = datetime.now(NY_TZ)

    def fail_inference(self, error: str):
        """Mark inference as failed with error."""
        with self._lock:
            self.inference.status = InferenceStatus.ERROR
            self.inference.result = None
            self.inference.error = error
            self.inference.completed_at = datetime.now(NY_TZ)

    def get_inference_snapshot(self) -> dict:
        """Get current inference state as dict."""
        with self._lock:
            return {
                "status": self.inference.status.value,
                "result": self.inference.result,
                "error": self.inference.error,
                "started_at": self.inference.started_at.strftime("%Y-%m-%d %H:%M:%S %Z") if self.inference.started_at else None,
                "completed_at": self.inference.completed_at.strftime("%Y-%m-%d %H:%M:%S %Z") if self.inference.completed_at else None,
                "context": self.inference.context
            }

    def is_inference_running(self) -> bool:
        with self._lock:
            return self.inference.status == InferenceStatus.RUNNING

    def get_snapshot(self):
        with self._lock:
            # Format nicely: YYYY-MM-DD HH:MM:SS ET
            formatted_time = None
            if self.last_updated:
                formatted_time = self.last_updated.strftime("%Y-%m-%d %H:%M:%S %Z")
            
            return {
                "is_running": self.is_running,
                "last_output": self.last_output,
                "current_interval": self.current_interval,
                "last_updated": formatted_time,
                "auto_inference_interval": self.auto_inference_interval,
                "active_setups": [s.model_dump() for s in self.trade_manager.get_active_setups()]
            }


# Global singleton
app_state = DaemonState()
