from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import pytz

NY_TZ = pytz.timezone('America/New_York')

class TradeStatus(str, Enum):
    MONITORING = "MONITORING"
    CLOSE_TO_ENTRY = "CLOSE_TO_ENTRY"
    TRADING = "TRADING"
    PROFIT = "PROFIT"
    STOP_LOSS = "STOP_LOSS"
    CANCELED = "CANCELED" # Timed out or invalidated
    NEW = "NEW"

class EntryRule(BaseModel):
    type: Literal["limit", "market", "stop"] = "limit"
    price: float
    condition: str = Field(..., description="Logic condition e.g. 'price <= 5850.00'")

class StopLossRule(BaseModel):
    price: float
    description: Optional[str] = None

class TargetRule(BaseModel):
    price: float
    description: Optional[str] = None

class TradeSetup(BaseModel):
    id: str
    symbol: str = "@ES"
    direction: Literal["LONG", "SHORT"]
    status: TradeStatus = TradeStatus.NEW
    created_at: datetime = Field(default_factory=lambda: datetime.now(NY_TZ))
    
    entry: EntryRule
    stop_loss: StopLossRule
    targets: List[TargetRule]
    
    rules_text: str = Field(..., description="Condensed human readable rules")
    reasoning: Optional[str] = None

class LLMResponse(BaseModel):
    inference_time: Optional[str] = Field(None, description="Market time when inference was run")
    inference_price: Optional[float] = Field(None, description="Price when inference was run")
    market_overview: Optional[str] = Field(None, description="Brief summary of current market conditions")
    setups: List[TradeSetup]
