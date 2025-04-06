"""
.. module:: momentum
   :synopsis: Momentum Indicators.

.. moduleauthor:: Dario Lopez Padial (Bukosabino)

"""
import numpy as np
import pandas as pd

from ta.utils import IndicatorMixin, _ema


class RSIIndicator(IndicatorMixin):
    """Relative Strength Index (RSI)

    Compares the magnitude of recent gains and losses over a specified time
    period to measure speed and change of price movements of a security. It is
    primarily used to attempt to identify overbought or oversold conditions in
    the trading of an asset.

    https://www.investopedia.com/terms/r/rsi.asp

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(self, close: pd.Series, window: int = 14, fillna: bool = False):
        self._close = close
        self._window = window
        self._fillna = fillna
        self._run()

    def _run(self):
        diff = self._close.diff(1)
        up_direction = diff.where(diff > 0, 0.0)
        down_direction = -diff.where(diff < 0, 0.0)
        min_periods = 0 if self._fillna else self._window
        emaup = up_direction.ewm(
            alpha=1 / self._window, min_periods=min_periods, adjust=False
        ).mean()
        emadn = down_direction.ewm(
            alpha=1 / self._window, min_periods=min_periods, adjust=False
        ).mean()
        relative_strength = emaup / emadn
        self._rsi = pd.Series(
            np.where(emadn == 0, 100, 100 - (100 / (1 + relative_strength))),
            index=self._close.index,
        )

    def rsi(self) -> pd.Series:
        """Relative Strength Index (RSI)

        Returns:
            pandas.Series: New feature generated.
        """
        rsi_series = self._check_fillna(self._rsi, value=50)
        return pd.Series(rsi_series, name="rsi")


class TSIIndicator(IndicatorMixin):
    """True strength index (TSI)

    Shows both trend direction and overbought/oversold conditions.

    https://school.stockcharts.com/doku.php?id=technical_indicators:true_strength_index

    Args:
        close(pandas.Series): dataset 'Close' column.
        window_slow(int): high period.
        window_fast(int): low period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        close: pd.Series,
        window_slow: int = 25,
        window_fast: int = 13,
        fillna: bool = False,
    ):
        self._close = close
        self._window_slow = window_slow
        self._window_fast = window_fast
        self._fillna = fillna
        self._run()

    def _run(self):
        diff_close = self._close - self._close.shift(1)
        min_periods_r = 0 if self._fillna else self._window_slow
        min_periods_s = 0 if self._fillna else self._window_fast
        smoothed = (
            diff_close.ewm(
                span=self._window_slow, min_periods=min_periods_r, adjust=False
            )
            .mean()
            .ewm(span=self._window_fast, min_periods=min_periods_s, adjust=False)
            .mean()
        )
        smoothed_abs = (
            abs(diff_close)
            .ewm(span=self._window_slow, min_periods=min_periods_r, adjust=False)
            .mean()
            .ewm(span=self._window_fast, min_periods=min_periods_s, adjust=False)
            .mean()
        )
        self._tsi = smoothed / smoothed_abs
        self._tsi *= 100

    def tsi(self) -> pd.Series:
        """True strength index (TSI)

        Returns:
            pandas.Series: New feature generated.
        """
        tsi_series = self._check_fillna(self._tsi, value=0)
        return pd.Series(tsi_series, name="tsi")


class UltimateOscillator(IndicatorMixin):
    """Ultimate Oscillator

    Larry Williams' (1976) signal, a momentum oscillator designed to capture
    momentum across three different timeframes.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ultimate_oscillator

    BP = Close - Minimum(Low or Prior Close).
    TR = Maximum(High or Prior Close)  -  Minimum(Low or Prior Close)
    Average7 = (7-period BP Sum) / (7-period TR Sum)
    Average14 = (14-period BP Sum) / (14-period TR Sum)
    Average28 = (28-period BP Sum) / (28-period TR Sum)

    UO = 100 x [(4 x Average7)+(2 x Average14)+Average28]/(4+2+1)

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window1(int): short period.
        window2(int): medium period.
        window3(int): long period.
        weight1(float): weight of short BP average for UO.
        weight2(float): weight of medium BP average for UO.
        weight3(float): weight of long BP average for UO.
        fillna(bool): if True, fill nan values with 50.
    """

    def __init__(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window1: int = 7,
        window2: int = 14,
        window3: int = 28,
        weight1: float = 4.0,
        weight2: float = 2.0,
        weight3: float = 1.0,
        fillna: bool = False,
    ):
        self._high = high
        self._low = low
        self._close = close
        self._window1 = window1
        self._window2 = window2
        self._window3 = window3
        self._weight1 = weight1
        self._weight2 = weight2
        self._weight3 = weight3
        self._fillna = fillna
        self._run()

    def _run(self):
        close_shift = self._close.shift(1)
        true_range = self._true_range(self._high, self._low, close_shift)
        buying_pressure = self._close - pd.DataFrame(
            {"low": self._low, "close": close_shift}
        ).min(axis=1, skipna=False)
        min_periods_s = 0 if self._fillna else self._window1
        min_periods_m = 0 if self._fillna else self._window2
        min_periods_len = 0 if self._fillna else self._window3
        avg_s = (
            buying_pressure.rolling(self._window1, min_periods=min_periods_s).sum()
            / true_range.rolling(self._window1, min_periods=min_periods_s).sum()
        )
        avg_m = (
            buying_pressure.rolling(self._window2, min_periods=min_periods_m).sum()
            / true_range.rolling(self._window2, min_periods=min_periods_m).sum()
        )
        avg_l = (
            buying_pressure.rolling(self._window3, min_periods=min_periods_len).sum()
            / true_range.rolling(self._window3, min_periods=min_periods_len).sum()
        )
        self._uo = (
            100.0
            * (
                (self._weight1 * avg_s)
                + (self._weight2 * avg_m)
                + (self._weight3 * avg_l)
            )
            / (self._weight1 + self._weight2 + self._weight3)
        )

    def ultimate_oscillator(self) -> pd.Series:
        """Ultimate Oscillator

        Returns:
            pandas.Series: New feature generated.
        """
        ultimate_osc = self._check_fillna(self._uo, value=50)
        return pd.Series(ultimate_osc, name="uo")


