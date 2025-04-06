from decimal import Decimal
from typing import Optional

from hummingbot.client.settings import AllConnectorSettings, ConnectorType


async def get_last_price(exchange: str, trading_pair: str) -> Optional[Decimal]:
    if exchange in AllConnectorSettings.get_connector_settings():
        conn_setting = AllConnectorSettings.get_connector_settings()[exchange]
        if AllConnectorSettings.get_connector_settings()[exchange].type in [ConnectorType.Exchange,
                                                                            ConnectorType.Derivative]:
            try:
                connector = conn_setting.non_trading_connector_instance_with_default_configuration()
                last_prices = await connector.get_last_traded_prices(trading_pairs=[trading_pair])
                if last_prices:
                    return Decimal(str(last_prices[trading_pair]))
            except ModuleNotFoundError:
                pass
