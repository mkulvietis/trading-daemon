from datetime import datetime, time
import pytz

NY_TZ = pytz.timezone('America/New_York')
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

def is_market_open() -> bool:
    """
    Checks if the current NY time is within market hours (9:30 - 16:00 ET, Mon-Fri).
    """
    now_ny = datetime.now(NY_TZ)
    
    # Check if it's a weekday (Monday=0, Sunday=6)
    if now_ny.weekday() > 4:
        return False

    current_time = now_ny.time()
    
    return MARKET_OPEN <= current_time <= MARKET_CLOSE

def get_seconds_until_execution(interval_seconds: int) -> int:
    """
    Calculates seconds to wait. 
    If market is open, returns interval.
    If market is closed, could handle logic to wait for open (simplified to just interval for now to keep loop alive).
    """
    if is_market_open():
        return interval_seconds
    
    # If market is closed, we still might want to poll or just wait.
    # For now, we return interval to keep the daemon responsive to start/stop commands.
    return interval_seconds
