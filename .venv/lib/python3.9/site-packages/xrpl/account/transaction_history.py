"""High-level methods to obtain information about account transaction history."""

import asyncio

from xrpl.asyncio.account import transaction_history
from xrpl.clients.sync_client import SyncClient
from xrpl.models.response import Response


def get_latest_transaction(account: str, client: SyncClient) -> Response:
    """
    Fetches the most recent transaction on the ledger associated with an account.

    Args:
        account: the account to query.
        client: the network client used to communicate with a rippled node.

    Returns:
        The Response object containing the transaction info.

    Raises:
        XRPLRequestFailureException: if the transaction fails.
    """
    return asyncio.run(transaction_history.get_latest_transaction(account, client))
