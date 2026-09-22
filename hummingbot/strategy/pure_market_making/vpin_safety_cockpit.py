import logging
from followsm import FollowSMClient

logger = logging.getLogger(__name__)

class VPINSafetyCockpit:
    """
    Auxiliary risk manager for Hummingbot Pure Market Making strategy.
    Widens bid-ask spread when orderbook depth imbalance or VPIN spikes.
    """
    def __init__(self):
        self.client = FollowSMClient()

    def get_spread_multiplier(self, symbol: str) -> float:
        try:
            snapshot = self.client.get_toxicity_snapshot(symbol)
            vpin = getattr(snapshot, 'vpin', 0.0)
            ob_toxicity = getattr(snapshot, 'ob_toxicity_1pct', 1.0)
            
            if vpin > 0.70 or ob_toxicity > 2.0:
                # Widen spreads 3x to prevent adverse selection
                return 3.0
        except Exception as e:
            logger.warning(f"FollowSM telemetry fetch failed for {symbol}: {e}")
        return 1.0