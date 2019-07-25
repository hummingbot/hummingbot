import pandas as pd
from sqlalchemy.orm import (
    Session,
    Query
)
from typing import (
    List,
    Any,
    Optional,
)

from hummingbot.core.utils.wallet_setup import list_wallets
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.in_memory_config_map import in_memory_config_map
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_helpers import get_strategy_config_map
from hummingbot.client.settings import (
    EXCHANGES,
    MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT
)
from hummingbot.model.trade_fill import TradeFill

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ListCommand:

    def list_wallet(self,  # type: HummingbotApplication
                    ):
        wallets = list_wallets()
        if len(wallets) == 0:
            self._notify('Wallet not available. Please configure your wallet (Enter "config wallet")')
        else:
            self._notify('\n'.join(wallets))

    def list_exchanges(self,  # type: HummingbotApplication
                       ):
        if len(EXCHANGES) == 0:
            self._notify("No exchanges available")
        else:
            self._notify('\n'.join(EXCHANGES))

    def list_configs(self,  # type: HummingbotApplication
                     ):
        columns: List[str] = ["Key", "Current Value"]

        global_cvs: List[ConfigVar] = list(in_memory_config_map.values()) + list(global_config_map.values())
        global_data: List[List[Any]] = [
            [cv.key, len(str(cv.value)) * "*" if cv.is_secure else str(cv.value)]
            for cv in global_cvs]
        global_df: pd.DataFrame = pd.DataFrame(data=global_data, columns=columns)
        self._notify("\nglobal configs:")
        self._notify(str(global_df))

        strategy = in_memory_config_map.get("strategy").value
        if strategy:
            strategy_cvs: List[ConfigVar] = get_strategy_config_map(strategy).values()
            strategy_data: List[List[Any]] = [
                [cv.key, len(str(cv.value)) * "*" if cv.is_secure else str(cv.value)]
                for cv in strategy_cvs]
            strategy_df: pd.DataFrame = pd.DataFrame(data=strategy_data, columns=columns)

            self._notify(f"\n{strategy} strategy configs:")
            self._notify(str(strategy_df))

        self._notify("\n")

    def _get_trades_from_session(self,  # type: HummingbotApplication
                                 start_timestamp: int,
                                 number_of_rows: Optional[int] = None) -> List[TradeFill]:
        session: Session = self.trade_fill_db.get_shared_session()
        query: Query = (session
                        .query(TradeFill)
                        .filter(TradeFill.timestamp >= start_timestamp)
                        .order_by(TradeFill.timestamp.desc()))
        if number_of_rows is None:
            result: Optional[TradeFill] = query.all()
        else:
            result: Optional[TradeFill] = query.limit(number_of_rows).all()
        return result or []

    def list_trades(self,  # type: HummingbotApplication
                    ):
        lines = []
        # To access the trades from Markets Recorder you need the file path and strategy name
        if in_memory_config_map.get("strategy_file_path").value is None or \
                in_memory_config_map.get("strategy").value is None:
            self._notify("Bot not started. No past trades.")
        else:
            # Query for maximum number of trades to display + 1
            queried_trades: List[TradeFill] = self._get_trades_from_session(self.init_time,
                                                                            MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT + 1)
            df: pd.DataFrame = TradeFill.to_pandas(queried_trades)

            if len(df) > 0:
                # Check if number of trades exceed maximum number of trades to display
                if len(df) > MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT:
                    df_lines = str(df[:MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT]).split("\n")
                    self._notify(
                        f"Number of Trades exceeds the maximum display limit "
                        f"of:{MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT} trades. "
                        f"Please change limit in client settings to display the required number of trades ")
                else:
                    df_lines = str(df).split("\n")
                lines.extend(["", "  Past trades:"] +
                             ["    " + line for line in df_lines])
            else:
                lines.extend(["  No past trades in this session."])
            self._notify("\n".join(lines))

    def list(self,  # type: HummingbotApplication
             obj: str):
        """ Router function for list command """
        if obj == "wallets":
            self.list_wallet()
        elif obj == "exchanges":
            self.list_exchanges()
        elif obj == "configs":
            self.list_configs()
        elif obj == "trades":
            self.list_trades()
        else:
            self.help("list")

