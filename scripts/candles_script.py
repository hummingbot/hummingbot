from hummingbot.script.script_base import ScriptBase
from scripts.utils.candles import Candles


class CandlesScript(ScriptBase):

    def __init__(self):
        """
        Note we don't initialise the candles here, we wait until the first script tick
        This is so that we can be sure that the underlying framework has initialised properly
        And we can use notify etc
        """
        super().__init__()
        self.candles = None
        self.valid = False

    def on_tick(self):
        if self.candles is None:
            self.candles = Candles(self)
            self.valid = self.candles.init()
            if not self.valid:
                raise RuntimeError('Failed to initialise candles')

        if self.valid:
            new_candle = self.candles.on_tick(self.mid_price)
            if new_candle is True:
                candle = self.candles.one_minute_candles[-1]
                self.notify(candle.to_string())
