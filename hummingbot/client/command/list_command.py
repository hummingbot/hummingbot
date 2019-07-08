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
from hummingbot.client.config.config_helpers import (
    get_strategy_config_map,
)
from hummingbot.client.settings import (
    EXCHANGES,
)
from hummingbot.core.data_type.trade import Trade

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
            if self.strategy is None:
                self._notify(("No strategy available, cannot show past trades"))
            #strategy = in_memory_config_map.get("strategy").value
            else:
                if len(self.strategy.trades) > 0:
                    df = Trade.to_pandas(self.strategy.trades)
                    df_lines = str(df).split("\n")
                    lines.extend(["", "  Past trades:"] +
                                 ["    " + line for line in df_lines])
                else:
                    lines.extend(["  No past trades."])
            self._notify("\n".join(lines))
        else:
            self.help("list")
