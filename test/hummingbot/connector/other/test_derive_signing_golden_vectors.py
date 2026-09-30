import json
import unittest
from decimal import Decimal
from pathlib import Path

from hummingbot.connector.other.derive_common_utils import (
    ModuleData,
    SignedAction,
    TradeModuleData,
    big_int_to_decimal_str,
    compute_domain_separator,
    decimal_to_big_int,
    estimate_max_fee,
    get_action_nonce,
    get_signature_expiry_sec,
)

GOLDEN_VECTORS = Path(__file__).parent / "fixtures" / "derive_golden_vectors.json"

# Published v3 domain separators, from docs.derive.xyz. The point of the tests below is that we
# never hardcode these in the connector: they are derived, and these values only pin the
# derivation.
MAINNET_CHAIN_ID = 1
TESTNET_CHAIN_ID = 11155111
MATCHING_CONTRACT = "0xeB8d770ec18DB98Db922E9D83260A585b9F0DeAD"  # noqa: mock
MAINNET_DOMAIN_SEPARATOR = "0xda616dfabb88681b08e1592820a41d55ddc62d68de110e327ae99d734506fe19"  # noqa: mock
TESTNET_DOMAIN_SEPARATOR = "0x24d674cd5f2b9d564691c51e9d88f649b99246a2244dd74ce27b96578d773e85"  # noqa: mock


class _RawModuleData(ModuleData):
    """Passes a pre-encoded blob through, for the envelope-only vectors."""

    def __init__(self, raw_hex: str):
        self._raw = bytes.fromhex(raw_hex[2:])

    def to_abi_encoded(self) -> bytes:
        return self._raw

    def to_json(self):
        return {}


