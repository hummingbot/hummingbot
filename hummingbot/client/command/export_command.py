import os
from typing import TYPE_CHECKING, List, Optional

import pandas as pd
from sqlalchemy.orm import Query, Session

from hummingbot.client.config.security import Security
from hummingbot.client.settings import DEFAULT_LOG_FILE_PATH
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.model.trade_fill import TradeFill

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class ExportCommand:
    def export(self,  # type: HummingbotApplication
               option):
        if option is None or option not in ("keys", "trades"):
            self.notify("Invalid export option.")
            return
        elif option == "keys":
            safe_ensure_future(self.export_keys())
        elif option == "trades":
            safe_ensure_future(self.export_trades())

    async def export_keys(self,  # type: HummingbotApplication
                          ):
        await Security.wait_til_decryption_done()
        if not Security.any_secure_configs():
            self.notify("There are no keys to export.")
            return
        self.placeholder_mode = True
        self.app.hide_input = True
        if await self.check_password():
            self.notify("\nWarning: Never disclose API keys or private keys. Anyone with your keys can steal any "
                        "assets held in your account.")
            self.notify("\nAPI keys:")
            for key, cm in Security.all_decrypted_values().items():
                for el in cm.traverse(secure=False):
                    if el.client_field_data is not None and el.client_field_data.is_secure:
                        self.notify(f"{el.attr}: {el.printable_value}")
        self.app.change_prompt(prompt=">>> ")
        self.app.hide_input = False
        self.placeholder_mode = False

    async def prompt_new_export_file_name(self,  # type: HummingbotApplication
                                          path):
        input = await self.app.prompt(prompt="Enter a new csv file name >>> ")
        if input is None or input == "":
            self.notify("Value is required.")
            return await self.prompt_new_export_file_name(path)
        if input == " ":
            return None
        if "." not in input:
            input = input + ".csv"
        file_path = os.path.join(path, input)
        if os.path.exists(file_path):
            self.notify(f"{input} file already exists, please enter a new name.")
            return await self.prompt_new_export_file_name(path)
        else:
            return input

    async def export_trades(self,  # type: HummingbotApplication
                            ):
        with self.trade_fill_db.get_new_session() as session:
            trades: List[TradeFill] = self._get_trades_from_session(
                int(self.init_time * 1e3),
                session=session)
            if len(trades) == 0:
                self.notify("No past trades to export.")
                return
            self.placeholder_mode = True
            self.app.hide_input = True
            path = self.client_config_map.log_file_path
            if path is None:
                path = str(DEFAULT_LOG_FILE_PATH)
            file_name = await self.prompt_new_export_file_name(path)
            if file_name is None:
                return
            file_path = os.path.join(path, file_name)
            try:
                df: pd.DataFrame = TradeFill.to_pandas(trades)
                df.to_csv(file_path, header=True)
                self.notify(f"Successfully exported trades to {file_path}")
            except Exception as e:
                self.notify(f"Error exporting trades to {path}: {e}")
            self.app.change_prompt(prompt=">>> ")
            self.placeholder_mode = False
            self.app.hide_input = False

    def _get_trades_from_session(self,  # type: HummingbotApplication
                                 start_timestamp: int,
                                 session: Session,
                                 number_of_rows: Optional[int] = None,
                                 config_file_path: str = None) -> List[TradeFill]:

        filters = [TradeFill.timestamp >= start_timestamp]
        if config_file_path is not None:
            filters.append(TradeFill.config_file_path.like(f"%{config_file_path}%"))
        query: Query = (session
                        .query(TradeFill)
                        .filter(*filters)
                        .order_by(TradeFill.timestamp.desc()))
        if number_of_rows is None:
            result: List[TradeFill] = query.all() or []
        else:
            result: List[TradeFill] = query.limit(number_of_rows).all() or []

        # Get the latest 100 trades in ascending timestamp order
        result.reverse()
        return result
