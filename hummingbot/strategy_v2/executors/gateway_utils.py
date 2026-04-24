"""
Shared utilities for Gateway executors.

Provides connector validation and normalization for LPExecutor.

Architecture:
- connector_name: Network identifier (e.g., "solana-mainnet-beta")
- provider: Combined format "dex/trading_type" (e.g., "jupiter/router", "meteora/clmm")
- dex_name: DEX protocol name parsed from provider (e.g., "orca", "jupiter")
- trading_type: Pool/route type parsed from provider (e.g., "clmm", "amm", "router")

Provider Format:
- Executors use provider strings: "jupiter/router", "meteora/clmm"
- Gateway HTTP client uses separate dex_name and trading_type
- Use parse_provider() to convert between formats
"""
import logging
from typing import Callable, List, Optional, Tuple

from hummingbot.client.settings import GATEWAY_DEXS

logger = logging.getLogger(__name__)


def parse_provider(provider: str, default_trading_type: str = "router") -> Tuple[str, str]:
    """
    Parse provider string into (dex_name, trading_type) tuple.

    Provider strings are used by executors in format "dex/trading_type".
    Gateway HTTP client requires separate dex_name and trading_type parameters.

    Args:
        provider: Provider string in format "dex/type" or just "dex"
            Examples: "jupiter/router", "meteora/clmm", "orca"
        default_trading_type: Default type if not specified in provider
            Use "router" for swap operations, "clmm" for LP operations

    Returns:
        Tuple of (dex_name, trading_type)

    Examples:
        >>> parse_provider("jupiter/router")
        ("jupiter", "router")
        >>> parse_provider("meteora/clmm")
        ("meteora", "clmm")
        >>> parse_provider("orca")
        ("orca", "router")
        >>> parse_provider("orca", default_trading_type="clmm")
        ("orca", "clmm")
    """
    if "/" in provider:
        parts = provider.split("/", 1)
        return parts[0], parts[1]
    return provider, default_trading_type


def validate_network_connector(
    connector_name: str,
    on_error: Callable[[str], None],
) -> bool:
    """
    Validate that a network-style connector exists.

    Network connectors are in format "chain-network" (e.g., "solana-mainnet-beta").
    These are registered in GATEWAY_DEXS from the chains endpoint.

    Args:
        connector_name: Network connector name (e.g., "solana-mainnet-beta")
        on_error: Callback function to log error messages

    Returns:
        True if valid, False otherwise
    """
    # If GATEWAY_DEXS is empty, skip validation
    # (API context without monitor loop - Gateway will validate at execution time)
    if not GATEWAY_DEXS:
        logger.debug(
            f"GATEWAY_DEXS empty, skipping validation for {connector_name}. "
            "Gateway will validate at execution time."
        )
        return True

    # Check if connector exists in GATEWAY_DEXS
    if connector_name in GATEWAY_DEXS:
        return True

    # Get network-style connectors for better error message
    network_connectors = [c for c in GATEWAY_DEXS if '-' in c and '/' not in c]

    on_error(
        f"Network connector '{connector_name}' not found in Gateway. "
        f"Available network connectors: {network_connectors}"
    )
    return False


def validate_and_normalize_connector(
    connector_name: str,
    required_type: str,
    on_error: Callable[[str], None],
) -> Tuple[Optional[str], bool]:
    """
    Validate and normalize connector name for Gateway executors.

    Supports two connector formats:
    1. Network format: "chain-network" (e.g., "solana-mainnet-beta")
       - Used with separate dex and trading_type parameters
       - Returns as-is if valid
    2. DEX format: "dex/type" (e.g., "orca/clmm", "jupiter/router")
       - Legacy format with type embedded in name
       - If base name only, auto-appends required_type

    Args:
        connector_name: Connector name from config
        required_type: The connector type suffix required (e.g., "router", "clmm")
        on_error: Callback function to log error messages

    Returns:
        Tuple of (normalized_connector_name, success)
        - If validation succeeds: (normalized_name, True)
        - If validation fails: (None, False)
    """
    type_suffix = f"/{required_type}"

    # Check if it's a network-style connector (chain-network format)
    # Network connectors don't have '/' and typically have '-' (e.g., "solana-mainnet-beta")
    if '/' not in connector_name and '-' in connector_name:
        # Network connector format - validate it exists
        if validate_network_connector(connector_name, on_error):
            return connector_name, True
        return None, False

    # DEX format: handle /type suffix
    if "/" in connector_name:
        base, connector_type = connector_name.split("/", 1)

        if connector_type != required_type:
            on_error(
                f"Executor requires /{required_type} connector type. "
                f"'{connector_type}' is not supported."
            )
            return None, False

        # If GATEWAY_DEXS is empty, skip validation (API context without monitor loop)
        # Gateway will validate at execution time
        if not GATEWAY_DEXS:
            logger.debug(
                f"GATEWAY_DEXS empty, skipping validation for {connector_name}. "
                "Gateway will validate at execution time."
            )
            return connector_name, True

        if connector_name not in GATEWAY_DEXS:
            matching_connectors = [c for c in GATEWAY_DEXS if type_suffix in c]
            on_error(
                f"Connector '{connector_name}' not found in Gateway. "
                f"Available {required_type} connectors: {matching_connectors}"
            )
            return None, False

        return connector_name, True

    # Base name only - auto-append the required type
    normalized_name = f"{connector_name}/{required_type}"

    # If GATEWAY_DEXS is empty, skip validation (API context without monitor loop)
    # Just normalize the name and let Gateway validate at execution time
    if not GATEWAY_DEXS:
        logger.debug(
            f"GATEWAY_DEXS empty, normalizing {connector_name} -> {normalized_name}. "
            "Gateway will validate at execution time."
        )
        return normalized_name, True

    if normalized_name in GATEWAY_DEXS:
        return normalized_name, True

    # Check if connector exists at all with any type
    matching = [c for c in GATEWAY_DEXS if c.startswith(f"{connector_name}/")]
    if matching:
        on_error(
            f"Connector '{connector_name}' doesn't support /{required_type}. "
            f"Available types for {connector_name}: {matching}"
        )
    else:
        matching_connectors = [c for c in GATEWAY_DEXS if type_suffix in c]
        on_error(
            f"Connector '{connector_name}' not found in Gateway. "
            f"Available {required_type} connectors: {matching_connectors}"
        )

    return None, False


def get_connectors_by_type(connector_type: str) -> List[str]:
    """
    Get all Gateway connectors of a specific type.

    Args:
        connector_type: The connector type (e.g., "router", "clmm", "amm")

    Returns:
        List of connector names matching the type
    """
    type_suffix = f"/{connector_type}"
    return [c for c in GATEWAY_DEXS if type_suffix in c]


def get_network_connectors() -> List[str]:
    """
    Get all network-style connectors (chain-network format).

    Returns:
        List of network connector names (e.g., ["solana-mainnet-beta", "ethereum-mainnet"])
    """
    return [c for c in GATEWAY_DEXS if '-' in c and '/' not in c]
