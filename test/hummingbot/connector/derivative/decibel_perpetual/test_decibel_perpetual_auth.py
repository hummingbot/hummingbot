from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth


class DummyRESTRequest:
    def __init__(self, method=None, data=None, headers=None, url=""):
        self.method = method
        self.data = data
        self.headers = headers if headers is not None else {}
        self.url = url


class TestDecibelPerpetualAuth(IsolatedAsyncioWrapperTestCase):

    def test_init_strips_0x_prefix_from_public_key(self):
        auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xaabbccdd",
            main_wallet_public_key="0xmainwallet123",
            api_key="test-api-key"
        )
        assert auth._main_wallet_public_key == "mainwallet123"

    def test_init_strips_0X_prefix_from_public_key(self):
        auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xaabbccdd",
            main_wallet_public_key="0XMAINWALLET123",
            api_key="test-api-key"
        )
        assert auth._main_wallet_public_key == "MAINWALLET123"

    def test_main_wallet_address_format(self):
        auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xaabbccdd",
            main_wallet_public_key="mainwallet123",
            api_key="test-api-key"
        )
        assert auth.main_wallet_address == "0xmainwallet123"

    def test_get_subaccount_address_returns_main_wallet(self):
        auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xaabbccdd",
            main_wallet_public_key="0xmainwallet123",
            api_key="test-api-key"
        )
        result = auth.get_subaccount_address("0xpackage123")
        assert result == "0xmainwallet123"

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth.Account")
    def test_account_lazy_initialization(self, mock_account):
        mock_account_instance = MagicMock()
        mock_account_instance.address.return_value = "0xtestaddress"
        mock_account.load_key.return_value = mock_account_instance

        auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xaabbccdd",
            main_wallet_public_key="0xmainwallet123",
            api_key="test-api-key"
        )

        assert auth._api_wallet_account is None

        _ = auth.account

        mock_account.load_key.assert_called_once()

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth.Account")
    def test_address_property(self, mock_account):
        mock_account_instance = MagicMock()
        mock_account_instance.address.return_value = "0xderivedaddress"
        mock_account.load_key.return_value = mock_account_instance

        auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xaabbccdd",
            main_wallet_public_key="0xmainwallet123",
            api_key="test-api-key"
        )

        address = auth.address
        assert address == "0xderivedaddress"

    @patch("hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth.Account")
    def test_sign_transaction(self, mock_account):
        mock_private_key = MagicMock()
        mock_account_instance = MagicMock()
        mock_account_instance.private_key = mock_private_key
        mock_account.load_key.return_value = mock_account_instance

        auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xaabbccdd",
            main_wallet_public_key="0xmainwallet123",
            api_key="test-api-key"
        )

        mock_transaction = MagicMock()
        auth.sign_transaction(mock_transaction)

        mock_transaction.sign.assert_called_once_with(mock_private_key)

    def test_rest_authenticate_adds_bearer_token(self):
        auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xaabbccdd",
            main_wallet_public_key="0xmainwallet123",
            api_key="test-api-key"
        )

        request = DummyRESTRequest(method="GET", data={"key": "value"})
        result = self.run_async_with_timeout(auth.rest_authenticate(request))

        assert result is request
        assert request.headers["Authorization"] == "Bearer test-api-key"

    def test_rest_authenticate_no_token_when_api_key_empty(self):
        auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xaabbccdd",
            main_wallet_public_key="0xmainwallet123",
            api_key=""
        )

        request = DummyRESTRequest(method="GET", data={"key": "value"})
        result = self.run_async_with_timeout(auth.rest_authenticate(request))

        assert result is request
        assert "Authorization" not in request.headers
