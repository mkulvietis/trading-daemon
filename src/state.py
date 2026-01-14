import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pytz

NY_TZ = pytz.timezone('America/New_York')

@dataclass
class DaemonState:
    is_running: bool = False
    last_output: str = "Daemon initializing..."
    current_interval: int = 120
    last_updated: Optional[datetime] = None
    _lock: threading.Lock = threading.Lock()

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
                "last_updated": formatted_time
            }

# Global singleton
app_state = DaemonState()
