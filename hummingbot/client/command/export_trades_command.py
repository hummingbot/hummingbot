import pandas as pd
import threading
from os.path import join
from typing import List
from hummingbot.model.trade_fill import TradeFill
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.settings import DEFAULT_LOG_FILE_PATH
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ExportTradesCommand:
    def export_trades(self,  # type: HummingbotApplication
                      path: str = ""):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.export_trades, path)
            return

        if not path:
            fname = f"trades_{pd.Timestamp.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv"
            path = global_config_map["log_file_path"].value
            if path is None:
                path = DEFAULT_LOG_FILE_PATH
            path = join(path, fname)

        trades: List[TradeFill] = self._get_trades_from_session(self.init_time)

        if len(trades) > 0:
            try:
                df: pd.DataFrame = TradeFill.to_pandas(trades)
                df.to_csv(path, header=True)
                self._notify(f"Successfully saved trades to {path}")
            except Exception as e:
                self._notify(f"Error saving trades to {path}: {e}")
        else:
            self._notify("No past trades to export.")
