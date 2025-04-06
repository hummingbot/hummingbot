"""
.. module:: trend
   :synopsis: Trend Indicators.

.. moduleauthor:: Dario Lopez Padial (Bukosabino)

"""
import numpy as np
import pandas as pd

from ta.utils import IndicatorMixin, _ema, _get_min_max, _sma


class AroonIndicator(IndicatorMixin):
    """Aroon Indicator

    Identify when trends are likely to change direction.

    Aroon Up = ((N - Days Since N-day High) / N) x 100
    Aroon Down = ((N - Days Since N-day Low) / N) x 100
    Aroon Indicator = Aroon Up - Aroon Down

    https://www.investopedia.com/terms/a/aroon.asp

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self, high: pd.Series, low: pd.Series, window: int = 25, fillna: bool = False
    ):
        self._high = high
        self._low = low
        self._window = window
        self._fillna = fillna
        self._run()

    def _run(self):
        # Note: window-size + current time point = self._window + 1
        min_periods = 1 if self._fillna else self._window + 1

        rolling_high = self._high.rolling(self._window + 1, min_periods=min_periods)
        self._aroon_up = rolling_high.apply(
            lambda x: float(np.argmax(x)) / self._window * 100, raw=True
        )

        rolling_low = self._low.rolling(self._window + 1, min_periods=min_periods)
        self._aroon_down = rolling_low.apply(
            lambda x: float(np.argmin(x)) / self._window * 100, raw=True
        )

    def aroon_up(self) -> pd.Series:
        """Aroon Up Channel

        Returns:
            pandas.Series: New feature generated.
        """
        aroon_up_series = self._check_fillna(self._aroon_up, value=0)
        return pd.Series(aroon_up_series, name=f"aroon_up_{self._window}")

    def aroon_down(self) -> pd.Series:
        """Aroon Down Channel

        Returns:
            pandas.Series: New feature generated.
        """
        aroon_down_series = self._check_fillna(self._aroon_down, value=0)
        return pd.Series(aroon_down_series, name=f"aroon_down_{self._window}")

    def aroon_indicator(self) -> pd.Series:
        """Aroon Indicator

        Returns:
            pandas.Series: New feature generated.
        """
        aroon_diff = self._aroon_up - self._aroon_down
        aroon_diff = self._check_fillna(aroon_diff, value=0)
        return pd.Series(aroon_diff, name=f"aroon_ind_{self._window}")


class MACD(IndicatorMixin):
    """Moving Average Convergence Divergence (MACD)

    Is a trend-following momentum indicator that shows the relationship between
    two moving averages of prices.

    https://school.stockcharts.com/doku.php?id=technical_indicators:moving_average_convergence_divergence_macd

    Args:
        close(pandas.Series): dataset 'Close' column.
        window_fast(int): n period short-term.
        window_slow(int): n period long-term.
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
        self._emafast = _ema(self._close, self._window_fast, self._fillna)
        self._emaslow = _ema(self._close, self._window_slow, self._fillna)
        self._macd = self._emafast - self._emaslow
        self._macd_signal = _ema(self._macd, self._window_sign, self._fillna)
        self._macd_diff = self._macd - self._macd_signal

    def macd(self) -> pd.Series:
        """MACD Line

        Returns:
            pandas.Series: New feature generated.
        """
        macd_series = self._check_fillna(self._macd, value=0)
        return pd.Series(
            macd_series, name=f"MACD_{self._window_fast}_{self._window_slow}"
        )

    def macd_signal(self) -> pd.Series:
        """Signal Line

        Returns:
            pandas.Series: New feature generated.
        """

        macd_signal_series = self._check_fillna(self._macd_signal, value=0)
        return pd.Series(
            macd_signal_series,
            name=f"MACD_sign_{self._window_fast}_{self._window_slow}",
        )

    def macd_diff(self) -> pd.Series:
        """MACD Histogram

        Returns:
            pandas.Series: New feature generated.
        """
        macd_diff_series = self._check_fillna(self._macd_diff, value=0)
        return pd.Series(
            macd_diff_series, name=f"MACD_diff_{self._window_fast}_{self._window_slow}"
        )


class EMAIndicator(IndicatorMixin):
    """EMA - Exponential Moving Average

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(self, close: pd.Series, window: int = 14, fillna: bool = False):
        self._close = close
        self._window = window
        self._fillna = fillna

    def ema_indicator(self) -> pd.Series:
        """Exponential Moving Average (EMA)

        Returns:
            pandas.Series: New feature generated.
        """
        ema_ = _ema(self._close, self._window, self._fillna)
        return pd.Series(ema_, name=f"ema_{self._window}")


class SMAIndicator(IndicatorMixin):
    """SMA - Simple Moving Average

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(self, close: pd.Series, window: int, fillna: bool = False):
        self._close = close
        self._window = window
        self._fillna = fillna

    def sma_indicator(self) -> pd.Series:
        """Simple Moving Average (SMA)

        Returns:
            pandas.Series: New feature generated.
        """
        sma_ = _sma(self._close, self._window, self._fillna)
        return pd.Series(sma_, name=f"sma_{self._window}")


