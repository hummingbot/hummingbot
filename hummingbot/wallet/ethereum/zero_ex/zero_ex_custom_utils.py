from typing import Tuple
from zero_ex.order_utils import (
    _Constants,
    _convert_ec_signature_to_vrs_hex,
    _parse_signature_hex_as_vrs,
    _parse_signature_hex_as_rsv,
    is_valid_signature,
    Order
)


def convert_order_to_tuple(order: Order) -> Tuple[str, any]:
    order_tuple = (order["makerAddress"],
                   order["takerAddress"],
                   order["feeRecipientAddress"],
                   order["senderAddress"],
                   int(order["makerAssetAmount"]),
                   int(order["takerAssetAmount"]),
                   int(order["makerFee"]),
                   int(order["takerFee"]),
                   int(order["expirationTimeSeconds"]),
                   int(order["salt"]),
                   order["makerAssetData"],
                   order["takerAssetData"])
    return order_tuple


# fix_signature extracts the logic used for formatting the signature required by the 0x protocol from 0x's custom
# sign_hash helper.
# https://github.com/0xProject/0x-monorepo/blob/development/python-packages/order_utils/src/zero_ex/order_utils/__init__.py#L462
def fix_signature(provider, signer_address, hash_hex, signature) -> str:
    valid_v_param_values = [27, 28]

    # HACK: There is no consensus on whether the signatureHex string should be
    # formatted as v + r + s OR r + s + v, and different clients (even
    # different versions of the same client) return the signature params in
    # different orders. In order to support all client implementations, we
    # parse the signature in both ways, and evaluate if either one is a valid
    # signature.  r + s + v is the most prevalent format from eth_sign, so we
    # attempt this first.

    ec_signature = _parse_signature_hex_as_rsv(signature)
    if ec_signature["v"] in valid_v_param_values:
        signature_as_vrst_hex = (
            _convert_ec_signature_to_vrs_hex(ec_signature)
            + _Constants.SignatureType.ETH_SIGN.value.to_bytes(
                1, byteorder="big"
            ).hex()
        )

        (valid, _) = is_valid_signature(
            provider, hash_hex, signature_as_vrst_hex, signer_address
        )

        if valid is True:
            return signature_as_vrst_hex

    ec_signature = _parse_signature_hex_as_vrs(signature)
    if ec_signature["v"] in valid_v_param_values:
        signature_as_vrst_hex = (
            _convert_ec_signature_to_vrs_hex(ec_signature)
            + _Constants.SignatureType.ETH_SIGN.value.to_bytes(
                1, byteorder="big"
            ).hex()
        )
        (valid, _) = is_valid_signature(
            provider, hash_hex, signature_as_vrst_hex, signer_address
        )

        if valid is True:
            return signature_as_vrst_hex

    raise RuntimeError(
        "Signature returned from web3 provider is in an unknown format."
        + " Attempted to parse as RSV and as VRS."
    )