class StochasticOscillator(IndicatorMixin):
    """Stochastic Oscillator

    Developed in the late 1950s by George Lane. The stochastic
    oscillator presents the location of the closing price of a
    stock in relation to the high and low range of the price
    of a stock over a period of time, typically a 14-day period.

    https://school.stockcharts.com/doku.php?id=technical_indicators:stochastic_oscillator_fast_slow_and_full

    Args:
        close(pandas.Series): dataset 'Close' column.
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window(int): n period.
        smooth_window(int): sma period over stoch_k.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int = 14,
        smooth_window: int = 3,
        fillna: bool = False,
    ):
        self._close = close
        self._high = high
        self._low = low
        self._window = window
        self._smooth_window = smooth_window
        self._fillna = fillna
        self._run()

    def _run(self):
        min_periods = 0 if self._fillna else self._window
        smin = self._low.rolling(self._window, min_periods=min_periods).min()
        smax = self._high.rolling(self._window, min_periods=min_periods).max()
        self._stoch_k = 100 * (self._close - smin) / (smax - smin)

    def stoch(self) -> pd.Series:
        """Stochastic Oscillator

        Returns:
            pandas.Series: New feature generated.
        """
        stoch_k = self._check_fillna(self._stoch_k, value=50)
        return pd.Series(stoch_k, name="stoch_k")

    def stoch_signal(self) -> pd.Series:
        """Signal Stochastic Oscillator

        Returns:
            pandas.Series: New feature generated.
        """
        min_periods = 0 if self._fillna else self._smooth_window
        stoch_d = self._stoch_k.rolling(
            self._smooth_window, min_periods=min_periods
        ).mean()
        stoch_d = self._check_fillna(stoch_d, value=50)
        return pd.Series(stoch_d, name="stoch_k_signal")


class KAMAIndicator(IndicatorMixin):
    """Kaufman's Adaptive Moving Average (KAMA)

    Moving average designed to account for market noise or volatility. KAMA
    will closely follow prices when the price swings are relatively small and
    the noise is low. KAMA will adjust when the price swings widen and follow
    prices from a greater distance. This trend-following indicator can be
    used to identify the overall trend, time turning points and filter price
    movements.

    https://www.tradingview.com/ideas/kama/

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        pow1(int): number of periods for the fastest EMA constant.
        pow2(int): number of periods for the slowest EMA constant.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        close: pd.Series,
        window: int = 10,
        pow1: int = 2,
        pow2: int = 30,
        fillna: bool = False,
    ):
        self._close = close
        self._window = window
        self._pow1 = pow1
        self._pow2 = pow2
        self._fillna = fillna
        self._run()

    def _run(self):
        close_values = self._close.values
        vol = pd.Series(abs(self._close - np.roll(self._close, 1)))

        min_periods = 0 if self._fillna else self._window
        er_num = abs(close_values - np.roll(close_values, self._window))
        er_den = vol.rolling(self._window, min_periods=min_periods).sum()
        efficiency_ratio = np.divide(
            er_num, er_den, out=np.zeros_like(er_num), where=er_den != 0
        )

        smoothing_constant = (
            (
                efficiency_ratio * (2.0 / (self._pow1 + 1) - 2.0 / (self._pow2 + 1.0))
                + 2 / (self._pow2 + 1.0)
            )
            ** 2.0
        ).values

        self._kama = np.zeros(smoothing_constant.size)
        len_kama = len(self._kama)
        first_value = True

        for i in range(len_kama):
            if np.isnan(smoothing_constant[i]):
                self._kama[i] = np.nan
            elif first_value:
                self._kama[i] = close_values[i]
                first_value = False
            else:
                self._kama[i] = self._kama[i - 1] + smoothing_constant[i] * (
                    close_values[i] - self._kama[i - 1]
                )

    def kama(self) -> pd.Series:
        """Kaufman's Adaptive Moving Average (KAMA)

        Returns:
            pandas.Series: New feature generated.
        """
        kama_series = pd.Series(self._kama, index=self._close.index)
        kama_series = self._check_fillna(kama_series, value=self._close)
        return pd.Series(kama_series, name="kama")


