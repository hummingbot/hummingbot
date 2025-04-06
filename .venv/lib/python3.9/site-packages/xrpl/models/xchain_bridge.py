"""A XChainBridge represents a cross-chain bridge."""

from __future__ import annotations

from dataclasses import dataclass

from xrpl.models.base_model import BaseModel
from xrpl.models.currencies import Currency
from xrpl.models.utils import KW_ONLY_DATACLASS, require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True, **KW_ONLY_DATACLASS)
class XChainBridge(BaseModel):
    """A XChainBridge represents a cross-chain bridge."""

    locking_chain_door: str
    """
    The door account on the locking chain.
    """

    locking_chain_issue: Currency
    """
    The asset that is locked and unlocked on the locking chain.
    """

    issuing_chain_door: str
    """
    The door account on the issuing chain. For an XRP-XRP bridge, this must be
    the genesis account (the account that is created when the network is first
    started, which contains all of the XRP).
    """

    issuing_chain_issue: Currency
    """
    The asset that is minted and burned on the issuing chain. For an IOU-IOU
    bridge, the issuer of the asset must be the door account on the issuing
    chain, to avoid supply issues.
    """
