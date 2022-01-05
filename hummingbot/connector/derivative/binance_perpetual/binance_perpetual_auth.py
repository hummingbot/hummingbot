import hashlib
import hmac


class BinancePerpetualAuth():
    """
    Auth class required by Binance Perpetual API
    """

    def __init__(self, api_secret: str):
        self._api_secret: str = api_secret

    def extend_query_with_authentication_info(self, query: str):
        secret = bytes(self._api_secret.encode("utf-8"))
        signature = hmac.new(secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
        query += f"&signature={signature}"