class WMAIndicator(IndicatorMixin):
    """WMA - Weighted Moving Average

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(self, close: pd.Series, window: int = 9, fillna: bool = False):
        self._close = close
        self._window = window
        self._fillna = fillna
        self._run()

    def _run(self):
        _weight = pd.Series(
            [
                i * 2 / (self._window * (self._window + 1))
                for i in range(1, self._window + 1)
            ]
        )

        def weighted_average(weight):
            def _weighted_average(x):
                return (weight * x).sum()

            return _weighted_average

        self._wma = self._close.rolling(self._window).apply(
            weighted_average(_weight), raw=True
        )

    def wma(self) -> pd.Series:
        """Weighted Moving Average (WMA)

        Returns:
            pandas.Series: New feature generated.
        """
        wma = self._check_fillna(self._wma, value=0)
        return pd.Series(wma, name=f"wma_{self._window}")


class TRIXIndicator(IndicatorMixin):
    """Trix (TRIX)

    Shows the percent rate of change of a triple exponentially smoothed moving
    average.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:trix

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(self, close: pd.Series, window: int = 15, fillna: bool = False):
        self._close = close
        self._window = window
        self._fillna = fillna
        self._run()

    def _run(self):
        ema1 = _ema(self._close, self._window, self._fillna)
        ema2 = _ema(ema1, self._window, self._fillna)
        ema3 = _ema(ema2, self._window, self._fillna)
        self._trix = (ema3 - ema3.shift(1, fill_value=ema3.mean())) / ema3.shift(
            1, fill_value=ema3.mean()
        )
        self._trix *= 100

    def trix(self) -> pd.Series:
        """Trix (TRIX)

        Returns:
            pandas.Series: New feature generated.
        """
        trix_series = self._check_fillna(self._trix, value=0)
        return pd.Series(trix_series, name=f"trix_{self._window}")


class MassIndex(IndicatorMixin):
    """Mass Index (MI)

    It uses the high-low range to identify trend reversals based on range
    expansions. It identifies range bulges that can foreshadow a reversal of
    the current trend.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:mass_index

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window_fast(int): fast period value.
        window_slow(int): slow period value.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        high: pd.Series,
        low: pd.Series,
        window_fast: int = 9,
        window_slow: int = 25,
        fillna: bool = False,
    ):
        self._high = high
        self._low = low
        self._window_fast = window_fast
        self._window_slow = window_slow
        self._fillna = fillna
        self._run()

    def _run(self):
        min_periods = 0 if self._fillna else self._window_slow
        amplitude = self._high - self._low
        ema1 = _ema(amplitude, self._window_fast, self._fillna)
        ema2 = _ema(ema1, self._window_fast, self._fillna)
        mass = ema1 / ema2
        self._mass = mass.rolling(self._window_slow, min_periods=min_periods).sum()

    def mass_index(self) -> pd.Series:
        """Mass Index (MI)

        Returns:
            pandas.Series: New feature generated.
        """
        mass = self._check_fillna(self._mass, value=0)
        return pd.Series(
            mass, name=f"mass_index_{self._window_fast}_{self._window_slow}"
        )


class IchimokuIndicator(IndicatorMixin):
    """Ichimoku Kinkō Hyō (Ichimoku)

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ichimoku_cloud

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window1(int): n1 low period.
        window2(int): n2 medium period.
        window3(int): n3 high period.
        visual(bool): if True, shift n2 values.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        high: pd.Series,
        low: pd.Series,
        window1: int = 9,
        window2: int = 26,
        window3: int = 52,
        visual: bool = False,
        fillna: bool = False,
    ):
        self._high = high
        self._low = low
        self._window1 = window1
        self._window2 = window2
        self._window3 = window3
        self._visual = visual
        self._fillna = fillna
        self._run()

    def _run(self):
        min_periods_n1 = 0 if self._fillna else self._window1
        min_periods_n2 = 0 if self._fillna else self._window2
        self._conv = 0.5 * (
            self._high.rolling(self._window1, min_periods=min_periods_n1).max()
            + self._low.rolling(self._window1, min_periods=min_periods_n1).min()
        )
        self._base = 0.5 * (
            self._high.rolling(self._window2, min_periods=min_periods_n2).max()
            + self._low.rolling(self._window2, min_periods=min_periods_n2).min()
        )

    def ichimoku_conversion_line(self) -> pd.Series:
        """Tenkan-sen (Conversion Line)

        Returns:
            pandas.Series: New feature generated.
        """
        conversion = self._check_fillna(self._conv, value=-1)
        return pd.Series(
            conversion, name=f"ichimoku_conv_{self._window1}_{self._window2}"
        )

    def ichimoku_base_line(self) -> pd.Series:
        """Kijun-sen (Base Line)

        Returns:
            pandas.Series: New feature generated.
        """
        base = self._check_fillna(self._base, value=-1)
        return pd.Series(base, name=f"ichimoku_base_{self._window1}_{self._window2}")

    def ichimoku_a(self) -> pd.Series:
        """Senkou Span A (Leading Span A)

        Returns:
            pandas.Series: New feature generated.
        """
        spana = 0.5 * (self._conv + self._base)
        spana = (
            spana.shift(self._window2, fill_value=spana.mean())
            if self._visual
            else spana
        )
        spana = self._check_fillna(spana, value=-1)
        return pd.Series(spana, name=f"ichimoku_a_{self._window1}_{self._window2}")

    def ichimoku_b(self) -> pd.Series:
        """Senkou Span B (Leading Span B)

        Returns:
            pandas.Series: New feature generated.
        """
        spanb = 0.5 * (
            self._high.rolling(self._window3, min_periods=0).max()
            + self._low.rolling(self._window3, min_periods=0).min()
        )
        spanb = (
            spanb.shift(self._window2, fill_value=spanb.mean())
            if self._visual
            else spanb
        )
        spanb = self._check_fillna(spanb, value=-1)
        return pd.Series(spanb, name=f"ichimoku_b_{self._window1}_{self._window2}")