class ROCIndicator(IndicatorMixin):
    """Rate of Change (ROC)

    The Rate-of-Change (ROC) indicator, which is also referred to as simply
    Momentum, is a pure momentum oscillator that measures the percent change in
    price from one period to the next. The ROC calculation compares the current
    price with the price “n” periods ago. The plot forms an oscillator that
    fluctuates above and below the zero line as the Rate-of-Change moves from
    positive to negative. As a momentum oscillator, ROC signals include
    centerline crossovers, divergences and overbought-oversold readings.
    Divergences fail to foreshadow reversals more often than not, so this
    article will forgo a detailed discussion on them. Even though centerline
    crossovers are prone to whipsaw, especially short-term, these crossovers
    can be used to identify the overall trend. Identifying overbought or
    oversold extremes comes naturally to the Rate-of-Change oscillator.

    https://school.stockcharts.com/doku.php?id=technical_indicators:rate_of_change_roc_and_momentum

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(self, close: pd.Series, window: int = 12, fillna: bool = False):
        self._close = close
        self._window = window
        self._fillna = fillna
        self._run()

    def _run(self):
        self._roc = (
            (self._close - self._close.shift(self._window))
            / self._close.shift(self._window)
        ) * 100

    def roc(self) -> pd.Series:
        """Rate of Change (ROC)

        Returns:
            pandas.Series: New feature generated.
        """
        roc_series = self._check_fillna(self._roc)
        return pd.Series(roc_series, name="roc")


class AwesomeOscillatorIndicator(IndicatorMixin):
    """Awesome Oscillator

    From: https://www.tradingview.com/wiki/Awesome_Oscillator_(AO)

    The Awesome Oscillator is an indicator used to measure market momentum. AO
    calculates the difference of a 34 Period and 5 Period Simple Moving
    Averages. The Simple Moving Averages that are used are not calculated
    using closing price but rather each bar's midpoints. AO is generally used
    to affirm trends or to anticipate possible reversals.

    From: https://www.ifcm.co.uk/ntx-indicators/awesome-oscillator

    Awesome Oscillator is a 34-period simple moving average, plotted through
    the central points of the bars (H+L)/2, and subtracted from the 5-period
    simple moving average, graphed across the central points of the bars
    (H+L)/2.

    MEDIAN PRICE = (HIGH+LOW)/2

    AO = SMA(MEDIAN PRICE, 5)-SMA(MEDIAN PRICE, 34)

    where

    SMA — Simple Moving Average.

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window1(int): short period.
        window2(int): long period.
        fillna(bool): if True, fill nan values with -50.
    """

    def __init__(
        self,
        high: pd.Series,
        low: pd.Series,
        window1: int = 5,
        window2: int = 34,
        fillna: bool = False,
    ):
        self._high = high
        self._low = low
        self._window1 = window1
        self._window2 = window2
        self._fillna = fillna
        self._run()

    def _run(self):
        median_price = 0.5 * (self._high + self._low)
        min_periods_s = 0 if self._fillna else self._window1
        min_periods_len = 0 if self._fillna else self._window2
        self._ao = (
            median_price.rolling(self._window1, min_periods=min_periods_s).mean()
            - median_price.rolling(self._window2, min_periods=min_periods_len).mean()
        )

    def awesome_oscillator(self) -> pd.Series:
        """Awesome Oscillator

        Returns:
            pandas.Series: New feature generated.
        """
        ao_series = self._check_fillna(self._ao, value=0)
        return pd.Series(ao_series, name="ao")


class WilliamsRIndicator(IndicatorMixin):
    """Williams %R

    Developed by Larry Williams, Williams %R is a momentum indicator that is
    the inverse of the Fast Stochastic Oscillator. Also referred to as %R,
    Williams %R reflects the level of the close relative to the highest high
    for the look-back period. In contrast, the Stochastic Oscillator reflects
    the level of the close relative to the lowest low. %R corrects for the
    inversion by multiplying the raw value by -100. As a result, the Fast
    Stochastic Oscillator and Williams %R produce the exact same lines, only
    the scaling is different. Williams %R oscillates from 0 to -100.

    Readings from 0 to -20 are considered overbought. Readings from -80 to -100
    are considered oversold.

    Unsurprisingly, signals derived from the Stochastic Oscillator are also
    applicable to Williams %R.

    %R = (Highest High - Close)/(Highest High - Lowest Low) * -100

    Lowest Low = lowest low for the look-back period
    Highest High = highest high for the look-back period
    %R is multiplied by -100 correct the inversion and move the decimal.

    https://school.stockcharts.com/doku.php?id=technical_indicators:williams_r

    The Williams %R oscillates from 0 to -100. When the indicator produces
    readings from 0 to -20, this indicates overbought market conditions. When
    readings are -80 to -100, it indicates oversold market conditions.

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        lbp(int): lookback period.
        fillna(bool): if True, fill nan values with -50.
    """

    def __init__(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        lbp: int = 14,
        fillna: bool = False,
    ):
        self._high = high
        self._low = low
        self._close = close
        self._lbp = lbp
        self._fillna = fillna
        self._run()

    def _run(self):
        min_periods = 0 if self._fillna else self._lbp
        highest_high = self._high.rolling(
            self._lbp, min_periods=min_periods
        ).max()  # highest high over lookback period lbp
        lowest_low = self._low.rolling(
            self._lbp, min_periods=min_periods
        ).min()  # lowest low over lookback period lbp
        self._wr = -100 * (highest_high - self._close) / (highest_high - lowest_low)

    def williams_r(self) -> pd.Series:
        """Williams %R

        Returns:
            pandas.Series: New feature generated.
        """
        wr_series = self._check_fillna(self._wr, value=-50)
        return pd.Series(wr_series, name="wr")


class StochRSIIndicator(IndicatorMixin):
    """Stochastic RSI

    The StochRSI oscillator was developed to take advantage of both momentum
    indicators in order to create a more sensitive indicator that is attuned to
    a specific security's historical performance rather than a generalized analysis
    of price change.

    https://school.stockcharts.com/doku.php?id=technical_indicators:stochrsi
    https://www.investopedia.com/terms/s/stochrsi.asp

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period
        smooth1(int): moving average of Stochastic RSI
        smooth2(int): moving average of %K
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        close: pd.Series,
        window: int = 14,
        smooth1: int = 3,
        smooth2: int = 3,
        fillna: bool = False,
    ):
        self._close = close
        self._window = window
        self._smooth1 = smooth1
        self._smooth2 = smooth2
        self._fillna = fillna
        self._run()

    def _run(self):
        self._rsi = RSIIndicator(
            close=self._close, window=self._window, fillna=self._fillna
        ).rsi()
        lowest_low_rsi = self._rsi.rolling(self._window).min()
        self._stochrsi = (self._rsi - lowest_low_rsi) / (
            self._rsi.rolling(self._window).max() - lowest_low_rsi
        )
        self._stochrsi_k = self._stochrsi.rolling(self._smooth1).mean()

    def stochrsi(self):
        """Stochastic RSI

        Returns:
            pandas.Series: New feature generated.
        """
        stochrsi_series = self._check_fillna(self._stochrsi)
        return pd.Series(stochrsi_series, name="stochrsi")

    def stochrsi_k(self):
        """Stochastic RSI %k

        Returns:
            pandas.Series: New feature generated.
        """
        stochrsi_k_series = self._check_fillna(self._stochrsi_k)
        return pd.Series(stochrsi_k_series, name="stochrsi_k")

    def stochrsi_d(self):
        """Stochastic RSI %d

        Returns:
            pandas.Series: New feature generated.
        """
        stochrsi_d_series = self._stochrsi_k.rolling(self._smooth2).mean()
        stochrsi_d_series = self._check_fillna(stochrsi_d_series)
        return pd.Series(stochrsi_d_series, name="stochrsi_d")


