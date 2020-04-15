import pandas as pd
import threading
from sqlalchemy.orm import (
    Session,
    Query
)
from typing import (
    List,
    Optional,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.wallet_setup import list_wallets
from hummingbot.client.settings import (
    EXCHANGES,
    MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.client.config.security import Security
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

    def _get_trades_from_session(self,  # type: HummingbotApplication
                                 start_timestamp: int,
                                 number_of_rows: Optional[int] = None) -> List[TradeFill]:
        session: Session = self.trade_fill_db.get_shared_session()
        query: Query = (session
                        .query(TradeFill)
                        .filter(TradeFill.timestamp >= start_timestamp)
                        .order_by(TradeFill.timestamp.desc()))
        if number_of_rows is None:
            result: List[TradeFill] = query.all() or []
        else:
            result: List[TradeFill] = query.limit(number_of_rows).all() or []

        # Get the latest 100 trades in ascending timestamp order
        result.reverse()
        return result

    def list_trades(self,  # type: HummingbotApplication
                    ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.list_trades)
            return

        lines = []
        if self.strategy is None:
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
                        f"\n  Showing last {MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT} trades in the current session.")
                else:
                    df_lines = str(df).split("\n")
                lines.extend(["", "  Recent trades:"] +
                             ["    " + line for line in df_lines])
            else:
                lines.extend(["\n  No past trades in this session."])
            self._notify("\n".join(lines))

    async def list_encrypted(self,  # type: HummingbotApplication
                             ):
        if not Security.any_encryped_files():
            self._notify("There is no encrypted file in your conf folder.")
            return
        self.placeholder_mode = True
        self.app.toggle_hide_input()
        await self.check_password()
        if Security.is_decryption_done():
            for key, value in Security.all_decrypted_values().items():
                self._notify(f"{key}: {value}")
        else:
            self._notify(f"Files are being decrypted, please try again later.")
        self.app.change_prompt(prompt=">>> ")
        self.app.toggle_hide_input()
        self.placeholder_mode = False

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
        elif obj == "encrypted":
            safe_ensure_future(self.list_encrypted())
        else:
            self.help("list")