class KSTIndicator(IndicatorMixin):
    """KST Oscillator (KST Signal)

    It is useful to identify major stock market cycle junctures because its
    formula is weighed to be more greatly influenced by the longer and more
    dominant time spans, in order to better reflect the primary swings of stock
    market cycle.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:know_sure_thing_kst

    Args:
        close(pandas.Series): dataset 'Close' column.
        roc1(int): roc1 period.
        roc2(int): roc2 period.
        roc3(int): roc3 period.
        roc4(int): roc4 period.
        window1(int): n1 smoothed period.
        window2(int): n2 smoothed period.
        window3(int): n3 smoothed period.
        window4(int): n4 smoothed period.
        nsig(int): n period to signal.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        close: pd.Series,
        roc1: int = 10,
        roc2: int = 15,
        roc3: int = 20,
        roc4: int = 30,
        window1: int = 10,
        window2: int = 10,
        window3: int = 10,
        window4: int = 15,
        nsig: int = 9,
        fillna: bool = False,
    ):
        self._close = close
        self._r1 = roc1
        self._r2 = roc2
        self._r3 = roc3
        self._r4 = roc4
        self._window1 = window1
        self._window2 = window2
        self._window3 = window3
        self._window4 = window4
        self._nsig = nsig
        self._fillna = fillna
        self._run()

    def _run(self):
        min_periods_n1 = 0 if self._fillna else self._window1
        min_periods_n2 = 0 if self._fillna else self._window2
        min_periods_n3 = 0 if self._fillna else self._window3
        min_periods_n4 = 0 if self._fillna else self._window4
        rocma1 = (
            (
                (
                    self._close
                    - self._close.shift(self._r1, fill_value=self._close.mean())
                )
                / self._close.shift(self._r1, fill_value=self._close.mean())
            )
            .rolling(self._window1, min_periods=min_periods_n1)
            .mean()
        )
        rocma2 = (
            (
                (
                    self._close
                    - self._close.shift(self._r2, fill_value=self._close.mean())
                )
                / self._close.shift(self._r2, fill_value=self._close.mean())
            )
            .rolling(self._window2, min_periods=min_periods_n2)
            .mean()
        )
        rocma3 = (
            (
                (
                    self._close
                    - self._close.shift(self._r3, fill_value=self._close.mean())
                )
                / self._close.shift(self._r3, fill_value=self._close.mean())
            )
            .rolling(self._window3, min_periods=min_periods_n3)
            .mean()
        )
        rocma4 = (
            (
                (
                    self._close
                    - self._close.shift(self._r4, fill_value=self._close.mean())
                )
                / self._close.shift(self._r4, fill_value=self._close.mean())
            )
            .rolling(self._window4, min_periods=min_periods_n4)
            .mean()
        )
        self._kst = 100 * (rocma1 + 2 * rocma2 + 3 * rocma3 + 4 * rocma4)
        self._kst_sig = self._kst.rolling(self._nsig, min_periods=0).mean()

    def kst(self) -> pd.Series:
        """Know Sure Thing (KST)

        Returns:
            pandas.Series: New feature generated.
        """
        kst_series = self._check_fillna(self._kst, value=0)
        return pd.Series(kst_series, name="kst")

    def kst_sig(self) -> pd.Series:
        """Signal Line Know Sure Thing (KST)

        nsig-period SMA of KST

        Returns:
            pandas.Series: New feature generated.
        """
        kst_sig_series = self._check_fillna(self._kst_sig, value=0)
        return pd.Series(kst_sig_series, name="kst_sig")

    def kst_diff(self) -> pd.Series:
        """Diff Know Sure Thing (KST)

        KST - Signal_KST

        Returns:
            pandas.Series: New feature generated.
        """
        kst_diff = self._kst - self._kst_sig
        kst_diff = self._check_fillna(kst_diff, value=0)
        return pd.Series(kst_diff, name="kst_diff")


class DPOIndicator(IndicatorMixin):
    """Detrended Price Oscillator (DPO)

    Is an indicator designed to remove trend from price and make it easier to
    identify cycles.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:detrended_price_osci

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(self, close: pd.Series, window: int = 20, fillna: bool = False):
        self._close = close
        self._window = window
        self._fillna = fillna
        self._run()

    def _run(self):
        min_periods = 0 if self._fillna else self._window
        self._dpo = (
            self._close.shift(
                int((0.5 * self._window) + 1), fill_value=self._close.mean()
            )
            - self._close.rolling(self._window, min_periods=min_periods).mean()
        )

    def dpo(self) -> pd.Series:
        """Detrended Price Oscillator (DPO)

        Returns:
            pandas.Series: New feature generated.
        """
        dpo_series = self._check_fillna(self._dpo, value=0)
        return pd.Series(dpo_series, name="dpo_" + str(self._window))