class PercentagePriceOscillator(IndicatorMixin):
    """
    The Percentage Price Oscillator (PPO) is a momentum oscillator that measures
    the difference between two moving averages as a percentage of the larger moving average.

    https://school.stockcharts.com/doku.php?id=technical_indicators:price_oscillators_ppo

    Args:
        close(pandas.Series): dataset 'Price' column.
        window_slow(int): n period long-term.
        window_fast(int): n period short-term.
        window_sign(int): n period to signal.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        close: pd.Series,
        window_slow: int = 26,
        window_fast: int = 12,
        window_sign: int = 9,
        fillna: bool = False,
    ):
        self._close = close
        self._window_slow = window_slow
        self._window_fast = window_fast
        self._window_sign = window_sign
        self._fillna = fillna
        self._run()

    def _run(self):
        _emafast = _ema(self._close, self._window_fast, self._fillna)
        _emaslow = _ema(self._close, self._window_slow, self._fillna)
        self._ppo = ((_emafast - _emaslow) / _emaslow) * 100
        self._ppo_signal = _ema(self._ppo, self._window_sign, self._fillna)
        self._ppo_hist = self._ppo - self._ppo_signal

    def ppo(self):
        """Percentage Price Oscillator Line

        Returns:
            pandas.Series: New feature generated.
        """
        ppo_series = self._check_fillna(self._ppo, value=0)
        return pd.Series(
            ppo_series, name=f"PPO_{self._window_fast}_{self._window_slow}"
        )

    def ppo_signal(self):
        """Percentage Price Oscillator Signal Line

        Returns:
            pandas.Series: New feature generated.
        """

        ppo_signal_series = self._check_fillna(self._ppo_signal, value=0)
        return pd.Series(
            ppo_signal_series, name=f"PPO_sign_{self._window_fast}_{self._window_slow}"
        )

    def ppo_hist(self):
        """Percentage Price Oscillator Histogram

        Returns:
            pandas.Series: New feature generated.
        """

        ppo_hist_series = self._check_fillna(self._ppo_hist, value=0)
        return pd.Series(
            ppo_hist_series, name=f"PPO_hist_{self._window_fast}_{self._window_slow}"
        )


class PercentageVolumeOscillator(IndicatorMixin):
    """
    The Percentage Volume Oscillator (PVO) is a momentum oscillator for volume.
    The PVO measures the difference between two volume-based moving averages as a
    percentage of the larger moving average.

    https://school.stockcharts.com/doku.php?id=technical_indicators:percentage_volume_oscillator_pvo

    Args:
        volume(pandas.Series): dataset 'Volume' column.
        window_slow(int): n period long-term.
        window_fast(int): n period short-term.
        window_sign(int): n period to signal.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        volume: pd.Series,
        window_slow: int = 26,
        window_fast: int = 12,
        window_sign: int = 9,
        fillna: bool = False,
    ):
        self._volume = volume
        self._window_slow = window_slow
        self._window_fast = window_fast
        self._window_sign = window_sign
        self._fillna = fillna
        self._run()

    def _run(self):
        _emafast = _ema(self._volume, self._window_fast, self._fillna)
        _emaslow = _ema(self._volume, self._window_slow, self._fillna)
        self._pvo = ((_emafast - _emaslow) / _emaslow) * 100
        self._pvo_signal = _ema(self._pvo, self._window_sign, self._fillna)
        self._pvo_hist = self._pvo - self._pvo_signal

    def pvo(self) -> pd.Series:
        """PVO Line

        Returns:
            pandas.Series: New feature generated.
        """
        pvo_series = self._check_fillna(self._pvo, value=0)
        return pd.Series(
            pvo_series, name=f"PVO_{self._window_fast}_{self._window_slow}"
        )

    def pvo_signal(self) -> pd.Series:
        """Signal Line

        Returns:
            pandas.Series: New feature generated.
        """

        pvo_signal_series = self._check_fillna(self._pvo_signal, value=0)
        return pd.Series(
            pvo_signal_series, name=f"PVO_sign_{self._window_fast}_{self._window_slow}"
        )

    def pvo_hist(self) -> pd.Series:
        """Histgram

        Returns:
            pandas.Series: New feature generated.
        """

        pvo_hist_series = self._check_fillna(self._pvo_hist, value=0)
        return pd.Series(
            pvo_hist_series, name=f"PVO_hist_{self._window_fast}_{self._window_slow}"
        )


