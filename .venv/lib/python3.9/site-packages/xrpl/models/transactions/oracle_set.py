"""Model for OracleSet transaction type."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from typing_extensions import Self

from xrpl.models.nested_model import NestedModel
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import require_kwargs_on_init

MAX_ORACLE_DATA_SERIES = 10
MAX_ORACLE_PROVIDER = 256
MAX_ORACLE_URI = 256
MAX_ORACLE_SYMBOL_CLASS = 16

# epoch offset must equal 946684800 seconds. It represents the diff between the
# genesis of Unix time and Ripple-Epoch time
EPOCH_OFFSET = (
    datetime.datetime(2000, 1, 1) - datetime.datetime(1970, 1, 1)
).total_seconds()


@require_kwargs_on_init
@dataclass(frozen=True)
class OracleSet(Transaction):
    """Creates a new Oracle ledger entry or updates the fields of an existing one,
    using the Oracle ID.

    The oracle provider must complete these steps before submitting this transaction:

    Create or own the XRPL account in the Owner field and have enough XRP to meet the
    reserve and transaction fee requirements.
    Publish the XRPL account public key, so it can be used for verification by dApps.
    Publish a registry of available price oracles with their unique OracleDocumentID .
    """

    account: str = REQUIRED  # type: ignore
    """This account must match the account in the Owner field of the Oracle object."""

    oracle_document_id: int = REQUIRED  # type: ignore
    """A unique identifier of the price oracle for the Account."""

    provider: Optional[str] = None
    """
    This field must be hex-encoded. You can use `xrpl.utils.str_to_hex` to
    convert a UTF-8 string to hex.

    An arbitrary value that identifies an oracle provider, such as Chainlink, Band, or
    DIA. This field is a string, up to 256 ASCII hex encoded characters (0x20-0x7E).
    This field is required when creating a new Oracle ledger entry, but is optional for
    updates.
    """

    uri: Optional[str] = None
    """
    This field must be hex-encoded. You can use `xrpl.utils.str_to_hex` to
    convert a UTF-8 string to hex.

    An optional Universal Resource Identifier to reference price data off-chain. This
    field is limited to 256 bytes.
    """

    asset_class: Optional[str] = None
    """
    This field must be hex-encoded. You can use `xrpl.utils.str_to_hex` to
    convert a UTF-8 string to hex.

    Describes the type of asset, such as "currency", "commodity", or "index". This
    field is a string, up to 16 ASCII hex encoded characters (0x20-0x7E). This field is
    required when creating a new Oracle ledger entry, but is optional for updates.
    """

    last_update_time: int = REQUIRED  # type: ignore
    """LastUpdateTime is the specific point in time when the data was last updated.
    The LastUpdateTime is represented as Unix Time - the number of seconds since
    January 1, 1970 (00:00 UTC)."""

    price_data_series: List[PriceData] = REQUIRED  # type: ignore
    """An array of up to 10 PriceData objects, each representing the price information
    for a token pair. More than five PriceData objects require two owner reserves."""

    transaction_type: TransactionType = field(
        default=TransactionType.ORACLE_SET,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        errors = super()._get_errors()

        # If price_data_series is not set, do not perform further validation
        if "price_data_series" not in errors:
            if len(self.price_data_series) == 0:
                errors["price_data_series"] = "Field must have a length greater than 0."

            if len(self.price_data_series) > MAX_ORACLE_DATA_SERIES:
                errors["price_data_series"] = (
                    "Field must have a length less than"
                    f" or equal to {MAX_ORACLE_DATA_SERIES}"
                )

            # either asset_price and scale are both present or both excluded
            for price_data in self.price_data_series:
                if (price_data.asset_price is not None) != (
                    price_data.scale is not None
                ):
                    errors["price_data_series"] = (
                        "Field must have both "
                        "`AssetPrice` and `Scale` if any are present"
                    )

        if self.asset_class is not None and len(self.asset_class) == 0:
            errors["asset_class"] = "Field must have a length greater than 0."

        if (
            self.asset_class is not None
            and len(self.asset_class) > MAX_ORACLE_SYMBOL_CLASS
        ):
            errors["asset_class"] = (
                "Field must have a length less than"
                f" or equal to {MAX_ORACLE_SYMBOL_CLASS}"
            )

        if self.provider is not None and len(self.provider) == 0:
            errors["provider"] = "Field must have a length greater than 0."

        if self.provider is not None and len(self.provider) > MAX_ORACLE_PROVIDER:
            errors["provider"] = (
                f"Field must have a length less than or equal to {MAX_ORACLE_PROVIDER}."
            )

        if self.uri is not None and len(self.uri) == 0:
            errors["uri"] = "Field must have a length greater than 0."

        if self.uri is not None and len(self.uri) > MAX_ORACLE_URI:
            errors["uri"] = (
                f"Field must have a length less than or equal to {MAX_ORACLE_URI}."
            )

        # check on the last_update_time
        if self.last_update_time < EPOCH_OFFSET:
            errors["last_update_time"] = (
                "LastUpdateTime must be greater than or equal"
                f" to Ripple-Epoch {EPOCH_OFFSET} seconds"
            )

        return errors


@require_kwargs_on_init
@dataclass(frozen=True)
class PriceData(NestedModel):
    """Represents one PriceData element. It is used in OracleSet transaction"""

    base_asset: str = REQUIRED  # type: ignore
    """The primary asset in a trading pair. Any valid identifier, such as a stock
    symbol, bond CUSIP, or currency code is allowed. For example, in the BTC/USD pair,
    BTC is the base asset; in 912810RR9/BTC, 912810RR9 is the base asset."""

    quote_asset: str = REQUIRED  # type: ignore
    """The quote asset in a trading pair. The quote asset denotes the price of one unit
    of the base asset. For example, in the BTC/USD pair, BTC is the base asset; in
    912810RR9/BTC, 912810RR9 is the base asset."""

    asset_price: Optional[int] = None
    """The asset price after applying the Scale precision level. It's not included if
    the last update transaction didn't include the BaseAsset/QuoteAsset pair."""

    scale: Optional[int] = None
    """The scaling factor to apply to an asset price. For example, if Scale is 6 and
    original price is 0.155, then the scaled price is 155000. Valid scale ranges are
    0-10. It's not included if the last update transaction didn't include the
    BaseAsset/QuoteAsset pair."""