class DeriveSigningGoldenVectorsTests(unittest.TestCase):
    """
    Replays the official derive-ts golden vectors
    (test/unit/fixtures/golden-vectors.json in derivexyz/derive-ts).

    These pin the whole signing scheme - trade-module ABI encoding, action hash, typed data hash
    and the final signature bytes - against the reference implementation, which is the only way to
    be confident about signing without a funded testnet account.
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.vectors = json.loads(GOLDEN_VECTORS.read_text())
        cls.cases = {case["name"]: case for case in cls.vectors["cases"]}

    def _signed_action(self, case, module_data) -> SignedAction:
        inputs = case["inputs"]
        return SignedAction(
            subaccount_id=inputs["subaccount_id"],
            owner=inputs["owner"],
            signer=inputs["signer"],
            signature_expiry_sec=inputs["signature_expiry_sec"],
            nonce=int(inputs["nonce"]),
            module_address=inputs["module"],
            module_data=module_data,
            DOMAIN_SEPARATOR=self.vectors["domainSeparator"],
            ACTION_TYPEHASH=self.vectors["actionTypehash"],
        )

    def _assert_matches_vector(self, case, module_data):
        action = self._signed_action(case, module_data)

        self.assertEqual(case["actionHash"].lower(), "0x" + action._get_action_hash().hex().lower())
        self.assertEqual(
            case["typedDataHash"].lower(), "0x" + action._to_typed_data_hash().hex().lower()
        )
        signature = action.sign(self.vectors["signerPrivateKey"])
        self.assertEqual(case["signature"].lower(), signature.lower())

        # And the signature must recover to the signer.
        action.validate_signature()

    def test_envelope_minimal_vector(self):
        case = self.cases["envelope-minimal"]
        self._assert_matches_vector(case, _RawModuleData(case["inputs"]["data"]))

    def test_envelope_large_vector(self):
        case = self.cases["envelope-large"]
        self._assert_matches_vector(case, _RawModuleData(case["inputs"]["data"]))

    def test_trade_module_vector(self):
        case = self.cases["trade"]
        inputs = case["inputs"]
        module_data = TradeModuleData(
            asset_address=inputs["asset_address"],
            sub_id=int(inputs["sub_id"]),
            limit_price=Decimal(inputs["limit_price"]),
            amount=Decimal(inputs["amount"]),
            max_fee=Decimal(inputs["max_fee"]),
            recipient_id=int(inputs["recipient_subaccount_id"]),
            is_bid=inputs["is_bid"],
        )

        # The ABI encoding of the trade data itself.
        self.assertEqual(case["dataHex"].lower(), "0x" + module_data.to_abi_encoded().hex().lower())

        self._assert_matches_vector(case, module_data)

    def test_trade_wire_values_are_rendered_from_the_signed_words(self):
        """The JSON the exchange matches on must not drift from what was signed."""
        inputs = self.cases["trade"]["inputs"]
        module_data = TradeModuleData(
            asset_address=inputs["asset_address"],
            sub_id=int(inputs["sub_id"]),
            limit_price=Decimal(inputs["limit_price"]),
            amount=Decimal(inputs["amount"]),
            max_fee=Decimal(inputs["max_fee"]),
            recipient_id=int(inputs["recipient_subaccount_id"]),
            is_bid=inputs["is_bid"],
        )

        self.assertEqual(
            {"limit_price": "1500.5", "amount": "2.5", "max_fee": "100"}, module_data.to_json()
        )


class DeriveDomainSeparatorTests(unittest.TestCase):
    def test_domain_separator_is_derived_not_hardcoded(self):
        """
        Hardcoding the separator is how it went stale across the v2 to v3 move. Deriving it means
        a chain id change is all that is needed.
        """
        self.assertEqual(
            MAINNET_DOMAIN_SEPARATOR,
            compute_domain_separator(MAINNET_CHAIN_ID, MATCHING_CONTRACT),
        )
        self.assertEqual(
            TESTNET_DOMAIN_SEPARATOR,
            compute_domain_separator(TESTNET_CHAIN_ID, MATCHING_CONTRACT),
        )

    def test_domain_separator_reproduces_the_legacy_v2_value(self):
        """
        The same derivation on the old Derive L2 chain id reproduces the v2 separator, which
        confirms the formula rather than the constants.
        """
        self.assertEqual(
            "0xd96e5f90797da7ec8dc4e276260c7f3f87fedf68775fbe1ef116e996fc60441b",  # noqa: mock
            compute_domain_separator(957, MATCHING_CONTRACT),
        )


class DeriveEncodingTests(unittest.TestCase):
    def test_e18_round_trip(self):
        for value in ("1500.5", "2.5", "100", "0.000000000001", "-3.25"):
            self.assertEqual(
                value, big_int_to_decimal_str(decimal_to_big_int(Decimal(value))), f"for {value}"
            )

    def test_precision_finer_than_1e_12_is_rejected_not_truncated(self):
        """v3 rejects the order rather than rounding, so signing it would waste a round trip."""
        with self.assertRaises(ValueError) as ctx:
            decimal_to_big_int(Decimal("0.0000000000001"))  # 1e-13
        self.assertIn("1e-12", str(ctx.exception))

    def test_values_outside_int128_are_rejected(self):
        with self.assertRaises(ValueError):
            decimal_to_big_int(Decimal(2 ** 127))

    def test_nonce_is_utc_nanoseconds_and_strictly_increasing(self):
        first = get_action_nonce()
        second = get_action_nonce()

        # Nanoseconds since the epoch is a 19 digit number for any plausible current date.
        self.assertEqual(19, len(str(first)))
        # The v2 scheme could repeat inside one millisecond; nanoseconds cannot.
        self.assertLess(first, second)

    def test_signature_expiry_must_stay_within_the_accepted_window(self):
        self.assertGreater(get_signature_expiry_sec(3600), 0)

        with self.assertRaises(ValueError):
            get_signature_expiry_sec(60)  # under 5 minutes
        with self.assertRaises(ValueError):
            get_signature_expiry_sec(2 ** 31 - 1)  # the v2 value

    def test_max_fee_matches_the_derive_ts_formula(self):
        # 3 * (2 * 0.0003 * max(2700, 2695) + 0.01) == 3 * (1.62 + 0.01) == 4.89
        self.assertEqual(
            Decimal("4.89"),
            estimate_max_fee(
                taker_fee_rate=Decimal("0.0003"),
                base_fee=Decimal("0.01"),
                index_price=Decimal("2695"),
                limit_price=Decimal("2700"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