def rsi(close, window=14, fillna=False) -> pd.Series:
    """Relative Strength Index (RSI)

    Compares the magnitude of recent gains and losses over a specified time
    period to measure speed and change of price movements of a security. It is
    primarily used to attempt to identify overbought or oversold conditions in
    the trading of an asset.

    https://www.investopedia.com/terms/r/rsi.asp

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return RSIIndicator(close=close, window=window, fillna=fillna).rsi()


def tsi(close, window_slow=25, window_fast=13, fillna=False) -> pd.Series:
    """True strength index (TSI)

    Shows both trend direction and overbought/oversold conditions.

    https://en.wikipedia.org/wiki/True_strength_index

    Args:
        close(pandas.Series): dataset 'Close' column.
        window_slow(int): high period.
        window_fast(int): low period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return TSIIndicator(
        close=close, window_slow=window_slow, window_fast=window_fast, fillna=fillna
    ).tsi()


def ultimate_oscillator(
    high,
    low,
    close,
    window1=7,
    window2=14,
    window3=28,
    weight1=4.0,
    weight2=2.0,
    weight3=1.0,
    fillna=False,
) -> pd.Series:
    """Ultimate Oscillator

    Larry Williams' (1976) signal, a momentum oscillator designed to capture
    momentum across three different timeframes.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ultimate_oscillator

    BP = Close - Minimum(Low or Prior Close).
    TR = Maximum(High or Prior Close)  -  Minimum(Low or Prior Close)
    Average7 = (7-period BP Sum) / (7-period TR Sum)
    Average14 = (14-period BP Sum) / (14-period TR Sum)
    Average28 = (28-period BP Sum) / (28-period TR Sum)

    UO = 100 x [(4 x Average7)+(2 x Average14)+Average28]/(4+2+1)

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window1(int): short period.
        window2(int): medium period.
        window3(int): long period.
        weight1(float): weight of short BP average for UO.
        weight2(float): weight of medium BP average for UO.
        weight3(float): weight of long BP average for UO.
        fillna(bool): if True, fill nan values with 50.

    Returns:
        pandas.Series: New feature generated.

    """
    return UltimateOscillator(
        high=high,
        low=low,
        close=close,
        window1=window1,
        window2=window2,
        window3=window3,
        weight1=weight1,
        weight2=weight2,
        weight3=weight3,
        fillna=fillna,
    ).ultimate_oscillator()


