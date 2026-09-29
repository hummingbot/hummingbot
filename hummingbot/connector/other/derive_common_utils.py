"""
Shared signing helpers for the Derive v3 API.

Ported from the official SDKs (``derive-py`` ``_web3/action_signing`` and ``derive-ts``) rather
than taken as a dependency: ``derive-py`` is an early beta that pulls in pandas, rich, click and
web3 7, and ships its own HTTP/WS session stack which would duplicate the web-assistant layer.

The hashing scheme is pinned by the ``derive-ts`` golden vectors, which the unit tests replay:

    actionHash    = keccak256(abi.encode(
                        [bytes32, uint256, uint256, address, bytes32, uint256, address, address],
                        [ACTION_TYPEHASH, subaccount_id, nonce, module,
                         keccak256(module_data), signature_expiry_sec, owner, signer]))
    typedDataHash = keccak256(0x1901 || DOMAIN_SEPARATOR || actionHash)
    signature     = ECDSA(signing_key, typedDataHash)   # r || s || v
"""
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict

from eth_abi.abi import encode
from hexbytes import HexBytes
from web3 import Account, Web3

# The EIP-712 domain is identical on every network; only the chain id changes. Deriving the
# separator instead of hardcoding it is what stops it going stale the way the v2 value did.
EIP712_DOMAIN_NAME = "Matching"
EIP712_DOMAIN_VERSION = "1.0"
EIP712_DOMAIN_TYPEHASH = Web3.keccak(
    text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
)

# v3 signed decimals are still e18 words, but the API rejects (rather than truncates) precision
# finer than 1e-12, and the signed values have to fit in an i128.
SIGNED_DECIMALS = 18
MAX_SIGNED_PRECISION = Decimal("1e-12")
MAX_INT_128 = 2 ** 127 - 1
MIN_INT_128 = -(2 ** 127)

# signature_expiry_sec bounds enforced by the API: error 11011 outside this window.
MIN_SIGNATURE_EXPIRY_SEC = 300
MAX_SIGNATURE_EXPIRY_SEC = 120 * 24 * 60 * 60

# Guards the nonce counter so concurrently signed orders cannot draw the same value.
_nonce_lock = threading.Lock()
_last_nonce = 0


def compute_domain_separator(chain_id: int, verifying_contract: str) -> str:
    """
    Derives the EIP-712 domain separator for a Derive deployment.

    :param chain_id: the settlement chain id (1 mainnet, 11155111 Sepolia testnet)
    :param verifying_contract: the Matching contract address
    :return: the 0x-prefixed 32-byte domain separator
    """
    return "0x" + Web3.keccak(
        encode(
            ["bytes32", "bytes32", "bytes32", "uint256", "address"],
            [
                EIP712_DOMAIN_TYPEHASH,
                Web3.keccak(text=EIP712_DOMAIN_NAME),
                Web3.keccak(text=EIP712_DOMAIN_VERSION),
                int(chain_id),
                Web3.to_checksum_address(verifying_contract),
            ],
        )
    ).hex()


def decimal_to_big_int(value: Decimal) -> int:
    """
    Converts a decimal to the e18 integer word that gets signed.

    v3 rejects anything finer than 1e-12 instead of rounding it away, so a value that would lose
    precision is refused here rather than being silently altered between what is signed and what
    the caller asked for.

    :param value: the decimal to encode
    :return: the value scaled by 1e18
    """
    value = Decimal(value)

    # Comparing against a quantized copy would overflow the decimal context for very large
    # values, so inspect the exponent instead. normalize() first so that a value carrying
    # trailing zeros, such as 1.500000000000000, is not mistaken for excess precision.
    exponent = value.normalize().as_tuple().exponent
    if isinstance(exponent, int) and exponent < MAX_SIGNED_PRECISION.as_tuple().exponent:
        raise ValueError(
            f"{value} is more precise than the 1e-12 the Derive API accepts; it would be rejected "
            f"rather than rounded. Quantize the value to the instrument's tick size or amount step "
            f"before signing."
        )

    result = int(value.scaleb(SIGNED_DECIMALS).to_integral_value())

    if result < MIN_INT_128 or result > MAX_INT_128:
        raise ValueError(f"resulting integer value must be between {MIN_INT_128} and {MAX_INT_128}")

    return result