class CCIIndicator(IndicatorMixin):
    """Commodity Channel Index (CCI)

    CCI measures the difference between a security's price change and its
    average price change. High positive readings indicate that prices are well
    above their average, which is a show of strength. Low negative readings
    indicate that prices are well below their average, which is a show of
    weakness.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:commodity_channel_index_cci

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        constant(int): constant.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int = 20,
        constant: float = 0.015,
        fillna: bool = False,
    ):
        self._high = high
        self._low = low
        self._close = close
        self._window = window
        self._constant = constant
        self._fillna = fillna
        self._run()

    def _run(self):
        def _mad(x):
            return np.mean(np.abs(x - np.mean(x)))

        min_periods = 0 if self._fillna else self._window
        typical_price = (self._high + self._low + self._close) / 3.0
        self._cci = (
            typical_price
            - typical_price.rolling(self._window, min_periods=min_periods).mean()
        ) / (
            self._constant
            * typical_price.rolling(self._window, min_periods=min_periods).apply(
                _mad, True
            )
        )

    def cci(self) -> pd.Series:
        """Commodity Channel Index (CCI)

        Returns:
            pandas.Series: New feature generated.
        """
        cci_series = self._check_fillna(self._cci, value=0)
        return pd.Series(cci_series, name="cci")


class ADXIndicator(IndicatorMixin):
    """Average Directional Movement Index (ADX)

    The Plus Directional Indicator (+DI) and Minus Directional Indicator (-DI)
    are derived from smoothed averages of these differences, and measure trend
    direction over time. These two indicators are often referred to
    collectively as the Directional Movement Indicator (DMI).

    The Average Directional Index (ADX) is in turn derived from the smoothed
    averages of the difference between +DI and -DI, and measures the strength
    of the trend (regardless of direction) over time.

    Using these three indicators together, chartists can determine both the
    direction and strength of the trend.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:average_directional_index_adx

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int = 14,
        fillna: bool = False,
    ):
        self._high = high
        self._low = low
        self._close = close
        self._window = window
        self._fillna = fillna
        self._run()

    def _run(self):
        if self._window == 0:
            raise ValueError("window may not be 0")

        close_shift = self._close.shift(1)

        pdm = _get_min_max(self._high, close_shift, "max")
        pdn = _get_min_max(self._low, close_shift, "min")

        diff_directional_movement = pdm - pdn

        self._trs_initial = np.zeros(self._window - 1)
        self._trs = np.zeros(len(self._close) - (self._window - 1))
        self._trs[0] = diff_directional_movement.dropna().iloc[0 : self._window].sum()
        diff_directional_movement = diff_directional_movement.reset_index(drop=True)

        for i in range(1, len(self._trs) - 1):
            self._trs[i] = (
                self._trs[i - 1]
                - (self._trs[i - 1] / float(self._window))
                + diff_directional_movement[self._window + i]
            )

        diff_up = self._high - self._high.shift(1)
        diff_down = self._low.shift(1) - self._low

        pos = abs(((diff_up > diff_down) & (diff_up > 0)) * diff_up)
        neg = abs(((diff_down > diff_up) & (diff_down > 0)) * diff_down)

        self._dip = np.zeros(len(self._close) - (self._window - 1))
        self._dip[0] = pos.dropna().iloc[0 : self._window].sum()

        pos = pos.reset_index(drop=True)

        for i in range(1, len(self._dip) - 1):
            self._dip[i] = (
                self._dip[i - 1]
                - (self._dip[i - 1] / float(self._window))
                + pos[self._window + i]
            )

        self._din = np.zeros(len(self._close) - (self._window - 1))
        self._din[0] = neg.dropna().iloc[0 : self._window].sum()

        neg = neg.reset_index(drop=True)

        for i in range(1, len(self._din) - 1):
            self._din[i] = (
                self._din[i - 1]
                - (self._din[i - 1] / float(self._window))
                + neg[self._window + i]
            )

    def adx(self) -> pd.Series:
        """Average Directional Index (ADX)

        Returns:
            pandas.Series: New feature generated.tr
        """
        dip = np.zeros(len(self._trs))

        for idx, value in enumerate(self._trs):
            if value != 0:
                dip[idx] = 100 * (self._dip[idx] / value)

            else:
                dip[idx] = 0

        din = np.zeros(len(self._trs))

        for idx, value in enumerate(self._trs):
            if value != 0:
                din[idx] = 100 * (self._din[idx] / value)

            else:
                din[idx] = 0

        directional_index = np.zeros(len(self._trs))

        for idx in range(len(self._trs)):
            if dip[idx] + din[idx] != 0:
                directional_index[idx] = 100 * np.abs(
                    (dip[idx] - din[idx]) / (dip[idx] + din[idx])
                )

            else:
                directional_index[idx] = 0

        adx_series = np.zeros(len(self._trs))
        adx_series[self._window] = directional_index[0 : self._window].mean()

        for i in range(self._window + 1, len(adx_series)):
            adx_series[i] = (
                (adx_series[i - 1] * (self._window - 1)) + directional_index[i - 1]
            ) / float(self._window)

        adx_series = np.concatenate((self._trs_initial, adx_series), axis=0)
        adx_series = pd.Series(data=adx_series, index=self._close.index)
        adx_series = self._check_fillna(adx_series, value=20)

        return pd.Series(adx_series, name="adx")

    def adx_pos(self) -> pd.Series:
        """Plus Directional Indicator (+DI)

        Returns:
            pandas.Series: New feature generated.
        """
        dip = np.zeros(len(self._close))

        for i in range(1, len(self._trs) - 1):
            if self._trs[i] != 0:
                dip[i + self._window] = 100 * (self._dip[i] / self._trs[i])

            else:
                dip[i + self._window] = 0

        adx_pos_series = self._check_fillna(
            pd.Series(dip, index=self._close.index), value=20
        )

        return pd.Series(adx_pos_series, name="adx_pos")

    def adx_neg(self) -> pd.Series:
        """Minus Directional Indicator (-DI)

        Returns:
            pandas.Series: New feature generated.
        """
        din = np.zeros(len(self._close))

        for i in range(1, len(self._trs) - 1):
            if self._trs[i] != 0:
                din[i + self._window] = 100 * (self._din[i] / self._trs[i])

            else:
                din[i + self._window] = 0

        adx_neg_series = self._check_fillna(
            pd.Series(din, index=self._close.index), value=20
        )

        return pd.Series(adx_neg_series, name="adx_neg")


