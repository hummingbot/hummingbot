"""High-level methods to obtain information about accounts."""

from typing import Dict, Union, cast

from xrpl.asyncio.clients import Client, XRPLRequestFailureException
from xrpl.core.addresscodec import is_valid_xaddress, xaddress_to_classic_address
from xrpl.models.requests import AccountInfo


async def does_account_exist(
    address: str, client: Client, ledger_index: Union[str, int] = "validated"
) -> bool:
    """
    Query the ledger for whether the account exists.

    Args:
        address: the account to query.
        client: the network client used to make network calls.
        ledger_index: The ledger index to use for the request. Must be an integer
            ledger value or "current" (the current working version), "closed" (for the
            closed-and-proposed version), or "validated" (the most recent version
            validated by consensus). The default is "validated".

    Returns:
        Whether the account exists on the ledger.

    Raises:
        XRPLRequestFailureException: if the transaction fails.
    """
    try:
        await get_account_root(address, client, ledger_index=ledger_index)
        return True
    except XRPLRequestFailureException as e:
        if e.error == "actNotFound":
            # error code for if the account is not found on the ledger
            return False
        raise


async def get_next_valid_seq_number(
    address: str, client: Client, ledger_index: Union[str, int] = "current"
) -> int:
    """
    Query the ledger for the next available sequence number for an account.

    Args:
        address: the account to query.
        client: the network client used to make network calls.
        ledger_index: The ledger index to use for the request. Must be an integer
            ledger value or "current" (the current working version), "closed" (for the
            closed-and-proposed version), or "validated" (the most recent version
            validated by consensus). The default is "current".

    Returns:
        The next valid sequence number for the address.
    """
    return cast(
        int, (await get_account_root(address, client, ledger_index))["Sequence"]
    )


async def get_balance(
    address: str, client: Client, ledger_index: Union[str, int] = "validated"
) -> int:
    """
    Query the ledger for the balance of the given account.

    Args:
        address: the account to query.
        client: the network client used to make network calls.
        ledger_index: The ledger index to use for the request. Must be an integer
            ledger value or "current" (the current working version), "closed" (for the
            closed-and-proposed version), or "validated" (the most recent version
            validated by consensus). The default is "validated".

    Returns:
        The balance of the address.
    """
    return int(
        (await get_account_root(address, client, ledger_index=ledger_index))["Balance"]
    )


async def get_account_root(
    address: str, client: Client, ledger_index: Union[str, int] = "validated"
) -> Dict[str, Union[int, str]]:
    """
    Query the ledger for the AccountRoot object associated with a given address.

    Args:
        address: the account to query.
        client: the network client used to make network calls.
        ledger_index: The ledger index to use for the request. Must be an integer
            ledger value or "current" (the current working version), "closed" (for the
            closed-and-proposed version), or "validated" (the most recent version
            validated by consensus). The default is "validated".

    Returns:
        The AccountRoot dictionary for the address.

    Raises:
        XRPLRequestFailureException: if the rippled API call fails.
    """
    classic_address = address

    if is_valid_xaddress(address):
        classic_address, _, _ = xaddress_to_classic_address(address)

    account_info = await client._request_impl(
        AccountInfo(
            account=classic_address,
            ledger_index=ledger_index,
        )
    )

    if not account_info.is_successful():
        raise XRPLRequestFailureException(account_info.result)

    return cast(Dict[str, Union[int, str]], account_info.result["account_data"])