def stoch(high, low, close, window=14, smooth_window=3, fillna=False) -> pd.Series:
    """Stochastic Oscillator

    Developed in the late 1950s by George Lane. The stochastic
    oscillator presents the location of the closing price of a
    stock in relation to the high and low range of the price
    of a stock over a period of time, typically a 14-day period.

    https://www.investopedia.com/terms/s/stochasticoscillator.asp

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        smooth_window(int): sma period over stoch_k
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """

    return StochasticOscillator(
        high=high,
        low=low,
        close=close,
        window=window,
        smooth_window=smooth_window,
        fillna=fillna,
    ).stoch()


def stoch_signal(
    high, low, close, window=14, smooth_window=3, fillna=False
) -> pd.Series:
    """Stochastic Oscillator Signal

    Shows SMA of Stochastic Oscillator. Typically a 3 day SMA.

    https://www.investopedia.com/terms/s/stochasticoscillator.asp

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        smooth_window(int): sma period over stoch_k
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return StochasticOscillator(
        high=high,
        low=low,
        close=close,
        window=window,
        smooth_window=smooth_window,
        fillna=fillna,
    ).stoch_signal()


def williams_r(high, low, close, lbp=14, fillna=False) -> pd.Series:
    """Williams %R

    From: http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:williams_r

    Developed by Larry Williams, Williams %R is a momentum indicator that is
    the inverse of the Fast Stochastic Oscillator. Also referred to as %R,
    Williams %R reflects the level of the close relative to the highest high
    for the look-back period. In contrast, the Stochastic Oscillator reflects
    the level of the close relative to the lowest low. %R corrects for the
    inversion by multiplying the raw value by -100. As a result, the Fast
    Stochastic Oscillator and Williams %R produce the exact same lines, only
    the scaling is different. Williams %R oscillates from 0 to -100.

    Readings from 0 to -20 are considered overbought. Readings from -80 to -100
    are considered oversold.

    Unsurprisingly, signals derived from the Stochastic Oscillator are also
    applicable to Williams %R.

    %R = (Highest High - Close)/(Highest High - Lowest Low) * -100

    Lowest Low = lowest low for the look-back period
    Highest High = highest high for the look-back period
    %R is multiplied by -100 correct the inversion and move the decimal.

    From: https://www.investopedia.com/terms/w/williamsr.asp
    The Williams %R oscillates from 0 to -100. When the indicator produces
    readings from 0 to -20, this indicates overbought market conditions. When
    readings are -80 to -100, it indicates oversold market conditions.

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        lbp(int): lookback period.
        fillna(bool): if True, fill nan values with -50.

    Returns:
        pandas.Series: New feature generated.
    """
    return WilliamsRIndicator(
        high=high, low=low, close=close, lbp=lbp, fillna=fillna
    ).williams_r()


def awesome_oscillator(high, low, window1=5, window2=34, fillna=False) -> pd.Series:
    """Awesome Oscillator

    From: https://www.tradingview.com/wiki/Awesome_Oscillator_(AO)

    The Awesome Oscillator is an indicator used to measure market momentum. AO
    calculates the difference of a 34 Period and 5 Period Simple Moving
    Averages. The Simple Moving Averages that are used are not calculated
    using closing price but rather each bar's midpoints. AO is generally used
    to affirm trends or to anticipate possible reversals.

    From: https://www.ifcm.co.uk/ntx-indicators/awesome-oscillator

    Awesome Oscillator is a 34-period simple moving average, plotted through
    the central points of the bars (H+L)/2, and subtracted from the 5-period
    simple moving average, graphed across the central points of the bars
    (H+L)/2.

    MEDIAN PRICE = (HIGH+LOW)/2

    AO = SMA(MEDIAN PRICE, 5)-SMA(MEDIAN PRICE, 34)

    where

    SMA — Simple Moving Average.

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window1(int): short period.
        window2(int): long period.
        fillna(bool): if True, fill nan values with -50.

    Returns:
        pandas.Series: New feature generated.
    """
    return AwesomeOscillatorIndicator(
        high=high, low=low, window1=window1, window2=window2, fillna=fillna
    ).awesome_oscillator()


def kama(close, window=10, pow1=2, pow2=30, fillna=False) -> pd.Series:
    """Kaufman's Adaptive Moving Average (KAMA)

    Moving average designed to account for market noise or volatility. KAMA
    will closely follow prices when the price swings are relatively small and
    the noise is low. KAMA will adjust when the price swings widen and follow
    prices from a greater distance. This trend-following indicator can be
    used to identify the overall trend, time turning points and filter price
    movements.

    https://www.tradingview.com/ideas/kama/

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n number of periods for the efficiency ratio.
        pow1(int): number of periods for the fastest EMA constant.
        pow2(int): number of periods for the slowest EMA constant.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return KAMAIndicator(
        close=close, window=window, pow1=pow1, pow2=pow2, fillna=fillna
    ).kama()


