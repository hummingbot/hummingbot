from typing import Tuple

from hummingbot.core.data_type.common import OutcomeType


def format_event_trading_pair(market_id: str, outcome: OutcomeType, quote: str) -> str:
    """
    Builds an internal event trading pair identifier using the canonical convention:
    "{MARKETID}-{OUTCOME}-{QUOTE}" e.g., "ELECTION2024-YES-USDC".
    """
    return f"{market_id}-{outcome.name}-{quote}"


def parse_event_trading_pair(trading_pair: str) -> Tuple[str, OutcomeType, str]:
    """
    Parses an internal event trading pair identifier into components.
    Expected format: "{MARKETID}-{OUTCOME}-{QUOTE}".
    Returns a tuple: (market_id, outcome: OutcomeType, quote).
    """
    try:
        parts = trading_pair.split("-")
        if len(parts) < 3:
            raise ValueError(f"Invalid format: {trading_pair}")

        # Quote is last part, outcome is second to last, market_id is everything before
        quote = parts[-1]
        outcome_str = parts[-2]
        market_id = "-".join(parts[:-2])

        outcome = OutcomeType[outcome_str]
        return market_id, outcome, quote
    except Exception as e:
        raise ValueError(f"Invalid event trading pair format: {trading_pair}") from e
