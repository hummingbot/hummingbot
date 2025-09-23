from unittest.async_case import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from xrpl.models import Response, Transaction
from xrpl.models.response import ResponseStatus

from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange


class TestXRPLSubmitTransaction(IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.exchange = XrplExchange(
            xrpl_secret_key="",
            wss_node_urls=["wss://sample.com"],
            max_request_per_minute=100,
            trading_pairs=["SOLO-XRP"],
            trading_required=False,
        )
        self.exchange._sleep = AsyncMock()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient")
    async def test_submit_transaction_success(self, mock_client_class):
        """Test successful transaction submission with proper mocking."""
        # Setup client mock
        mock_client_instance = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client_instance

        # Setup transaction mocks
        mock_transaction = MagicMock(spec=Transaction)
        mock_filled_tx = MagicMock(spec=Transaction)
        mock_signed_tx = MagicMock(spec=Transaction)
        mock_wallet = MagicMock()

        # Setup successful response
        mock_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "ledger_index": 99999221,
                "validated": True,
                "meta": {
                    "TransactionResult": "tesSUCCESS",
                },
            },
        )

        # Mock necessary methods
        self.exchange.tx_autofill = AsyncMock(return_value=mock_filled_tx)
        self.exchange._xrpl_auth = MagicMock()
        self.exchange._xrpl_auth.get_wallet.return_value = mock_wallet

        # Patch sign and submit_and_wait methods
        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.sign", return_value=mock_signed_tx) as mock_sign:
            with patch(
                "hummingbot.connector.exchange.xrpl.xrpl_exchange.async_submit_and_wait", return_value=mock_response
            ) as mock_submit_and_wait:
                # Execute the method
                result = await self.exchange._submit_transaction(mock_transaction)

                # Verify results
                self.assertEqual(result, mock_response)

                # Verify method calls
                self.exchange.tx_autofill.assert_awaited_once_with(mock_transaction, mock_client_instance)
                self.exchange._xrpl_auth.get_wallet.assert_called_once()
                mock_sign.assert_called_once_with(mock_filled_tx, mock_wallet)
                mock_submit_and_wait.assert_awaited_once_with(
                    mock_signed_tx, mock_client_instance, mock_wallet, autofill=False, fail_hard=True
                )

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_constants.PLACE_ORDER_MAX_RETRY", 1)
    async def test_submit_transaction_error_response(self, mock_client_class):
        """Test transaction submission with error response."""
        # Setup client mock
        mock_client_instance = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client_instance

        # Setup transaction mocks
        mock_transaction = MagicMock(spec=Transaction)
        mock_filled_tx = MagicMock(spec=Transaction)
        mock_signed_tx = MagicMock(spec=Transaction)
        mock_wallet = MagicMock()

        # Setup error response
        error_response = Response(
            status=ResponseStatus.ERROR,
            result={"error": "test error message"},
        )

        # Mock necessary methods
        self.exchange.tx_autofill = AsyncMock(return_value=mock_filled_tx)
        self.exchange._xrpl_auth = MagicMock()
        self.exchange._xrpl_auth.get_wallet.return_value = mock_wallet

        # Patch sign and submit_and_wait methods
        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.sign", return_value=mock_signed_tx):
            with patch(
                "hummingbot.connector.exchange.xrpl.xrpl_exchange.async_submit_and_wait", return_value=error_response
            ):
                # Execute the method and expect ValueError
                with self.assertRaises(ValueError) as context:
                    await self.exchange._submit_transaction(mock_transaction)

                # Verify error message
                self.assertIn("Transaction failed after 1 attempts", str(context.exception))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.AsyncWebsocketClient")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_constants.PLACE_ORDER_MAX_RETRY", 1)
    async def test_submit_transaction_exception(self, mock_client_class):
        """Test transaction submission with exception."""
        # Setup client mock
        mock_client_instance = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client_instance

        # Setup transaction mocks
        mock_transaction = MagicMock(spec=Transaction)
        mock_filled_tx = MagicMock(spec=Transaction)
        mock_signed_tx = MagicMock(spec=Transaction)
        mock_wallet = MagicMock()

        # Mock necessary methods
        self.exchange.tx_autofill = AsyncMock(return_value=mock_filled_tx)
        self.exchange._xrpl_auth = MagicMock()
        self.exchange._xrpl_auth.get_wallet.return_value = mock_wallet

        # Patch sign and submit_and_wait methods
        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.sign", return_value=mock_signed_tx):
            with patch(
                "hummingbot.connector.exchange.xrpl.xrpl_exchange.async_submit_and_wait",
                side_effect=Exception("Network error"),
            ):
                # Execute the method and expect ValueError
                with self.assertRaises(ValueError) as context:
                    await self.exchange._submit_transaction(mock_transaction)

                # Verify error message
                self.assertIn("Transaction failed after 1 attempts", str(context.exception))
