import json
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from hummingbot.connector.other.derive_common_utils import (
    MAX_SIGNATURE_EXPIRY_SEC,
    RESTING_ORDER_VALIDITY_SEC,
    SESSION_KEY_EXPIRY_MARGIN_SEC,
    ModuleData,
    SignedAction,
    TradeModuleData,
    big_int_to_decimal_str,
    compute_domain_separator,
    decimal_to_big_int,
    estimate_max_fee,
    get_action_nonce,
    get_order_signature_expiry_sec,
    get_signature_expiry_sec,
    parse_subaccount_id,
)

GOLDEN_VECTORS = Path(__file__).parent / "fixtures" / "derive_golden_vectors.json"

# The v3 domain separators as published in the "Domain separator" table at
# docs.derive.xyz/authentication/action-signing, which also gives the chain ids and the verifying
# contract. derive-py hardcodes the same two values (derive_py/config/contracts.py), and derive-ts
# derives them from the same chain ids and contract (src/config/networks.ts, src/signing/eip712.ts).
#
# The connector never hardcodes these: it derives them, and the values here pin the derivation
# against what Derive publishes.
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

    def test_max_fee_is_never_below_what_the_exchange_suggests(self):
        """
        order_quote returns the cap the exchange would sign itself, suggested_max_fee. These are
        the values the testnet returned on 2026-10-04 for minimum-size orders, with the index at
        the time. Every perp charges taker 0.0003, maker 0.0001 and a 0.01 base fee.

        They fit 1.1 * 2 * max(taker, maker) * max(limit, index), plus base_fee / amount_step for
        any order that can take: the flat base fee spread over the smallest possible fill, which
        is why the extra term is 10 on ETH, 100 on BTC and 0.1 on XRP whatever the order's size.
        """
        observed = [
            # label,                  index,      limit,     amount step, can take, suggested_max_fee
            ("ETH-PERP post_only buy", "2701.89", "1350.9", "0.001", False, "1.783249"),
            ("ETH-PERP gtc buy", "2701.89", "1350.9", "0.001", True, "11.783225"),
            ("ETH-PERP gtc sell", "2701.89", "4052.8", "0.001", True, "12.674874"),
            ("ETH-PERP market buy", "2701.89", "2755.9", "0.001", True, "11.783250"),
            ("BTC-PERP post_only buy", "85288.2", "42644.1", "0.0001", False, "56.283942"),
            ("BTC-PERP gtc buy", "85288.2", "42644.1", "0.0001", True, "156.284853"),
            ("BTC-PERP gtc sell", "85288.2", "127932.3", "0.0001", True, "184.435318"),
            ("XRP-PERP post_only buy", "1.50026", "0.7501", "0.1", False, "0.000991"),
            ("XRP-PERP gtc buy", "1.50026", "0.7501", "0.1", True, "0.100991"),
            ("XRP-PERP gtc sell", "1.50026", "2.2504", "0.1", True, "0.101485"),
        ]
        for label, index, limit, amount_step, can_take, suggested in observed:
            max_fee = estimate_max_fee(
                taker_fee_rate=Decimal("0.0003"),
                maker_fee_rate=Decimal("0.0001"),
                base_fee=Decimal("0.01"),
                index_price=Decimal(index),
                limit_price=Decimal(limit),
                amount_step=Decimal(amount_step),
                can_take=can_take,
            )
            self.assertGreaterEqual(max_fee, Decimal(suggested), label)

            reference_price = max(Decimal(index), Decimal(limit))
            expected = 3 * 2 * Decimal("0.0003") * reference_price
            if can_take:
                expected += Decimal("0.01") / Decimal(amount_step)
            self.assertEqual(expected, max_fee, label)

    def test_max_fee_does_not_depend_on_the_orders_own_size(self):
        """
        The cap is compared with the fee per unit of each fill, and a taker order's first fill can
        be as small as one amount step. Spreading the base fee over the order's own amount instead
        signed 0.44x of the exchange's suggestion on a minimum-size ETH order and 0.06x on XRP.
        """
        taker, base_fee, index = Decimal("0.0003"), Decimal("0.01"), Decimal("1.50026")
        max_fee = estimate_max_fee(
            taker_fee_rate=taker, base_fee=base_fee, index_price=index, limit_price=index, amount_step=Decimal("0.1")
        )
        over_the_orders_amount = 3 * (2 * taker * index + base_fee / Decimal("10"))    # a 10 XRP order

        self.assertEqual(3 * 2 * taker * index + Decimal("0.1"), max_fee)
        self.assertLess(over_the_orders_amount, Decimal("0.100991"))                   # under the suggestion
        self.assertGreater(max_fee, Decimal("0.100991"))

    def test_post_only_order_is_not_charged_the_base_fee_term(self):
        common = dict(
            taker_fee_rate=Decimal("0.0003"),
            base_fee=Decimal("0.01"),
            index_price=Decimal("2700"),
            limit_price=Decimal("2700"),
            amount_step=Decimal("0.001"),
        )
        self.assertEqual(Decimal("10"), estimate_max_fee(**common) - estimate_max_fee(can_take=False, **common))

    def test_max_fee_without_an_amount_step_takes_the_base_fee_per_whole_unit(self):
        # 3 * 2 * 0.0003 * max(2700, 2695) + 0.01 == 4.86 + 0.01
        self.assertEqual(
            Decimal("4.87"),
            estimate_max_fee(
                taker_fee_rate=Decimal("0.0003"),
                base_fee=Decimal("0.01"),
                index_price=Decimal("2695"),
                limit_price=Decimal("2700"),
            ),
        )

    def test_max_fee_uses_the_larger_fee_rate_and_the_larger_price(self):
        max_fee = estimate_max_fee(
            taker_fee_rate=Decimal("0.0003"),
            maker_fee_rate=Decimal("0.0005"),
            base_fee=Decimal("0"),
            index_price=Decimal("100"),
            limit_price=Decimal("90"),
        )
        self.assertEqual(Decimal("0.3"), max_fee)    # 3 * 2 * 0.0005 * 100

    def test_max_fee_is_rounded_up_to_signable_precision(self):
        max_fee = estimate_max_fee(
            taker_fee_rate=Decimal("0.0003"),
            base_fee=Decimal("0.01"),
            index_price=Decimal("2.5"),
            limit_price=Decimal("2.5"),
            amount_step=Decimal("3"),            # 0.01 / 3 does not terminate
        )
        self.assertGreaterEqual(max_fee, 3 * 2 * Decimal("0.0003") * Decimal("2.5") + Decimal("0.01") / 3)
        decimal_to_big_int(max_fee)              # would raise if finer than 1e-12

    def test_subaccount_id_is_normalised_to_an_integer(self):
        for configured in ("45686", 45686, " 45686 "):
            parsed = parse_subaccount_id(configured)
            self.assertEqual(45686, parsed)
            self.assertIs(int, type(parsed))

        # No account configured, as when a connector is built only to list trading pairs.
        self.assertIsNone(parse_subaccount_id(None))
        self.assertIsNone(parse_subaccount_id(""))

        with self.assertRaises(ValueError) as context:
            parse_subaccount_id("main-account")
        self.assertIn("must be a whole number", str(context.exception))

    def test_resting_order_validity_sits_just_inside_the_api_ceiling(self):
        self.assertLess(RESTING_ORDER_VALIDITY_SEC, MAX_SIGNATURE_EXPIRY_SEC)
        self.assertEqual(24 * 60 * 60, MAX_SIGNATURE_EXPIRY_SEC - RESTING_ORDER_VALIDITY_SEC)

    def test_order_signature_expiry_is_held_inside_the_session_key_lifetime(self):
        now = 1_700_000_000
        with patch("hummingbot.connector.other.derive_common_utils.time.time", return_value=now):
            # No key expiry known: the requested window stands.
            self.assertEqual(now + 3600, get_order_signature_expiry_sec(3600))
            self.assertEqual(now + 3600, get_order_signature_expiry_sec(3600, None))

            # The key outlives the window: unchanged.
            self.assertEqual(now + 3600, get_order_signature_expiry_sec(3600, now + 86400))

            # The window would outlive the key: shortened to end just before it (14038 otherwise).
            key_expiry = now + 86400
            self.assertEqual(
                key_expiry - SESSION_KEY_EXPIRY_MARGIN_SEC,
                get_order_signature_expiry_sec(RESTING_ORDER_VALIDITY_SEC, key_expiry),
            )

            # Too little of the key left to sign anything with.
            with self.assertRaises(ValueError) as context:
                get_order_signature_expiry_sec(3600, now + 200)
            self.assertIn("expires in 200 seconds", str(context.exception))
            with self.assertRaises(ValueError) as context:
                get_order_signature_expiry_sec(3600, now - 1)
            self.assertIn("has expired", str(context.exception))


if __name__ == "__main__":
    unittest.main()
