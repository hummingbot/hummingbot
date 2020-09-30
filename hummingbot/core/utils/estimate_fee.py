from decimal import Decimal
from hummingbot.core.event.events import TradeFee
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.client.settings import ALL_CONNECTORS


def estimate_fee(exchange: str, is_maker: bool) -> Decimal:
    override_config_name_suffix = "_maker_fee" if is_maker else "_taker_fee"
    override_config_name = exchange + override_config_name_suffix
    s_decimal_0 = Decimal("0")
    s_decimal_100 = Decimal("100")

    for connector_type, connectors in ALL_CONNECTORS.items():
        if exchange in connectors:
            try:
                path = f"hummingbot.connector.{connector_type}.{exchange}.{exchange}_utils"
                is_cex = getattr(__import__(path, fromlist=["CENTRALIZED"]), "CENTRALIZED")
                fee = getattr(__import__(path, fromlist=["DEFAULT_FEES"]), "DEFAULT_FEES")
            except Exception:
                pass
            if is_maker:
                if is_cex:
                    if fee_overrides_config_map[override_config_name].value is not None:
                        return TradeFee(percent=fee_overrides_config_map[override_config_name].value / s_decimal_100)
                    else:
                        return TradeFee(percent=Decimal(fee[0]) / s_decimal_100)
                else:
                    override_config_name += "_amount"
                    if fee_overrides_config_map[override_config_name].value is not None:
                        return TradeFee(percent=s_decimal_0, flat_fees=[("ETH", fee_overrides_config_map[override_config_name].value)])
                    else:
                        return TradeFee(percent=s_decimal_0, flat_fees=[("ETH", Decimal(fee[0]))])
            else:
                if is_cex:
                    if fee_overrides_config_map[override_config_name].value is not None:
                        return TradeFee(percent=fee_overrides_config_map[override_config_name].value / s_decimal_100)
                    else:
                        return TradeFee(percent=Decimal(fee[1]) / s_decimal_100)
                else:
                    override_config_name += "_amount"
                    if fee_overrides_config_map[override_config_name].value is not None:
                        return TradeFee(percent=s_decimal_0, flat_fees=[("ETH", fee_overrides_config_map[override_config_name].value)])
                    else:
                        return TradeFee(percent=s_decimal_0, flat_fees=[("ETH", Decimal(fee[1]))])
