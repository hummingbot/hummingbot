"""
Backpack Perpetual Auth - Reuses the spot connector's authentication.

The authentication mechanism is identical for both spot and perpetual trading.
"""

from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth


class BackpackPerpetualAuth(BackpackAuth):
    """
    Auth class for Backpack Perpetual using ED25519 signatures.

    This class inherits from the spot connector's BackpackAuth since
    the authentication mechanism is identical for perpetual trading.
    """
    pass
