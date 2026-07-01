from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LLMModelCandidate:
    provider: str
    name: str
    role: str
    quality_level: int
    speed_level: int
    cost_level: int
    privacy_level: str
    context_window: int
    input_token_price_per_1m: Decimal = Decimal("0")
    output_token_price_per_1m: Decimal = Decimal("0")
    average_latency_ms: int = 0
    timeout_seconds: int = 120
    model_tier: str = "standard"
