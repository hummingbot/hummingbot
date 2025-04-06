from typing import (
    Any,
    Dict,
)

from eth_abi import (
    abi,
)
from eth_typing import (
    URI,
)
import requests

from web3._utils.http import (
    DEFAULT_HTTP_TIMEOUT,
)
from web3._utils.type_conversion import (
    to_bytes_if_hex,
    to_hex_if_bytes,
)
from web3.exceptions import (
    MultipleFailedRequests,
    Web3ValidationError,
)
from web3.types import (
    TxParams,
)


def handle_offchain_lookup(
    offchain_lookup_payload: Dict[str, Any],
    transaction: TxParams,
) -> bytes:
    formatted_sender = to_hex_if_bytes(offchain_lookup_payload["sender"]).lower()
    formatted_data = to_hex_if_bytes(offchain_lookup_payload["callData"]).lower()

    if formatted_sender != to_hex_if_bytes(transaction["to"]).lower():
        raise Web3ValidationError(
            "Cannot handle OffchainLookup raised inside nested call. "
            "Returned `sender` value does not equal `to` address in transaction."
        )

    session = requests.Session()
    for url in offchain_lookup_payload["urls"]:
        formatted_url = URI(
            str(url)
            .replace("{sender}", str(formatted_sender))
            .replace("{data}", str(formatted_data))
        )

        try:
            if "{data}" in url and "{sender}" in url:
                response = session.get(formatted_url, timeout=DEFAULT_HTTP_TIMEOUT)
            else:
                response = session.post(
                    formatted_url,
                    json={"data": formatted_data, "sender": formatted_sender},
                    timeout=DEFAULT_HTTP_TIMEOUT,
                )
        except Exception:
            continue  # try next url if timeout or issues making the request

        if (
            400 <= response.status_code <= 499
        ):  # if request returns 400 error, raise exception
            response.raise_for_status()
        if not 200 <= response.status_code <= 299:  # if not 400 error, try next url
            continue

        result = response.json()

        if "data" not in result.keys():
            raise Web3ValidationError(
                "Improperly formatted response for offchain lookup HTTP request"
                " - missing 'data' field."
            )

        encoded_data_with_function_selector = b"".join(
            [
                # 4-byte callback function selector
                to_bytes_if_hex(offchain_lookup_payload["callbackFunction"]),
                # encode the `data` from the result and the `extraData` as bytes
                abi.encode(
                    ["bytes", "bytes"],
                    [
                        to_bytes_if_hex(result["data"]),
                        to_bytes_if_hex(offchain_lookup_payload["extraData"]),
                    ],
                ),
            ]
        )

        return encoded_data_with_function_selector
    raise MultipleFailedRequests("Offchain lookup failed for supplied urls.")
