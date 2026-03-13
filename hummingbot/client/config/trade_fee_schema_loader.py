from decimal import Decimal

from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeSchema


class TradeFeeSchemaLoader:
    """
    Utility class that contains the requried logic to load fee schemas applying any override the user
    might have configured.
    """

    @classmethod
    def configured_schema_for_exchange(cls, exchange_name: str) -> TradeFeeSchema:
        if exchange_name not in AllConnectorSettings.get_connector_settings():
            raise Exception(f"Invalid connector. {exchange_name} does not exist in AllConnectorSettings")
        trade_fee_schema = AllConnectorSettings.get_connector_settings()[exchange_name].trade_fee_schema
        trade_fee_schema = cls._superimpose_overrides(exchange_name, trade_fee_schema)
        return trade_fee_schema

    @classmethod
    def _superimpose_overrides(cls, exchange: str, trade_fee_schema: TradeFeeSchema):
        percent_fee_token_config = fee_overrides_config_map.get(f"{exchange}_percent_fee_token")
        trade_fee_schema.percent_fee_token = (
            percent_fee_token_config.value if percent_fee_token_config else None
        ) or trade_fee_schema.percent_fee_token

        maker_percent_fee_config = fee_overrides_config_map.get(f"{exchange}_maker_percent_fee")
        if maker_percent_fee_config and maker_percent_fee_config.value is not None:
            trade_fee_schema.maker_percent_fee_decimal = maker_percent_fee_config.value / Decimal("100")

        taker_percent_fee_config = fee_overrides_config_map.get(f"{exchange}_taker_percent_fee")
        if taker_percent_fee_config and taker_percent_fee_config.value is not None:
            trade_fee_schema.taker_percent_fee_decimal = taker_percent_fee_config.value / Decimal("100")

        buy_percent_fee_config = fee_overrides_config_map.get(f"{exchange}_buy_percent_fee_deducted_from_returns")
        if buy_percent_fee_config and buy_percent_fee_config.value is not None:
            trade_fee_schema.buy_percent_fee_deducted_from_returns = buy_percent_fee_config.value

        maker_fixed_fees_config = fee_overrides_config_map.get(f"{exchange}_maker_fixed_fees")
        trade_fee_schema.maker_fixed_fees = (
            maker_fixed_fees_config.value if maker_fixed_fees_config else None
        ) or trade_fee_schema.maker_fixed_fees
        trade_fee_schema.maker_fixed_fees = [
            TokenAmount(*maker_fixed_fee)
            for maker_fixed_fee in trade_fee_schema.maker_fixed_fees
        ]

        taker_fixed_fees_config = fee_overrides_config_map.get(f"{exchange}_taker_fixed_fees")
        trade_fee_schema.taker_fixed_fees = (
            taker_fixed_fees_config.value if taker_fixed_fees_config else None
        ) or trade_fee_schema.taker_fixed_fees
        trade_fee_schema.taker_fixed_fees = [
            TokenAmount(*taker_fixed_fee)
            for taker_fixed_fee in trade_fee_schema.taker_fixed_fees
        ]
        trade_fee_schema.validate_schema()
        return trade_fee_schema