class VortexIndicator(IndicatorMixin):
    """Vortex Indicator (VI)

    It consists of two oscillators that capture positive and negative trend
    movement. A bullish signal triggers when the positive trend indicator
    crosses above the negative trend indicator or a key level.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:vortex_indicator

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int = 14,
        fillna: bool = False,
    ):
        self._high = high
        self._low = low
        self._close = close
        self._window = window
        self._fillna = fillna
        self._run()

    def _run(self):
        close_shift = self._close.shift(1, fill_value=self._close.mean())
        true_range = self._true_range(self._high, self._low, close_shift)
        min_periods = 0 if self._fillna else self._window
        trn = true_range.rolling(self._window, min_periods=min_periods).sum()
        vmp = np.abs(self._high - self._low.shift(1))
        vmm = np.abs(self._low - self._high.shift(1))
        self._vip = vmp.rolling(self._window, min_periods=min_periods).sum() / trn
        self._vin = vmm.rolling(self._window, min_periods=min_periods).sum() / trn

    def vortex_indicator_pos(self):
        """+VI

        Returns:
            pandas.Series: New feature generated.
        """
        vip = self._check_fillna(self._vip, value=1)
        return pd.Series(vip, name="vip")

    def vortex_indicator_neg(self):
        """-VI

        Returns:
            pandas.Series: New feature generated.
        """
        vin = self._check_fillna(self._vin, value=1)
        return pd.Series(vin, name="vin")

    def vortex_indicator_diff(self):
        """Diff VI

        Returns:
            pandas.Series: New feature generated.
        """
        vid = self._vip - self._vin
        vid = self._check_fillna(vid, value=0)
        return pd.Series(vid, name="vid")


class PSARIndicator(IndicatorMixin):
    """Parabolic Stop and Reverse (Parabolic SAR)

    The Parabolic Stop and Reverse, more commonly known as the
    Parabolic SAR,is a trend-following indicator developed by
    J. Welles Wilder. The Parabolic SAR is displayed as a single
    parabolic line (or dots) underneath the price bars in an uptrend,
    and above the price bars in a downtrend.

    https://school.stockcharts.com/doku.php?id=technical_indicators:parabolic_sar

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        step(float): the Acceleration Factor used to compute the SAR.
        max_step(float): the maximum value allowed for the Acceleration Factor.
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        step: float = 0.02,
        max_step: float = 0.20,
        fillna: bool = False,
    ):
        self._high = high
        self._low = low
        self._close = close
        self._step = step
        self._max_step = max_step
        self._fillna = fillna
        self._run()

    def _run(self):  # noqa
        up_trend = True
        acceleration_factor = self._step
        up_trend_high = self._high.iloc[0]
        down_trend_low = self._low.iloc[0]

        self._psar = self._close.copy()
        self._psar_up = pd.Series(index=self._psar.index, dtype="float64")
        self._psar_down = pd.Series(index=self._psar.index, dtype="float64")

        for i in range(2, len(self._close)):
            reversal = False

            max_high = self._high.iloc[i]
            min_low = self._low.iloc[i]

            if up_trend:
                self._psar.iloc[i] = self._psar.iloc[i - 1] + (
                    acceleration_factor * (up_trend_high - self._psar.iloc[i - 1])
                )

                if min_low < self._psar.iloc[i]:
                    reversal = True
                    self._psar.iloc[i] = up_trend_high
                    down_trend_low = min_low
                    acceleration_factor = self._step
                else:
                    if max_high > up_trend_high:
                        up_trend_high = max_high
                        acceleration_factor = min(
                            acceleration_factor + self._step, self._max_step
                        )

                    low1 = self._low.iloc[i - 1]
                    low2 = self._low.iloc[i - 2]
                    if low2 < self._psar.iloc[i]:
                        self._psar.iloc[i] = low2
                    elif low1 < self._psar.iloc[i]:
                        self._psar.iloc[i] = low1
            else:
                self._psar.iloc[i] = self._psar.iloc[i - 1] - (
                    acceleration_factor * (self._psar.iloc[i - 1] - down_trend_low)
                )

                if max_high > self._psar.iloc[i]:
                    reversal = True
                    self._psar.iloc[i] = down_trend_low
                    up_trend_high = max_high
                    acceleration_factor = self._step
                else:
                    if min_low < down_trend_low:
                        down_trend_low = min_low
                        acceleration_factor = min(
                            acceleration_factor + self._step, self._max_step
                        )

                    high1 = self._high.iloc[i - 1]
                    high2 = self._high.iloc[i - 2]
                    if high2 > self._psar.iloc[i]:
                        self._psar[i] = high2
                    elif high1 > self._psar.iloc[i]:
                        self._psar.iloc[i] = high1

            up_trend = up_trend != reversal  # XOR

            if up_trend:
                self._psar_up.iloc[i] = self._psar.iloc[i]
            else:
                self._psar_down.iloc[i] = self._psar.iloc[i]

    def psar(self) -> pd.Series:
        """PSAR value

        Returns:
            pandas.Series: New feature generated.
        """
        psar_series = self._check_fillna(self._psar, value=-1)
        return pd.Series(psar_series, name="psar")

    def psar_up(self) -> pd.Series:
        """PSAR up trend value

        Returns:
            pandas.Series: New feature generated.
        """
        psar_up_series = self._check_fillna(self._psar_up, value=-1)
        return pd.Series(psar_up_series, name="psarup")

    def psar_down(self) -> pd.Series:
        """PSAR down trend value

        Returns:
            pandas.Series: New feature generated.
        """
        psar_down_series = self._check_fillna(self._psar_down, value=-1)
        return pd.Series(psar_down_series, name="psardown")

    def psar_up_indicator(self) -> pd.Series:
        """PSAR up trend value indicator

        Returns:
            pandas.Series: New feature generated.
        """
        indicator = self._psar_up.where(
            self._psar_up.notnull() & self._psar_up.shift(1).isnull(), 0
        )
        indicator = indicator.where(indicator == 0, 1)
        return pd.Series(indicator, index=self._close.index, name="psariup")

    def psar_down_indicator(self) -> pd.Series:
        """PSAR down trend value indicator

        Returns:
            pandas.Series: New feature generated.
        """
        indicator = self._psar_up.where(
            self._psar_down.notnull() & self._psar_down.shift(1).isnull(), 0
        )
        indicator = indicator.where(indicator == 0, 1)
        return pd.Series(indicator, index=self._close.index, name="psaridown")


