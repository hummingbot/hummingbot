from unittest.mock import MagicMock, patch

import pytest

from hummingbot.logger.logger import HummingbotLogger


@pytest.fixture()
def hb_logger():
    return HummingbotLogger("test.hb_logger_coverage")


def test_network_with_app_warning_msg_not_in_testing_mode(hb_logger):
    """Lines 97, 100: network() creates ApplicationWarning and calls add_application_warning
    when app_warning_msg is provided and NOT in testing mode."""
    mock_app = MagicMock()

    with (
        patch.object(HummingbotLogger, "is_testing_mode", return_value=False),
        patch("hummingbot.client.hummingbot_application.HummingbotApplication") as mock_hb_app_cls,
    ):
        mock_hb_app_cls.main_application.return_value = mock_app
        hb_logger.network("network log message", app_warning_msg="something is wrong")

    mock_app.add_application_warning.assert_called_once()
    warning_arg = mock_app.add_application_warning.call_args[0][0]
    # The ApplicationWarning should carry the warning message
    assert warning_arg.warning_msg == "something is wrong"


def test_network_no_app_warning_when_testing_mode(hb_logger):
    """network() must NOT create ApplicationWarning when is_testing_mode() returns True."""
    mock_app = MagicMock()

    with (
        patch.object(HummingbotLogger, "is_testing_mode", return_value=True),
        patch("hummingbot.client.hummingbot_application.HummingbotApplication") as mock_hb_app_cls,
    ):
        mock_hb_app_cls.main_application.return_value = mock_app
        hb_logger.network("network log message", app_warning_msg="should be ignored")

    mock_app.add_application_warning.assert_not_called()


def test_network_no_app_warning_when_msg_is_none(hb_logger):
    """network() with app_warning_msg=None must not touch HummingbotApplication."""
    with (
        patch.object(HummingbotLogger, "is_testing_mode", return_value=False),
        patch("hummingbot.client.hummingbot_application.HummingbotApplication") as mock_hb_app_cls,
    ):
        hb_logger.network("just a network log")

    mock_hb_app_cls.main_application.assert_not_called()


def test_is_testing_mode_returns_true_during_pytest():
    """is_testing_mode() must detect pytest in sys.argv."""
    assert HummingbotLogger.is_testing_mode() is True


def test_logger_name_for_class():
    class _Dummy:
        pass

    name = HummingbotLogger.logger_name_for_class(_Dummy)
    assert "_Dummy" in name
