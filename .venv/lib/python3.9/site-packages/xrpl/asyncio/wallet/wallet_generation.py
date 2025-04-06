"""Handles wallet generation from a faucet."""

import asyncio
from typing import Optional
from urllib.parse import urlparse, urlunparse

import httpx
from typing_extensions import Final

from xrpl.asyncio.account import get_balance, get_next_valid_seq_number
from xrpl.asyncio.clients import Client, XRPLRequestFailureException
from xrpl.constants import XRPLException
from xrpl.wallet.main import Wallet

_TEST_FAUCET_URL: Final[str] = "https://faucet.altnet.rippletest.net/accounts"
_DEV_FAUCET_URL: Final[str] = "https://faucet.devnet.rippletest.net/accounts"

_TIMEOUT_SECONDS: Final[int] = 40


class XRPLFaucetException(XRPLException):
    """Faucet generation exception."""

    pass


async def generate_faucet_wallet(
    client: Client,
    wallet: Optional[Wallet] = None,
    debug: bool = False,
    faucet_host: Optional[str] = None,
    usage_context: Optional[str] = None,
    user_agent: Optional[str] = "xrpl-py",
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
            (for example, testing). This information  will be included
            in the json body of the HTTP request to the faucet.
        user_agent: A string representing the user agent (software/ client used)
            for the HTTP request. Default is "xrpl-py".


    Returns:
        A Wallet on the testnet that contains some amount of XRP.

    Raises:
        XRPLFaucetException: if an address could not be funded with the faucet.
        XRPLRequestFailureException: if a request to the ledger fails.
        requests.exceptions.HTTPError: if the request to the faucet fails.

    .. # noqa: DAR402 exception raised in private method
    """
    faucet_url = get_faucet_url(client.url, faucet_host)

    if wallet is None:
        wallet = Wallet.create()

    address = wallet.address
    # The faucet *can* be flakey... by printing info about this it's easier to
    # understand if tests are actually failing, or if it was just a faucet failure.
    if debug:
        print("Attempting to fund address {}".format(address))
    # Balance prior to asking for more funds
    starting_balance = await _check_wallet_balance(address, client)

    # Ask the faucet to send funds to the given address
    await _request_funding(faucet_url, address, usage_context, user_agent)
    # Wait for the faucet to fund our account or until timeout
    # Waits one second checks if balance has changed
    # If balance doesn't change it will attempt again until _TIMEOUT_SECONDS
    is_funded = False
    for _ in range(_TIMEOUT_SECONDS):
        await asyncio.sleep(1)
        if not is_funded:  # faucet transaction hasn't been validated yet
            current_balance = await _check_wallet_balance(address, client)
            # If our current balance has changed, then the account has been funded
            if current_balance > starting_balance:
                if debug:
                    print("Faucet fund successful.")
                is_funded = True
        else:  # wallet has been funded, now the ledger needs to know the account exists
            next_seq_num = await _try_to_get_next_seq(address, client)
            if next_seq_num is not None:
                return wallet

    raise XRPLFaucetException(
        "Unable to fund address with faucet after waiting {} seconds".format(
            _TIMEOUT_SECONDS
        )
    )


def process_faucet_host_url(input_url: str) -> str:
    """
    Construct a URL from the given input string.

    Args:
        input_url (str): The input string that may or may not include a protocol,
                       and may or may not have a path.

    Returns:
        str: The constructed URL with https as the default protocol and /accounts as the
        default path.
    """
    # Strip the trailing forward slash
    input_url = input_url.rstrip("/")

    # prepend the layer-5 internet protocol, if not already present
    # Read the comment about netloc to understand the behavior of urllib.urlparse
    # without the protocol at the beginning of the URL
    if "://" not in input_url:
        input_url = "https://" + input_url

    # Parse the input URL to identify its components.
    parsed_url = urlparse(input_url)

    # If the input string includes a protocol (e.g., "https://"), urlparse will
    # correctly parse it.
    # Scheme refers to the protocol (e.g., "https", "http").
    scheme = parsed_url.scheme if parsed_url.scheme else "https"

    # Netloc is the network location part, which usually includes the domain name.
    # For input "https://abcd.com", netloc is "abcd.com".
    # If no protocol is provided, the domain might be parsed as the path.
    # Consider the input string "abcd.com". If you were to parse this string using
    # urlparse without manually prepending a protocol (like http:// or https://), the
    # parsing logic would interpret "abcd.com" not as the network location part
    # (or domain) of the URL, but rather as the path component. This is because
    # urlparse expects a scheme (protocol) to correctly identify the parts of the URL.
    # Hence, we check if netloc is present; if not, assume the path is actually the
    # netloc.
    netloc = parsed_url.netloc if parsed_url.netloc else parsed_url.path
    path = parsed_url.path if parsed_url.netloc else ""

    # If no specific path is provided, append '/accounts' to the URL.
    # For input "abcd.com", the constructed path will be "/accounts".
    if not path:
        path = "/accounts"

    # Construct the final URL by reassembling its components.
    final_url = urlunparse((scheme, netloc, path, "", "", ""))

    return final_url


def get_faucet_url(url: str, faucet_host: Optional[str] = None) -> str:
    """
    Returns the URL of the faucet that should be used, based on whether the URL is from
    a testnet or devnet client.

    Args:
        url: The URL that the client is using to access the ledger.
        faucet_host: A custom host to use for funding a wallet.

    Returns:
        The URL of the matching faucet.

    Raises:
        XRPLFaucetException: if the provided URL is not for the testnet or devnet.
    """
    if faucet_host is not None:
        return process_faucet_host_url(faucet_host)
    if "altnet" in url or "testnet" in url:  # testnet
        return _TEST_FAUCET_URL
    if "sidechain-net2" in url:  # sidechain issuing chain devnet
        raise XRPLFaucetException(
            "Cannot fund an account on an issuing chain. Accounts must be created via "
            "the bridge."
        )
    if "devnet" in url:  # devnet
        return _DEV_FAUCET_URL
    raise XRPLFaucetException(
        "Cannot fund an account with a client that is not on the testnet or devnet."
    )


async def _check_wallet_balance(address: str, client: Client) -> int:
    try:
        return await get_balance(address, client)
    except XRPLRequestFailureException as e:
        if e.error == "actNotFound":  # transaction has not gone through
            return 0
        # some other error
        raise


async def _request_funding(
    url: str,
    address: str,
    usage_context: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    async with httpx.AsyncClient() as http_client:
        json_body = {"destination": address, "userAgent": user_agent}
        if usage_context is not None:
            json_body["usageContext"] = usage_context
        response = await http_client.post(url=url, json=json_body)
    if not response.status_code == httpx.codes.OK:
        response.raise_for_status()


async def _try_to_get_next_seq(address: str, client: Client) -> Optional[int]:
    try:
        return await get_next_valid_seq_number(address, client)
    except XRPLRequestFailureException as e:
        if e.error == "actNotFound":
            # faucet gen has not fully gone through, try again
            return None
        # some other error
        raise