class STCIndicator(IndicatorMixin):
    """Schaff Trend Cycle (STC)

    The Schaff Trend Cycle (STC) is a charting indicator that
    is commonly used to identify market trends and provide buy
    and sell signals to traders. Developed in 1999 by noted currency
    trader Doug Schaff, STC is a type of oscillator and is based on
    the assumption that, regardless of time frame, currency trends
    accelerate and decelerate in cyclical patterns.

    https://www.investopedia.com/articles/forex/10/schaff-trend-cycle-indicator.asp

    Args:
        close(pandas.Series): dataset 'Close' column.
        window_fast(int): n period short-term.
        window_slow(int): n period long-term.
        cycle(int): cycle size
        smooth1(int): ema period over stoch_k
        smooth2(int): ema period over stoch_kd
        fillna(bool): if True, fill nan values.
    """

    def __init__(
        self,
        close: pd.Series,
        window_slow: int = 50,
        window_fast: int = 23,
        cycle: int = 10,
        smooth1: int = 3,
        smooth2: int = 3,
        fillna: bool = False,
    ):
        self._close = close
        self._window_slow = window_slow
        self._window_fast = window_fast
        self._cycle = cycle
        self._smooth1 = smooth1
        self._smooth2 = smooth2
        self._fillna = fillna
        self._run()

    def _run(self):
        _emafast = _ema(self._close, self._window_fast, self._fillna)
        _emaslow = _ema(self._close, self._window_slow, self._fillna)
        _macd = _emafast - _emaslow

        _macdmin = _macd.rolling(window=self._cycle).min()
        _macdmax = _macd.rolling(window=self._cycle).max()
        _stoch_k = 100 * (_macd - _macdmin) / (_macdmax - _macdmin)
        _stoch_d = _ema(_stoch_k, self._smooth1, self._fillna)

        _stoch_d_min = _stoch_d.rolling(window=self._cycle).min()
        _stoch_d_max = _stoch_d.rolling(window=self._cycle).max()
        _stoch_kd = 100 * (_stoch_d - _stoch_d_min) / (_stoch_d_max - _stoch_d_min)
        self._stc = _ema(_stoch_kd, self._smooth2, self._fillna)

    def stc(self):
        """Schaff Trend Cycle

        Returns:
            pandas.Series: New feature generated.
        """
        stc_series = self._check_fillna(self._stc)
        return pd.Series(stc_series, name="stc")


def ema_indicator(close, window=12, fillna=False):
    """Exponential Moving Average (EMA)

    Returns:
        pandas.Series: New feature generated.
    """
    return EMAIndicator(close=close, window=window, fillna=fillna).ema_indicator()


def sma_indicator(close, window=12, fillna=False):
    """Simple Moving Average (SMA)

    Returns:
        pandas.Series: New feature generated.
    """
    return SMAIndicator(close=close, window=window, fillna=fillna).sma_indicator()


def wma_indicator(close, window=9, fillna=False):
    """Weighted Moving Average (WMA)

    Returns:
        pandas.Series: New feature generated.
    """
    return WMAIndicator(close=close, window=window, fillna=fillna).wma()


def macd(close, window_slow=26, window_fast=12, fillna=False):
    """Moving Average Convergence Divergence (MACD)

    Is a trend-following momentum indicator that shows the relationship between
    two moving averages of prices.

    https://en.wikipedia.org/wiki/MACD

    Args:
        close(pandas.Series): dataset 'Close' column.
        window_fast(int): n period short-term.
        window_slow(int): n period long-term.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return MACD(
        close=close,
        window_slow=window_slow,
        window_fast=window_fast,
        window_sign=9,
        fillna=fillna,
    ).macd()


def macd_signal(close, window_slow=26, window_fast=12, window_sign=9, fillna=False):
    """Moving Average Convergence Divergence (MACD Signal)

    Shows EMA of MACD.

    https://en.wikipedia.org/wiki/MACD

    Args:
        close(pandas.Series): dataset 'Close' column.
        window_fast(int): n period short-term.
        window_slow(int): n period long-term.
        window_sign(int): n period to signal.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return MACD(
        close=close,
        window_slow=window_slow,
        window_fast=window_fast,
        window_sign=window_sign,
        fillna=fillna,
    ).macd_signal()


def macd_diff(close, window_slow=26, window_fast=12, window_sign=9, fillna=False):
    """Moving Average Convergence Divergence (MACD Diff)

    Shows the relationship between MACD and MACD Signal.

    https://en.wikipedia.org/wiki/MACD

    Args:
        close(pandas.Series): dataset 'Close' column.
        window_fast(int): n period short-term.
        window_slow(int): n period long-term.
        window_sign(int): n period to signal.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return MACD(
        close=close,
        window_slow=window_slow,
        window_fast=window_fast,
        window_sign=window_sign,
        fillna=fillna,
    ).macd_diff()


def adx(high, low, close, window=14, fillna=False):
    """Average Directional Movement Index (ADX)

    The Plus Directional Indicator (+DI) and Minus Directional Indicator (-DI)
    are derived from smoothed averages of these differences, and measure trend
    direction over time. These two indicators are often referred to
    collectively as the Directional Movement Indicator (DMI).

    The Average Directional Index (ADX) is in turn derived from the smoothed
    averages of the difference between +DI and -DI, and measures the strength
    of the trend (regardless of direction) over time.

    Using these three indicators together, chartists can determine both the
    direction and strength of the trend.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:average_directional_index_adx

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return ADXIndicator(
        high=high, low=low, close=close, window=window, fillna=fillna
    ).adx()


def adx_pos(high, low, close, window=14, fillna=False):
    """Average Directional Movement Index Positive (ADX)

    The Plus Directional Indicator (+DI) and Minus Directional Indicator (-DI)
    are derived from smoothed averages of these differences, and measure trend
    direction over time. These two indicators are often referred to
    collectively as the Directional Movement Indicator (DMI).

    The Average Directional Index (ADX) is in turn derived from the smoothed
    averages of the difference between +DI and -DI, and measures the strength
    of the trend (regardless of direction) over time.

    Using these three indicators together, chartists can determine both the
    direction and strength of the trend.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:average_directional_index_adx

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return ADXIndicator(
        high=high, low=low, close=close, window=window, fillna=fillna
    ).adx_pos()


def adx_neg(high, low, close, window=14, fillna=False):
    """Average Directional Movement Index Negative (ADX)

    The Plus Directional Indicator (+DI) and Minus Directional Indicator (-DI)
    are derived from smoothed averages of these differences, and measure trend
    direction over time. These two indicators are often referred to
    collectively as the Directional Movement Indicator (DMI).

    The Average Directional Index (ADX) is in turn derived from the smoothed
    averages of the difference between +DI and -DI, and measures the strength
    of the trend (regardless of direction) over time.

    Using these three indicators together, chartists can determine both the
    direction and strength of the trend.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:average_directional_index_adx

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return ADXIndicator(
        high=high, low=low, close=close, window=window, fillna=fillna
    ).adx_neg()


