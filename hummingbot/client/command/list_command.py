import pandas as pd
from typing import (
    List,
    Any,
)

from hummingbot.core.utils.wallet_setup import (
    list_wallets,
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.in_memory_config_map import in_memory_config_map
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.market.markets_recorder import MarketsRecorder
from hummingbot.client.config.config_helpers import (
    get_strategy_config_map,
)
from hummingbot.client.settings import (
    EXCHANGES,
    MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT
)
from hummingbot.model.trade_fill import TradeFill

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ListCommand:
    def list(self,  # type: HummingbotApplication
             obj: str):
        if obj == "wallets":
            wallets = list_wallets()
            if len(wallets) == 0:
                self._notify('Wallet not available. Please configure your wallet (Enter "config wallet")')
            else:
                self._notify('\n'.join(wallets))

        elif obj == "exchanges":
            if len(EXCHANGES) == 0:
                self._notify("No exchanges available")
            else:
                self._notify('\n'.join(EXCHANGES))

        elif obj == "configs":
            columns: List[str] = ["Key", "Current Value"]

            global_cvs: List[ConfigVar] = list(in_memory_config_map.values()) + list(global_config_map.values())
            global_data: List[List[str, Any]] = [
                [cv.key, len(str(cv.value)) * "*" if cv.is_secure else str(cv.value)]
                for cv in global_cvs]
            global_df: pd.DataFrame = pd.DataFrame(data=global_data, columns=columns)
            self._notify("\nglobal configs:")
            self._notify(str(global_df))

            strategy = in_memory_config_map.get("strategy").value
            if strategy:
                strategy_cvs: List[ConfigVar] = get_strategy_config_map(strategy).values()
                strategy_data: List[List[str, Any]] = [
                    [cv.key, len(str(cv.value)) * "*" if cv.is_secure else str(cv.value)]
                    for cv in strategy_cvs]
                strategy_df: pd.DataFrame = pd.DataFrame(data=strategy_data, columns=columns)

                self._notify(f"\n{strategy} strategy configs:")
                self._notify(str(strategy_df))

            self._notify("\n")

        elif obj == "trades":
            lines = []
            # To access the trades from Markets Recorder you need the file path and strategy name
            if in_memory_config_map.get("strategy_file_path").value is None or \
                    in_memory_config_map.get("strategy").value is None:
                self._notify("Please Configure the bot first")
            else:
                markets_recorder = MarketsRecorder(
                    self.trade_fill_db,
                    list(self.markets.values()),
                    in_memory_config_map.get("strategy_file_path").value,
                    in_memory_config_map.get("strategy").value
                )
                config_file = in_memory_config_map.get("strategy_file_path").value

                # Query for maximum number of trades to display + 1
                queried_trades = markets_recorder.get_trades_for_config(config_file,
                                                                        MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT + 1)
                df = TradeFill.to_pandas(queried_trades)
                if len(df) > 0:
                    #Check if number of trades exceed maximum number of trades to display
                    if len(df) > MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT:
                        df_lines = str(df[:MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT]).split("\n")
                        self._notify(f"Number of Trades exceeds the maximum display limit of :{MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT} trades. "
                                     f"Please change limit in client settings to display the required number of trades ")
                        lines.extend(["", "  Past trades:"] +
                                     ["    " + line for line in df_lines])
                    else:
                        df_lines = str(df).split("\n")
                        lines.extend(["", "  Past trades:"] +
                                     ["    " + line for line in df_lines])
                else:
                    lines.extend(["  No past trades."])
                self._notify("\n".join(lines))

            self.help("list")
