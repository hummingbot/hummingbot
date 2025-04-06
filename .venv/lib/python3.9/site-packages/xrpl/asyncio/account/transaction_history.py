"""High-level methods to obtain information about account transaction history."""

from xrpl.asyncio.clients import Client, XRPLRequestFailureException
from xrpl.core.addresscodec import is_valid_xaddress, xaddress_to_classic_address
from xrpl.models.requests import AccountTx
from xrpl.models.response import Response


async def get_latest_transaction(account: str, client: Client) -> Response:
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
    # max == -1 means that it's the most recent validated ledger version
    if is_valid_xaddress(account):
        account, _, _ = xaddress_to_classic_address(account)
    response = await client._request_impl(
        AccountTx(account=account, ledger_index_max=-1, limit=1)
    )
    if not response.is_successful():
        raise XRPLRequestFailureException(response.result)
    return response
