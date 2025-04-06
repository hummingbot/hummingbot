"""Model for NFTokenMint transaction type and related flags."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from typing_extensions import Final, Self

from xrpl.models.flags import FlagInterface
from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init

_MAX_URI_LENGTH: Final[int] = 512
_MAX_TRANSFER_FEE: Final[int] = 50000


class NFTokenMintFlag(int, Enum):
    """Transaction Flags for an NFTokenMint Transaction."""

    TF_BURNABLE = 0x00000001
    """
    If set, indicates that the minted token may be burned by the issuer even
    if the issuer does not currently hold the token. The current holder of
    the token may always burn it.
    """

    TF_ONLY_XRP = 0x00000002
    """
    If set, indicates that the token may only be offered or sold for XRP.
    """

    TF_TRUSTLINE = 0x00000004
    """
    If set, indicates that the issuer wants a trustline to be automatically
    created.
    """

    TF_TRANSFERABLE = 0x00000008
    """
    If set, indicates that this NFT can be transferred. This flag has no
    effect if the token is being transferred from the issuer or to the
    issuer.
    """


class NFTokenMintFlagInterface(FlagInterface):
    """Transaction Flags for an NFTokenMint Transaction."""

    TF_BURNABLE: bool
    TF_ONLY_XRP: bool
    TF_TRUSTLINE: bool
    TF_TRANSFERABLE: bool


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class NFTokenMint(Transaction):
    """
    The NFTokenMint transaction creates an NFToken object and adds it to the
    relevant NFTokenPage object of the minter. If the transaction is
    successful, the newly minted token will be owned by the minter account
    specified by the transaction.
    """

    nftoken_taxon: int = REQUIRED  # type: ignore
    """
    Indicates the taxon associated with this token. The taxon is generally a
    value chosen by the minter of the token and a given taxon may be used for
    multiple tokens. The implementation reserves taxon identifiers greater
    than or equal to 2147483648 (0x80000000). If you have no use for this
    field, set it to 0.

    :meta hide-value:
    """

    issuer: Optional[str] = None
    """
    Indicates the account that should be the issuer of this token. This value
    is optional and should only be specified if the account executing the
    transaction is not the `Issuer` of the `NFToken` object. If it is
    present, the `MintAccount` field in the `AccountRoot` of the `Issuer`
    field must match the `Account`, otherwise the transaction will fail.
    """

    transfer_fee: Optional[int] = None
    """
    Specifies the fee charged by the issuer for secondary sales of the Token,
    if such sales are allowed. Valid values for this field are between 0 and
    50000 inclusive, allowing transfer rates between 0.000% and 50.000% in
    increments of 0.001%. This field must NOT be present if the
    `tfTransferable` flag is not set.
    """

    uri: Optional[str] = None
    """
    URI that points to the data and/or metadata associated with the NFT.
    This field need not be an HTTP or HTTPS URL; it could be an IPFS URI, a
    magnet link, immediate data encoded as an RFC2379 "data" URL, or even an
    opaque issuer-specific encoding. The URI is not checked for validity.

    This field must be hex-encoded. You can use `xrpl.utils.str_to_hex` to
    convert a UTF-8 string to hex.
    """

    transaction_type: TransactionType = field(
        default=TransactionType.NFTOKEN_MINT,
        init=False,
    )

    def _get_errors(self: Self) -> Dict[str, str]:
        return {
            key: value
            for key, value in {
                **super()._get_errors(),
                "issuer": self._get_issuer_error(),
                "transfer_fee": self._get_transfer_fee_error(),
                "uri": self._get_uri_error(),
            }.items()
            if value is not None
        }

    def _get_issuer_error(self: Self) -> Optional[str]:
        if self.issuer == self.account:
            return "Must not be the same as the account"
        return None

    def _get_transfer_fee_error(self: Self) -> Optional[str]:
        if self.transfer_fee is not None and self.transfer_fee > _MAX_TRANSFER_FEE:
            return f"Must not be greater than {_MAX_TRANSFER_FEE}"
        return None

    def _get_uri_error(self: Self) -> Optional[str]:
        if self.uri is not None and len(self.uri) > _MAX_URI_LENGTH:
            return f"Must not be longer than {_MAX_URI_LENGTH} characters"
        return None
