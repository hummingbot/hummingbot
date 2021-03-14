from datetime import datetime, timedelta
from binance.client import Client as BinanceClient
from hummingbot.script.script_base import ScriptBase


def round_time(ts, sec):
    """
    Round a datetime object to a multiple of a timedelta
    dt : datetime.datetime object, default now.
    dateDelta : timedelta object, we round to a multiple of this, default 1 minute.
    from:  http://stackoverflow.com/questions/3463930/how-to-round-the-minute-of-a-datetime-object-python
    """
    dt = datetime.fromtimestamp(ts)
    round_to = timedelta(seconds=sec).total_seconds()
    seconds = (dt - dt.min).seconds

    if seconds % round_to == 0 and dt.microsecond == 0:
        rounding = (seconds + round_to / 2) // round_to * round_to
    else:
        rounding = (seconds + dt.microsecond / 1000000 + round_to) // round_to * round_to

    return datetime.timestamp(dt + timedelta(0, rounding - seconds, - dt.microsecond))


class Candle:
    __slots__ = ['Time', 'Open', 'High', 'Low', 'Close']

    def __init__(self, tm, open, high, low, close):
        self.Time = tm
        self.Open = open
        self.High = high
        self.Low = low
        self.Close = close

    def to_string(self):
        dt = datetime.fromtimestamp(self.Time)
        t = dt.strftime('%H:%M:%S')
        return f'{t} - Open: {self.Open} High: {self.High} Low: {self.Low} Close: {self.Close}'


# merge two candles together, left is assumed to be earlier and right later
def merge_candles(left: Candle, right: Candle):

    tm = left.Time
    open = left.Open
    high = max(left.High, right.High)
    low = min(left.Low, right.Low)
    close = right.Close
    candle = Candle(tm, open, high, low, close)

    return candle


# main candles class
class Candles:

    # this max length should be a config var based on the range of the indicators we want to support
    MAX_CANDLES = 100

    def __init__(self, script: ScriptBase):
        self.open = 0.0
        self.high = 0.0
        self.low = 0.0
        self.close = 0.0

        self.script = script

    def init(self):

        # initialise arrays of 1, 5 and 15 minute candles
        self.one_minute_candles = []
        self.five_minute_candles = []
        self.fifteen_minute_candles = []

        # use the public API to get historical klines
        binance = BinanceClient('', '')
        symbol = self.script.pmm_market_info.trading_pair.replace('-', '')

        # make sure we have enough candle data based on indicators we want to support
        # 12 hours of 15 min candles
        min_lines = 12 * 15 * 4
        start_time = f"{min_lines} minutes ago"

        # get klines
        try:
            klines = binance.get_historical_klines(symbol = symbol, interval='1m', start_str=start_time)
        except Exception as ex:
            self.script.notify(f'Could not get candle data from exchange, please try again\n{ex}')
            return False

        # get candle data start time
        start_time = klines[0][0] / 1e3
        dt = datetime.fromtimestamp(start_time)
        str = dt.strftime("%a %b %d %H:%M:%S")
        self.script.notify(f'Populating local candles with exchange data starting at {str}')

        # set up our timestamps
        self.next_one_minute_timestamp = round_time(start_time, 60)
        self.next_five_minute_timestamp = round_time(start_time, 5 * 60)
        self.next_fifteen_minute_timestamp = round_time(start_time, 15 * 60)

        # pipe one minute candles into local arrays
        for line in klines:
            self.open = float(line[1])
            self.high = float(line[2])
            self.low = float(line[3])
            self.close = float(line[4])
            self.add_one_minute_candle(self.close)

        return True

    def add_one_minute_candle(self, price):
        # close current candle, start time is one minute ago
        candle = Candle(
            self.next_one_minute_timestamp - 60,
            self.open,
            self.high,
            self.low,
            self.close)

        # add to list
        self.one_minute_candles.append(candle)
        while len(self.one_minute_candles) > self.MAX_CANDLES:
            self.one_minute_candles.pop(0)

        # start new candle
        self.open = price
        self.high = price
        self.low = price
        self.close = price

        # create 5 min candles
        if self.next_one_minute_timestamp >= self.next_five_minute_timestamp:
            if len(self.one_minute_candles) > 5:
                candle = self.one_minute_candles[-5]
                for i in range(-4, 0):
                    candle = merge_candles(candle, self.one_minute_candles[i])

                self.five_minute_candles.append(candle)
                while len(self.five_minute_candles) > self.MAX_CANDLES:
                    self.five_minute_candles.pop(0)

            self.next_five_minute_timestamp += 5 * 60

        # create 15 min candles
        if self.next_one_minute_timestamp >= self.next_fifteen_minute_timestamp:
            if len(self.five_minute_candles) > 3:
                candle = self.five_minute_candles[-3]
                candle = merge_candles(candle, self.five_minute_candles[-2])
                candle = merge_candles(candle, self.five_minute_candles[-1])

                self.fifteen_minute_candles.append(candle)
                while len(self.fifteen_minute_candles) > self.MAX_CANDLES:
                    self.fifteen_minute_candles.pop(0)

            self.next_fifteen_minute_timestamp += 15 * 60

        # set next minute stamp
        self.next_one_minute_timestamp += 60

    def on_tick(self, price):
        ts = datetime.timestamp(datetime.now())
        if ts >= self.next_one_minute_timestamp:
            # create new one min candle
            self.add_one_minute_candle(price)
            return True
        else:
            # update prices
            self.high = max(self.high, price)
            self.low = min(self.low, price)
            self.close = price

            return False