def roc(close: pd.Series, window: int = 12, fillna: bool = False) -> pd.Series:
    """Rate of Change (ROC)

    The Rate-of-Change (ROC) indicator, which is also referred to as simply
    Momentum, is a pure momentum oscillator that measures the percent change in
    price from one period to the next. The ROC calculation compares the current
    price with the price “n” periods ago. The plot forms an oscillator that
    fluctuates above and below the zero line as the Rate-of-Change moves from
    positive to negative. As a momentum oscillator, ROC signals include
    centerline crossovers, divergences and overbought-oversold readings.
    Divergences fail to foreshadow reversals more often than not, so this
    article will forgo a detailed discussion on them. Even though centerline
    crossovers are prone to whipsaw, especially short-term, these crossovers
    can be used to identify the overall trend. Identifying overbought or
    oversold extremes comes naturally to the Rate-of-Change oscillator.

    https://school.stockcharts.com/doku.php?id=technical_indicators:rate_of_change_roc_and_momentum

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n periods.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.

    """
    return ROCIndicator(close=close, window=window, fillna=fillna).roc()


def stochrsi(
    close: pd.Series,
    window: int = 14,
    smooth1: int = 3,
    smooth2: int = 3,
    fillna: bool = False,
) -> pd.Series:
    """Stochastic RSI

    The StochRSI oscillator was developed to take advantage of both momentum
    indicators in order to create a more sensitive indicator that is attuned to
    a specific security's historical performance rather than a generalized analysis
    of price change.

    https://www.investopedia.com/terms/s/stochrsi.asp

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period
        smooth1(int): moving average of Stochastic RSI
        smooth2(int): moving average of %K
        fillna(bool): if True, fill nan values.
    Returns:
            pandas.Series: New feature generated.
    """
    return StochRSIIndicator(
        close=close, window=window, smooth1=smooth1, smooth2=smooth2, fillna=fillna
    ).stochrsi()


def stochrsi_k(
    close: pd.Series,
    window: int = 14,
    smooth1: int = 3,
    smooth2: int = 3,
    fillna: bool = False,
) -> pd.Series:
    """Stochastic RSI %k

    The StochRSI oscillator was developed to take advantage of both momentum
    indicators in order to create a more sensitive indicator that is attuned to
    a specific security's historical performance rather than a generalized analysis
    of price change.

    https://www.investopedia.com/terms/s/stochrsi.asp

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period
        smooth1(int): moving average of Stochastic RSI
        smooth2(int): moving average of %K
        fillna(bool): if True, fill nan values.
    Returns:
            pandas.Series: New feature generated.
    """
    return StochRSIIndicator(
        close=close, window=window, smooth1=smooth1, smooth2=smooth2, fillna=fillna
    ).stochrsi_k()


def stochrsi_d(
    close: pd.Series,
    window: int = 14,
    smooth1: int = 3,
    smooth2: int = 3,
    fillna: bool = False,
) -> pd.Series:
    """Stochastic RSI %d

    The StochRSI oscillator was developed to take advantage of both momentum
    indicators in order to create a more sensitive indicator that is attuned to
    a specific security's historical performance rather than a generalized analysis
    of price change.

    https://www.investopedia.com/terms/s/stochrsi.asp

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period
        smooth1(int): moving average of Stochastic RSI
        smooth2(int): moving average of %K
        fillna(bool): if True, fill nan values.
    Returns:
            pandas.Series: New feature generated.
    """
    return StochRSIIndicator(
        close=close, window=window, smooth1=smooth1, smooth2=smooth2, fillna=fillna
    ).stochrsi_d()


def ppo(
    close: pd.Series,
    window_slow: int = 26,
    window_fast: int = 12,
    window_sign: int = 9,
    fillna: bool = False,
) -> pd.Series:
    """
    The Percentage Price Oscillator (PPO) is a momentum oscillator that measures
    the difference between two moving averages as a percentage of the larger moving average.

    https://school.stockcharts.com/doku.php?id=technical_indicators:price_oscillators_ppo

    Args:
        close(pandas.Series): dataset 'Price' column.
        window_slow(int): n period long-term.
        window_fast(int): n period short-term.
        window_sign(int): n period to signal.
        fillna(bool): if True, fill nan values.
    Returns:
        pandas.Series: New feature generated.
    """
    return PercentagePriceOscillator(
        close=close,
        window_slow=window_slow,
        window_fast=window_fast,
        window_sign=window_sign,
        fillna=fillna,
    ).ppo()