def big_int_to_decimal_str(value: int) -> str:
    """
    Renders an e18 integer word back as the decimal string sent on the wire.

    The wire value is formatted from the signed word rather than from the original decimal, so the
    number the exchange matches on can never drift from the number that was signed.

    :param value: an e18 integer word
    :return: the decimal string, without exponent notation or trailing zeros
    """
    as_decimal = Decimal(value).scaleb(-SIGNED_DECIMALS)
    normalized = as_decimal.normalize()
    # normalize() turns 100 into 1E+2; quantizing back to an integer exponent undoes that.
    if normalized == normalized.to_integral_value():
        normalized = normalized.quantize(Decimal(1))
    return format(normalized, "f")


def get_action_nonce() -> int:
    """
    Builds the replay-protection nonce.

    v3 requires UTC nanoseconds and rejects millisecond or microsecond nonces.

    ``time.time_ns()`` is only nanosecond-*denominated*: on macOS the underlying clock ticks in
    microseconds, so back-to-back calls do repeat. A repeated nonce is the same collision the v2
    ``<ms><random>`` scheme suffered, so the counter is forced strictly upwards rather than
    trusted to be unique on its own.

    :return: a strictly increasing UTC nanosecond timestamp
    """
    global _last_nonce
    with _nonce_lock:
        nonce = max(time.time_ns(), _last_nonce + 1)
        _last_nonce = nonce
    return nonce


def get_signature_expiry_sec(valid_for_sec: int) -> int:
    """
    Builds a bounded signature expiry timestamp.

    v3 requires the expiry to be between 5 minutes and 120 days out (error 11011) and no later
    than the session key's own expiry (error 14038), so the v2 habit of sending 2**31-1 is
    rejected outright.

    :param valid_for_sec: how long the signature should remain valid
    :return: the absolute expiry timestamp in seconds
    """
    if not MIN_SIGNATURE_EXPIRY_SEC <= valid_for_sec <= MAX_SIGNATURE_EXPIRY_SEC:
        raise ValueError(
            f"signature validity must be between {MIN_SIGNATURE_EXPIRY_SEC} seconds and "
            f"{MAX_SIGNATURE_EXPIRY_SEC} seconds ({valid_for_sec} given); the Derive API rejects "
            f"anything outside that window with error 11011."
        )
    return int(time.time()) + int(valid_for_sec)


def estimate_max_fee(
    taker_fee_rate: Decimal,
    base_fee: Decimal,
    index_price: Decimal,
    limit_price: Decimal,
) -> Decimal:
    """
    Estimates the ``max_fee`` to sign an order with.

    Mirrors derive-ts: ``3 * (2 * taker_fee_rate * max(index_price, limit_price) + base_fee)``.
    The headroom matters because the fee is signed: if the fee actually charged exceeds the signed
    ceiling the order is rejected with error 11023, or cancelled with ``signed_max_fee_too_low``.

    :param taker_fee_rate: the instrument's taker fee rate
    :param base_fee: the instrument's flat base fee
    :param index_price: the current index price
    :param limit_price: the order's limit price
    :return: the max fee, quantized to the precision the API accepts
    """
    reference_price = max(Decimal(index_price), Decimal(limit_price))
    max_fee = 3 * (2 * Decimal(taker_fee_rate) * reference_price + Decimal(base_fee))
    return max_fee.quantize(MAX_SIGNED_PRECISION)


@dataclass
class ModuleData:
    def to_abi_encoded(self):
        pass

    def to_json(self):
        pass


@dataclass
class TradeModuleData(ModuleData):
    """
    Trade module payload. The layout is unchanged from v2:
    ``address asset, uint subId, int limitPrice, int amount, uint maxFee, uint recipientId, bool isBid``
    """

    asset_address: str
    sub_id: int
    limit_price: Decimal
    amount: Decimal
    max_fee: Decimal
    recipient_id: int
    is_bid: bool

    def to_abi_encoded(self) -> bytes:
        return encode(
            ["address", "uint", "int", "int", "uint", "uint", "bool"],
            [
                Web3.to_checksum_address(self.asset_address),
                int(self.sub_id),
                decimal_to_big_int(self.limit_price),
                decimal_to_big_int(self.amount),
                decimal_to_big_int(self.max_fee),
                int(self.recipient_id),
                self.is_bid,
            ],
        )

    def to_json(self) -> Dict[str, Any]:
        # Rendered from the signed e18 words so the wire values match the signature exactly.
        return {
            "limit_price": big_int_to_decimal_str(decimal_to_big_int(self.limit_price)),
            "amount": big_int_to_decimal_str(decimal_to_big_int(self.amount)),
            "max_fee": big_int_to_decimal_str(decimal_to_big_int(self.max_fee)),
        }