def vortex_indicator_pos(high, low, close, window=14, fillna=False):
    """Vortex Indicator (VI)

    It consists of two oscillators that capture positive and negative trend
    movement. A bullish signal triggers when the positive trend indicator
    crosses above the negative trend indicator or a key level.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:vortex_indicator

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return VortexIndicator(
        high=high, low=low, close=close, window=window, fillna=fillna
    ).vortex_indicator_pos()


def vortex_indicator_neg(high, low, close, window=14, fillna=False):
    """Vortex Indicator (VI)

    It consists of two oscillators that capture positive and negative trend
    movement. A bearish signal triggers when the negative trend indicator
    crosses above the positive trend indicator or a key level.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:vortex_indicator

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return VortexIndicator(
        high=high, low=low, close=close, window=window, fillna=fillna
    ).vortex_indicator_neg()


def trix(close, window=15, fillna=False):
    """Trix (TRIX)

    Shows the percent rate of change of a triple exponentially smoothed moving
    average.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:trix

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return TRIXIndicator(close=close, window=window, fillna=fillna).trix()


def mass_index(high, low, window_fast=9, window_slow=25, fillna=False):
    """Mass Index (MI)

    It uses the high-low range to identify trend reversals based on range
    expansions. It identifies range bulges that can foreshadow a reversal of
    the current trend.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:mass_index

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window_fast(int): fast window value.
        window_slow(int): slow window value.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.

    """
    return MassIndex(
        high=high,
        low=low,
        window_fast=window_fast,
        window_slow=window_slow,
        fillna=fillna,
    ).mass_index()


def cci(high, low, close, window=20, constant=0.015, fillna=False):
    """Commodity Channel Index (CCI)

    CCI measures the difference between a security's price change and its
    average price change. High positive readings indicate that prices are well
    above their average, which is a show of strength. Low negative readings
    indicate that prices are well below their average, which is a show of
    weakness.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:commodity_channel_index_cci

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        window(int): n periods.
        constant(int): constant.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.

    """
    return CCIIndicator(
        high=high, low=low, close=close, window=window, constant=constant, fillna=fillna
    ).cci()


def dpo(close, window=20, fillna=False):
    """Detrended Price Oscillator (DPO)

    Is an indicator designed to remove trend from price and make it easier to
    identify cycles.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:detrended_price_osci

    Args:
        close(pandas.Series): dataset 'Close' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return DPOIndicator(close=close, window=window, fillna=fillna).dpo()


def kst(
    close,
    roc1=10,
    roc2=15,
    roc3=20,
    roc4=30,
    window1=10,
    window2=10,
    window3=10,
    window4=15,
    fillna=False,
):
    """KST Oscillator (KST)

    It is useful to identify major stock market cycle junctures because its
    formula is weighed to be more greatly influenced by the longer and more
    dominant time spans, in order to better reflect the primary swings of stock
    market cycle.

    https://en.wikipedia.org/wiki/KST_oscillator

    Args:
        close(pandas.Series): dataset 'Close' column.
        roc1(int): r1 period.
        roc2(int): r2 period.
        roc3(int): r3 period.
        roc4(int): r4 period.
        window1(int): n1 smoothed period.
        window2(int): n2 smoothed period.
        window3(int): n3 smoothed period.
        window4(int): n4 smoothed period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return KSTIndicator(
        close=close,
        roc1=roc1,
        roc2=roc2,
        roc3=roc3,
        roc4=roc4,
        window1=window1,
        window2=window2,
        window3=window3,
        window4=window4,
        nsig=9,
        fillna=fillna,
    ).kst()


def stc(
    close, window_slow=50, window_fast=23, cycle=10, smooth1=3, smooth2=3, fillna=False
):
    """Schaff Trend Cycle (STC)

    The Schaff Trend Cycle (STC) is a charting indicator that
    is commonly used to identify market trends and provide buy
    and sell signals to traders. Developed in 1999 by noted currency
    trader Doug Schaff, STC is a type of oscillator and is based on
    the assumption that, regardless of time frame, currency trends
    accelerate and decelerate in cyclical patterns.

    https://www.investopedia.com/articles/forex/10/schaff-trend-cycle-indicator.asp

    Args:
        close(pandas.Series): dataset 'Close' column.
        window_fast(int): n period short-term.
        window_slow(int): n period long-term.
        cycle(int): n period
        smooth1(int): ema period over stoch_k
        smooth2(int): ema period over stoch_kd
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return STCIndicator(
        close=close,
        window_slow=window_slow,
        window_fast=window_fast,
        cycle=cycle,
        smooth1=smooth1,
        smooth2=smooth2,
        fillna=fillna,
    ).stc()


def kst_sig(
    close,
    roc1=10,
    roc2=15,
    roc3=20,
    roc4=30,
    window1=10,
    window2=10,
    window3=10,
    window4=15,
    nsig=9,
    fillna=False,
):
    """KST Oscillator (KST Signal)

    It is useful to identify major stock market cycle junctures because its
    formula is weighed to be more greatly influenced by the longer and more
    dominant time spans, in order to better reflect the primary swings of stock
    market cycle.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:know_sure_thing_kst

    Args:
        close(pandas.Series): dataset 'Close' column.
        roc1(int): roc1 period.
        roc2(int): roc2 period.
        roc3(int): roc3 period.
        roc4(int): roc4 period.
        window1(int): n1 smoothed period.
        window2(int): n2 smoothed period.
        window3(int): n3 smoothed period.
        window4(int): n4 smoothed period.
        nsig(int): n period to signal.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return KSTIndicator(
        close=close,
        roc1=roc1,
        roc2=roc2,
        roc3=roc3,
        roc4=roc4,
        window1=window1,
        window2=window2,
        window3=window3,
        window4=window4,
        nsig=nsig,
        fillna=fillna,
    ).kst_sig()


def ichimoku_conversion_line(
    high, low, window1=9, window2=26, visual=False, fillna=False
) -> pd.Series:
    """Tenkan-sen (Conversion Line)

    It identifies the trend and look for potential signals within that trend.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ichimoku_cloud

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window1(int): n1 low period.
        window2(int): n2 medium period.
        visual(bool): if True, shift n2 values.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return IchimokuIndicator(
        high=high,
        low=low,
        window1=window1,
        window2=window2,
        window3=52,
        visual=visual,
        fillna=fillna,
    ).ichimoku_conversion_line()


