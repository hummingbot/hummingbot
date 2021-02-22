from hummingbot.script.script_base import ScriptBase
from scripts.utils.candles import Candles
from datetime import datetime


class CandlesScript(ScriptBase):

    def __init__(self):
        """
        Note we don't initialise the candles here, we wait until the first script tick
        This is so that we can be sure that the underlying framework has initialised properly
        And we can use notify etc
        """
        super().__init__()
        self.candles = None

    def on_tick(self):
        if self.candles is None:
            self.candles = Candles(self)
            if not self.candles.init():
                raise RuntimeError('Failed to initialise candles')

        new_candle = self.candles.on_tick(self.mid_price)
        if new_candle is True:
            candle = self.candles.one_minute_candles[-1]
            dt = datetime.fromtimestamp(candle.Time)
            t = dt.strftime('%H:%M:%S')
            self.notify(f'{t} - Open: {candle.Open} High: {candle.High} Low: {candle.Low} Close: {candle.Close}')