def ppo_signal(
    close: pd.Series, window_slow=26, window_fast=12, window_sign=9, fillna=False
) -> pd.Series:
    """
    The Percentage Price Oscillator (PPO) is a momentum oscillator that measures
    the difference between two moving averages as a percentage of the larger moving average.

    https://school.stockcharts.com/doku.php?id=technical_indicators:price_oscillators_ppo

    Args:
        close(pandas.Series): dataset 'Price' column.
        window_slow(int): n period long-term.
        window_fast(int): n period short-term.
        window_sign(int): n period to signal.
        fillna(bool): if True, fill nan values.
    Returns:
        pandas.Series: New feature generated.
    """
    return PercentagePriceOscillator(
        close=close,
        window_slow=window_slow,
        window_fast=window_fast,
        window_sign=window_sign,
        fillna=fillna,
    ).ppo_signal()


def ppo_hist(
    close: pd.Series,
    window_slow: int = 26,
    window_fast: int = 12,
    window_sign: int = 9,
    fillna: bool = False,
) -> pd.Series:
    """
    The Percentage Price Oscillator (PPO) is a momentum oscillator that measures
    the difference between two moving averages as a percentage of the larger moving average.

    https://school.stockcharts.com/doku.php?id=technical_indicators:price_oscillators_ppo

    Args:
        close(pandas.Series): dataset 'Price' column.
        window_slow(int): n period long-term.
        window_fast(int): n period short-term.
        window_sign(int): n period to signal.
        fillna(bool): if True, fill nan values.
    Returns:
        pandas.Series: New feature generated.
    """
    return PercentagePriceOscillator(
        close=close,
        window_slow=window_slow,
        window_fast=window_fast,
        window_sign=window_sign,
        fillna=fillna,
    ).ppo_hist()


def pvo(
    volume: pd.Series,
    window_slow: int = 26,
    window_fast: int = 12,
    window_sign: int = 9,
    fillna: bool = False,
) -> pd.Series:
    """
    The Percentage Volume Oscillator (PVO) is a momentum oscillator for volume.
    The PVO measures the difference between two volume-based moving averages as a
    percentage of the larger moving average.

    https://school.stockcharts.com/doku.php?id=technical_indicators:percentage_volume_oscillator_pvo

    Args:
        volume(pandas.Series): dataset 'Volume' column.
        window_slow(int): n period long-term.
        window_fast(int): n period short-term.
        window_sign(int): n period to signal.
        fillna(bool): if True, fill nan values.
    Returns:
        pandas.Series: New feature generated.
    """

    indicator = PercentageVolumeOscillator(
        volume=volume,
        window_slow=window_slow,
        window_fast=window_fast,
        window_sign=window_sign,
        fillna=fillna,
    )
    return indicator.pvo()


def pvo_signal(
    volume: pd.Series,
    window_slow: int = 26,
    window_fast: int = 12,
    window_sign: int = 9,
    fillna: bool = False,
) -> pd.Series:
    """
    The Percentage Volume Oscillator (PVO) is a momentum oscillator for volume.
    The PVO measures the difference between two volume-based moving averages as a
    percentage of the larger moving average.

    https://school.stockcharts.com/doku.php?id=technical_indicators:percentage_volume_oscillator_pvo

    Args:
        volume(pandas.Series): dataset 'Volume' column.
        window_slow(int): n period long-term.
        window_fast(int): n period short-term.
        window_sign(int): n period to signal.
        fillna(bool): if True, fill nan values.
    Returns:
        pandas.Series: New feature generated.
    """

    indicator = PercentageVolumeOscillator(
        volume=volume,
        window_slow=window_slow,
        window_fast=window_fast,
        window_sign=window_sign,
        fillna=fillna,
    )
    return indicator.pvo_signal()


def pvo_hist(
    volume: pd.Series,
    window_slow: int = 26,
    window_fast: int = 12,
    window_sign: int = 9,
    fillna: bool = False,
) -> pd.Series:
    """
    The Percentage Volume Oscillator (PVO) is a momentum oscillator for volume.
    The PVO measures the difference between two volume-based moving averages as a
    percentage of the larger moving average.

    https://school.stockcharts.com/doku.php?id=technical_indicators:percentage_volume_oscillator_pvo

    Args:
        volume(pandas.Series): dataset 'Volume' column.
        window_slow(int): n period long-term.
        window_fast(int): n period short-term.
        window_sign(int): n period to signal.
        fillna(bool): if True, fill nan values.
    Returns:
        pandas.Series: New feature generated.
    """

    indicator = PercentageVolumeOscillator(
        volume=volume,
        window_slow=window_slow,
        window_fast=window_fast,
        window_sign=window_sign,
        fillna=fillna,
    )
    return indicator.pvo_hist()