@dataclass
class SignedAction:
    """
    Used to sign and validate actions.

    :param subaccount_id: The subaccount id of the user.
    :param owner: The wallet that owns the account (not the session key).
    :param signer: The signer of the action - the owner or a session key.
    :param signature_expiry_sec: Absolute expiry timestamp in seconds. v3 requires 5 minutes to
        120 days from now, and no later than the session key's expiry.
    :param nonce: UTC nanoseconds. Serialized as a JSON string; v3 rejects ms/us nonces.
    :param module_address: The contract address of the module.
    :param module_data: Data defined by the specific protocol module.
    :param DOMAIN_SEPARATOR: The domain separator, from :func:`compute_domain_separator`.
    :param ACTION_TYPEHASH: The action typehash, unchanged between v2 and v3.
    :param signature: The signature of the action. Use sign() to generate it.
    """

    subaccount_id: int
    owner: str
    signer: str
    signature_expiry_sec: int
    nonce: int
    module_address: str
    module_data: ModuleData
    DOMAIN_SEPARATOR: str
    ACTION_TYPEHASH: str
    signature: str = ""

    def sign(self, signer_private_key: str) -> str:
        signer_wallet = Web3().eth.account.from_key(signer_private_key)
        signature: Account = signer_wallet.unsafe_sign_hash(self._to_typed_data_hash())
        self.signature = signature.signature.hex()
        if not self.signature.startswith("0x"):
            self.signature = "0x" + self.signature
        return self.signature

    def to_json(self) -> Dict[str, Any]:
        return {
            "subaccount_id": self.subaccount_id,
            # v3 requires the nanosecond nonce as a JSON string: as a number it would lose
            # precision in any consumer that parses JSON numbers as doubles.
            "nonce": str(self.nonce),
            "signer": self.signer,
            "signature_expiry_sec": self.signature_expiry_sec,
            "signature": self.signature,
            **self.module_data.to_json(),
        }

    def validate_signature(self):
        data_hash = self._to_typed_data_hash()
        recovered = Account._recover_hash(
            data_hash.hex(),
            signature=HexBytes(self.signature),
        )

        if recovered.lower() != self.signer.lower():
            raise ValueError("Invalid signature. Recovered signer does not match expected signer.")

    @property
    def domain_separator(self) -> bytes:
        try:
            return bytes.fromhex(self.DOMAIN_SEPARATOR[2:])
        except ValueError:
            raise ValueError(
                "Unable to extract bytes from DOMAIN_SEPARATOR. Derive it with "
                "compute_domain_separator(chain_id, verifying_contract)."
            )

    @property
    def action_typehash(self) -> bytes:
        try:
            return bytes.fromhex(self.ACTION_TYPEHASH[2:])
        except ValueError:
            raise ValueError(
                "Unable to extract bytes from ACTION_TYPEHASH. Ensure value is copied from "
                "Protocol Constants in docs.derive.xyz."
            )

    def _to_typed_data_hash(self) -> HexBytes:
        encoded_typed_data_hash = "".join(
            ["0x1901", self.DOMAIN_SEPARATOR[2:], self._get_action_hash().hex()]
        )
        return Web3.keccak(hexstr=encoded_typed_data_hash)

    def _get_action_hash(self) -> HexBytes:
        return Web3.keccak(
            encode(
                [
                    "bytes32",
                    "uint",
                    "uint",
                    "address",
                    "bytes32",
                    "uint",
                    "address",
                    "address",
                ],
                [
                    self.action_typehash,
                    self.subaccount_id,
                    self.nonce,
                    Web3.to_checksum_address(self.module_address),
                    Web3.keccak(self.module_data.to_abi_encoded()),
                    self.signature_expiry_sec,
                    Web3.to_checksum_address(self.owner),
                    Web3.to_checksum_address(self.signer),
                ],
            )
        )
