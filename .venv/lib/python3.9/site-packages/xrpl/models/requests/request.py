"""
The base class for all network request types.
Represents fields common to all request types.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Type, Union, cast

from typing_extensions import Final, Self

import xrpl.models.requests  # bare import to get around circular dependency
from xrpl.models.base_model import BaseModel
from xrpl.models.exceptions import XRPLModelException
from xrpl.models.required import REQUIRED
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init

_DEFAULT_API_VERSION: Final[int] = 2


class RequestMethod(str, Enum):
    """Represents the different options for the ``method`` field in a request."""

    # account methods
    ACCOUNT_CHANNELS = "account_channels"
    ACCOUNT_CURRENCIES = "account_currencies"
    ACCOUNT_INFO = "account_info"
    ACCOUNT_LINES = "account_lines"
    ACCOUNT_NFTS = "account_nfts"
    ACCOUNT_OBJECTS = "account_objects"
    ACCOUNT_OFFERS = "account_offers"
    ACCOUNT_TX = "account_tx"
    GATEWAY_BALANCES = "gateway_balances"
    NO_RIPPLE_CHECK = "noripple_check"

    # transaction methods
    SIGN = "sign"
    SIGN_FOR = "sign_for"
    SUBMIT = "submit"
    SUBMIT_MULTISIGNED = "submit_multisigned"
    TRANSACTION_ENTRY = "transaction_entry"
    TX = "tx"

    # channel methods
    CHANNEL_AUTHORIZE = "channel_authorize"
    CHANNEL_VERIFY = "channel_verify"

    # path methods
    BOOK_OFFERS = "book_offers"
    DEPOSIT_AUTHORIZED = "deposit_authorized"
    PATH_FIND = "path_find"
    RIPPLE_PATH_FIND = "ripple_path_find"

    # ledger methods
    LEDGER = "ledger"
    LEDGER_CLOSED = "ledger_closed"
    LEDGER_CURRENT = "ledger_current"
    LEDGER_DATA = "ledger_data"
    LEDGER_ENTRY = "ledger_entry"

    # NFT methods
    NFT_BUY_OFFERS = "nft_buy_offers"
    NFT_SELL_OFFERS = "nft_sell_offers"
    NFT_INFO = "nft_info"  # clio only
    NFT_HISTORY = "nft_history"  # clio only
    NFTS_BY_ISSUER = "nfts_by_issuer"  # clio only

    # subscription methods
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"

    # server info methods
    FEATURE = "feature"
    FEE = "fee"
    MANIFEST = "manifest"
    SERVER_DEFINITIONS = "server_definitions"
    SERVER_INFO = "server_info"
    SERVER_STATE = "server_state"

    # utility methods
    PING = "ping"
    RANDOM = "random"

    # amm methods
    AMM_INFO = "amm_info"

    # price oracle methods
    GET_AGGREGATE_PRICE = "get_aggregate_price"

    # generic unknown/unsupported request
    # (there is no XRPL analog, this model is specific to xrpl-py)
    GENERIC_REQUEST = "zzgeneric_request"


@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class Request(BaseModel):
    """
    The base class for all network request types.
    Represents fields common to all request types.
    """

    method: RequestMethod = REQUIRED  # type: ignore
    """
    This field is required.

    :meta hide-value:
    """

    id: Optional[Union[str, int]] = None

    api_version: int = _DEFAULT_API_VERSION
    """
    The API version to use for the said Request. By default, api_version: 2 is used.
    Docs:
    https://xrpl.org/docs/references/http-websocket-apis/api-conventions/request-formatting/#api-versioning
    """

    @classmethod
    def from_dict(cls: Type[Self], value: Dict[str, Any]) -> Self:
        """
        Construct a new Request from a dictionary of parameters.

        Args:
            value: The value to construct the Request from.

        Returns:
            A new Request object, constructed using the given parameters.

        Raises:
            XRPLModelException: If the dictionary provided is invalid.
        """
        if cls.__name__ == "Request":
            if "method" not in value:
                raise XRPLModelException("Request does not include method.")
            correct_type = cls.get_method(value["method"])
            return correct_type.from_dict(value)  # type: ignore

        if "method" in value:
            method = value["method"]
            if (
                cls.get_method(method).__name__ != cls.__name__
                and not (
                    method == "submit"
                    and cls.__name__ in ("SignAndSubmit", "SubmitOnly")
                )
                and not cls.__name__ == "GenericRequest"
            ):
                raise XRPLModelException(
                    f"Using wrong constructor: using {cls.__name__} constructor "
                    f"with Request method {method}."
                )
            value = {**value}
            del value["method"]

        return super(Request, cls).from_dict(value)

    @classmethod
    def get_method(cls: Type[Self], method: str) -> Type[Request]:
        """
        Returns the correct request method based on the string name.

        Args:
            method: The String name of the Request object.

        Returns:
            The request class with the given name. If the request doesn't exist, then
            it will return a `GenericRequest`.
        """
        # special case for NoRippleCheck and NFT methods
        if method == RequestMethod.NO_RIPPLE_CHECK:
            return xrpl.models.requests.NoRippleCheck
        if method == RequestMethod.ACCOUNT_NFTS:
            return xrpl.models.requests.AccountNFTs
        if method == RequestMethod.NFT_BUY_OFFERS:
            return xrpl.models.requests.NFTBuyOffers
        if method == RequestMethod.NFT_SELL_OFFERS:
            return xrpl.models.requests.NFTSellOffers
        if method == RequestMethod.NFT_INFO:
            return xrpl.models.requests.NFTInfo
        if method == RequestMethod.NFT_HISTORY:
            return xrpl.models.requests.NFTHistory
        if method == RequestMethod.NFTS_BY_ISSUER:
            return xrpl.models.requests.NFTsByIssuer
        parsed_name = "".join([word.capitalize() for word in method.split("_")])
        if parsed_name in xrpl.models.requests.__all__:
            return cast(Type[Request], getattr(xrpl.models.requests, parsed_name))
        return xrpl.models.requests.GenericRequest

    def to_dict(self: Self) -> Dict[str, Any]:
        """
        Returns the dictionary representation of a Request.

        Returns:
            The dictionary representation of a Request.
        """
        # we need to override this because method is using ``field``
        # which will not include the value in the object's __dict__
        return {**super().to_dict(), "method": self.method.value}


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class LookupByLedgerRequest:
    """Represents requests that need specifying an instance of the ledger"""

    ledger_hash: Optional[str] = None
    """
    A 20-byte hex string for the ledger version to use.
    """
    ledger_index: Optional[Union[str, int]] = None
    """
    The ledger index of the ledger to use, or a shortcut string.
    """
