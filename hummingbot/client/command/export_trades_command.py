import pandas as pd
from os.path import (
    join,
    dirname
)
from hummingbot.core.data_type.trade import Trade

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ExportTradesCommand:
    def export_trades(self,  # type: HummingbotApplication
                      path: str = ""):
        if not path:
            fname = f"trades_{pd.Timestamp.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv"
            path = join(dirname(__file__), f"../../../logs/{fname}")
        if self.strategy is None:
            self._notify("No strategy available, cannot export past trades.")

        else:
            if len(self.strategy.trades) > 0:
                try:
                    df: pd.DataFrame = Trade.to_pandas(self.strategy.trades)
                    df.to_csv(path, header=True)
                    self._notify(f"Successfully saved trades to {path}")
                except Exception as e:
                    self._notify(f"Error saving trades to {path}: {e}")
            else:
                self._notify("No past trades to export")