def ichimoku_base_line(
    high, low, window1=9, window2=26, visual=False, fillna=False
) -> pd.Series:
    """Kijun-sen (Base Line)

    It identifies the trend and look for potential signals within that trend.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ichimoku_cloud

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window1(int): n1 low period.
        window2(int): n2 medium period.
        visual(bool): if True, shift n2 values.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return IchimokuIndicator(
        high=high,
        low=low,
        window1=window1,
        window2=window2,
        window3=52,
        visual=visual,
        fillna=fillna,
    ).ichimoku_base_line()


def ichimoku_a(high, low, window1=9, window2=26, visual=False, fillna=False):
    """Ichimoku Kinkō Hyō (Ichimoku)

    It identifies the trend and look for potential signals within that trend.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ichimoku_cloud

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window1(int): n1 low period.
        window2(int): n2 medium period.
        visual(bool): if True, shift n2 values.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return IchimokuIndicator(
        high=high,
        low=low,
        window1=window1,
        window2=window2,
        window3=52,
        visual=visual,
        fillna=fillna,
    ).ichimoku_a()


def ichimoku_b(high, low, window2=26, window3=52, visual=False, fillna=False):
    """Ichimoku Kinkō Hyō (Ichimoku)

    It identifies the trend and look for potential signals within that trend.

    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:ichimoku_cloud

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window2(int): n2 medium period.
        window3(int): n3 high period.
        visual(bool): if True, shift n2 values.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return IchimokuIndicator(
        high=high,
        low=low,
        window1=9,
        window2=window2,
        window3=window3,
        visual=visual,
        fillna=fillna,
    ).ichimoku_b()


def aroon_up(high, low, window=25, fillna=False):
    """Aroon Indicator (AI)

    Identify when trends are likely to change direction (uptrend).

    Aroon Up - ((N - Days Since N-day High) / N) x 100

    https://www.investopedia.com/terms/a/aroon.asp

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.

    """
    return AroonIndicator(high=high, low=low, window=window, fillna=fillna).aroon_up()


def aroon_down(high, low, window=25, fillna=False):
    """Aroon Indicator (AI)

    Identify when trends are likely to change direction (downtrend).

    Aroon Down - ((N - Days Since N-day Low) / N) x 100

    https://www.investopedia.com/terms/a/aroon.asp

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        window(int): n period.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    return AroonIndicator(high=high, low=low, window=window, fillna=fillna).aroon_down()


def psar_up(high, low, close, step=0.02, max_step=0.20, fillna=False):
    """Parabolic Stop and Reverse (Parabolic SAR)

    Returns the PSAR series with non-N/A values for upward trends

    https://school.stockcharts.com/doku.php?id=technical_indicators:parabolic_sar

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        step(float): the Acceleration Factor used to compute the SAR.
        max_step(float): the maximum value allowed for the Acceleration Factor.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    indicator = PSARIndicator(
        high=high, low=low, close=close, step=step, max_step=max_step, fillna=fillna
    )
    return indicator.psar_up()


def psar_down(high, low, close, step=0.02, max_step=0.20, fillna=False):
    """Parabolic Stop and Reverse (Parabolic SAR)

    Returns the PSAR series with non-N/A values for downward trends

    https://school.stockcharts.com/doku.php?id=technical_indicators:parabolic_sar

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        step(float): the Acceleration Factor used to compute the SAR.
        max_step(float): the maximum value allowed for the Acceleration Factor.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    indicator = PSARIndicator(
        high=high, low=low, close=close, step=step, max_step=max_step, fillna=fillna
    )
    return indicator.psar_down()


def psar_up_indicator(high, low, close, step=0.02, max_step=0.20, fillna=False):
    """Parabolic Stop and Reverse (Parabolic SAR) Upward Trend Indicator

    Returns 1, if there is a reversal towards an upward trend. Else, returns 0.

    https://school.stockcharts.com/doku.php?id=technical_indicators:parabolic_sar

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        step(float): the Acceleration Factor used to compute the SAR.
        max_step(float): the maximum value allowed for the Acceleration Factor.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    indicator = PSARIndicator(
        high=high, low=low, close=close, step=step, max_step=max_step, fillna=fillna
    )
    return indicator.psar_up_indicator()


def psar_down_indicator(high, low, close, step=0.02, max_step=0.20, fillna=False):
    """Parabolic Stop and Reverse (Parabolic SAR) Downward Trend Indicator

    Returns 1, if there is a reversal towards an downward trend. Else, returns 0.

    https://school.stockcharts.com/doku.php?id=technical_indicators:parabolic_sar

    Args:
        high(pandas.Series): dataset 'High' column.
        low(pandas.Series): dataset 'Low' column.
        close(pandas.Series): dataset 'Close' column.
        step(float): the Acceleration Factor used to compute the SAR.
        max_step(float): the maximum value allowed for the Acceleration Factor.
        fillna(bool): if True, fill nan values.

    Returns:
        pandas.Series: New feature generated.
    """
    indicator = PSARIndicator(
        high=high, low=low, close=close, step=step, max_step=max_step, fillna=fillna
    )
    return indicator.psar_down_indicator()
