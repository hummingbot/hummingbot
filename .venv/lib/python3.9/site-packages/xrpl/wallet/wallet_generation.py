"""Handles wallet generation from a faucet."""

import asyncio
from typing import Optional

from xrpl.asyncio.wallet import generate_faucet_wallet as async_generate_faucet_wallet
from xrpl.clients.sync_client import SyncClient
from xrpl.wallet.main import Wallet


def generate_faucet_wallet(
    client: SyncClient,
    wallet: Optional[Wallet] = None,
    debug: bool = False,
    faucet_host: Optional[str] = None,
    usage_context: Optional[str] = None,
) -> Wallet:
    """
    Generates a random wallet and funds it using the XRPL Testnet Faucet.

    Args:
        client: the network client used to make network calls.
        wallet: the wallet to fund. If omitted or `None`, a new wallet is created.
        debug: Whether to print debug information as it creates the wallet.
        faucet_host: A custom host to use for funding a wallet. In environments other
            than devnet and testnet, this parameter is required.
        usage_context: The intended use case for the funding request
            (for example, testing). This information will be included in json body
            of the HTTP request to the faucet.

    Returns:
        A Wallet on the testnet that contains some amount of XRP.

    Raises:
        XRPLFaucetException: if an address could not be funded with the faucet.
        XRPLRequestFailureException: if a request to the ledger fails.
        requests.exceptions.HTTPError: if the request to the faucet fails.

    .. # noqa: DAR402 exception raised in private method
    """
    return asyncio.run(
        async_generate_faucet_wallet(client, wallet, debug, faucet_host, usage_context)
    )
