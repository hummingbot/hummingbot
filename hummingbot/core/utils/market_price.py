import statistics
from decimal import Decimal
from typing import Optional

import numpy as np

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


def calculate_median_after_removing_outliers(prices):
    # Convert the prices to float
    prices = [float(price) for price in prices]

    # Calculate Q1, Q3, and IQR
    Q1 = np.percentile(prices, 25)
    Q3 = np.percentile(prices, 75)
    IQR = Q3 - Q1

    # Define the bounds for outliers
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR

    # Remove outliers
    prices_without_outliers = [price for price in prices if lower_bound <= price <= upper_bound]

    # Calculate the median
    median_price = statistics.median(prices_without_outliers)

    return median_price
