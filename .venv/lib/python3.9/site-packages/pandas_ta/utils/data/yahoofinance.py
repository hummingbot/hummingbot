# -*- coding: utf-8 -*-
from pandas import DataFrame
from pandas_ta import Imports, RATE, version
from .._core import _camelCase2Title
from .._time import ytd


def yf(ticker: str, **kwargs):
    """yf - yfinance wrapper

    It retrieves market data (ohlcv) from Yahoo Finance using yfinance.
    To install yfinance. (pip install yfinance) This method can also pull
    additional data using the 'kind' kwarg. By default kind=None and retrieves
    Historical Chart Data.

    Other options of 'kind' include:
    * All: "all"
        - Prints everything below but only returns Chart History to Pandas TA
    * Company Information: "info"
    * Institutional Holders: "institutional_holders" or "ih"
    * Major Holders: "major_holders" or "mh"
    * Mutual Fund Holders: "mutualfund_holders" or "mfh"
    * Recommendations (YTD): "recommendations" or "rec"
    * Earnings Calendar: "calendar" or "cal"
    * Earnings: "earnings" or "earn"
    * Sustainability/ESG Scores: "sustainability", "sus" or "esg"
    * Financials: "financials" or "fin"
        - Returns in order: Income Statement, Balance Sheet and Cash Flow
    * Option Chain: "option_chain" or "oc"
        - Uses the nearest expiration date by default
        - Change the expiration date using kwarg "exp"
        - Show ITM options, set kwarg "itm" to True. Or OTM options, set
        kwarg "itm" to False.
    * Chart History:
        - The only data returned to Pandas TA.

    Args:
        ticker (str): Any string for a ticker you would use with yfinance.
            Default: "SPY"
    Kwargs:
        calls (bool): When True, prints only Option Calls for the Option Chain.
            Default: None
        desc (bool): Will print Company Description when printing Company
            Information. Default: False
        exp (str): Used to print other Option Chains for the given Expiration
            Date. Default: Nearest Expiration Date for the Option Chains
        interval (str): A yfinance argument. Default: "1d"
        itm (bool): When printing Option Chains, shows ITM Options when True.
            When False, it shows OTM Options: Default: None
        kind (str): Options see above. Default: None
        period (str): A yfinance argument. Default: "max"
        proxy (dict): Proxy for yfinance to use. Default: {}
        puts (bool): When True, prints only Option Puts for the Option Chain.
            Default: None
        show (int > 0): How many last rows of Chart History to show.
            Default: None
        snd (int): How many recent Splits and Dividends to show in Company
            Information. Default: 5
        verbose (bool): Prints Company Information "info" and a Chart History
            header to the screen. Default: False

    Returns:
        Exits if the DataFrame is empty or None
        Otherwise it returns a DataFrame of the Chart History
    """
    verbose = kwargs.pop("verbose", False)
    if ticker is not None and isinstance(ticker, str) and len(ticker):
        ticker = ticker.upper()
    else:
        ticker = "SPY"

    kind = kwargs.pop("kind", None)
    if kind is not None and isinstance(kind, str) and len(kind):
        kind = kind.lower()

    period = kwargs.pop("period", "max")
    interval = kwargs.pop("interval", "1d")
    proxy = kwargs.pop("proxy", {})
    show = kwargs.pop("show", None)

    if not Imports["yfinance"]:
        print(f"[X] Please install yfinance to use this method. (pip install yfinance)")
        return
    if Imports["yfinance"] and ticker is not None:
        import yfinance as yfra
        yfra.pdr_override()

        # Ticker Info & Chart History
        yfd = yfra.Ticker(ticker)

        try:
            df = yfd.history(period=period, interval=interval, proxy=proxy, **kwargs)
        except:
            if yfra.__version__ == "0.1.60":
                print(f"[!] If history is not downloading, see yfinance Issue #760 by user djl0.")
                print(f"[!] https://github.com/ranaroussi/yfinance/issues/760#issuecomment-877355832")
                return

        if df.empty: return
        df.name = ticker

        try:
            ticker_info = yfd.info
        except KeyError as ke:
            print(f"[X] Ticker '{ticker}' not found.")
            return

        filtered = {k: v for k, v in ticker_info.items() if v is not None}
        # print(f"\n{type(ticker_info)}\n{ticker_info}\n{ticker_info.items()}")
        ticker_info.clear()
        ticker_info.update(filtered)

        # Dividends and Splits
        dividends, splits = yfd.splits, yfd.dividends

        _all, div = ["all"], "=" * 53 # Max div width is 80
        if kind in _all + ["info"] or verbose:
            description = kwargs.pop("desc", False)
            snd_length = kwargs.pop("snd", 5)

            print("\n====  Company Information  " + div)
            ci_header = f"({ticker_info['shortName']}) [{ticker_info['symbol']}]"
            if "longName" in ticker_info and len(ticker_info["longName"]):
                print(f"{ticker_info['longName']}" + ci_header)
            else:
                print(ci_header)

            if description:
                print(f"{ticker_info['longBusinessSummary']}\n")
            if "address1" in ticker_info and len(ticker_info["address1"]):
                if "address2" in ticker_info and len(ticker_info["address2"]):
                    print(f"{ticker_info['address1']} {ticker_info['address2']}")
                else:
                    print(f"{ticker_info['address1']}")

                if "city" in ticker_info and len(ticker_info["city"]) and "state" in ticker_info and len(ticker_info["state"]) \
                    and "zip" in ticker_info and len(ticker_info["zip"]) and "country" in ticker_info and len(ticker_info["country"]):
                    print(f"{ticker_info['city']}, {ticker_info['state']} {ticker_info['zip']}, {ticker_info['country']}")
                else:
                    print(f"{ticker_info['state']} {ticker_info['zip']}, {ticker_info['country']}")
                print(f"Phone (Fax): {ticker_info['phone']} ({ticker_info['fax'] if 'fax' in ticker_info else 'N/A'})")

            if "website" in ticker_info and len(ticker_info['website']):
                s = f"Website: {ticker_info['website']}".ljust(40)
                if "fullTimeEmployees" in ticker_info:
                    s += f"FT Employees: {ticker_info['fullTimeEmployees']:,}".rjust(40)
                print(s)
            elif "fullTimeEmployees" in ticker_info:
                print(f"FT Employees: {ticker_info['fullTimeEmployees']:,}")

            if "companyOfficers" in ticker_info and len(ticker_info['companyOfficers']):
                print(f"Company Officers: {', '.join(ticker_info['companyOfficers'])}".ljust(40))
            if "sector" in ticker_info and len(ticker_info["sector"]) and "industry" in ticker_info and len(ticker_info["industry"]):
                # print(f"Sector: {ticker_info['sector']}".ljust(39), f"Industry: {ticker_info['industry']}".rjust(40))
                print(f"Sector | Industry".ljust(29), f"{ticker_info['sector']} | {ticker_info['industry']}".rjust(50))

            print("\n====  Market Information   " + div)
            _category = f" | {ticker_info['category']}" if "category" in ticker_info and ticker_info["category"] is not None else ""
            print(
                f"Market | Exchange | Symbol{' | Category' if 'category' in ticker_info and ticker_info['category'] is not None else ''}".ljust(39),
                f"{ticker_info['market'].split('_')[0].upper()} | {ticker_info['exchange']} | {ticker_info['symbol']}{_category}".rjust(40)
            )

            print()
            if "marketCap" in ticker_info and ticker_info["marketCap"] is not None:
                print(f"Market Cap.".ljust(39), f"{ticker_info['marketCap']:,} ({ticker_info['marketCap']/1000000:,.2f} MM)".rjust(40))
            if "navPrice" in ticker_info and ticker_info["navPrice"] is not None or "yield" in ticker_info and ticker_info["yield"] is not None:
                print(f"NAV | Yield".ljust(39), f"{ticker_info['navPrice']} | {100 * ticker_info['yield']:.4f}%".rjust(40))
            if "sharesOutstanding" in ticker_info and ticker_info["sharesOutstanding"] is not None and "floatShares" in ticker_info and ticker_info["floatShares"] is not None:
                print(f"Shares Outstanding | Float".ljust(39), f"{ticker_info['sharesOutstanding']:,} | {ticker_info['floatShares']:,}".rjust(40))
            if "impliedSharesOutstanding" in ticker_info and ticker_info["impliedSharesOutstanding"] is not None:
                print(f"Implied Shares Outstanding".ljust(39), f"{ticker_info['impliedSharesOutstanding']:,}".rjust(40))
            if "sharesShort" in ticker_info and "shortRatio" in ticker_info and ticker_info["sharesShort"] is not None and ticker_info["shortRatio"] is not None:
                print(f"Shares Short | Ratio".ljust(39), f"{ticker_info['sharesShort']:,} | {ticker_info['shortRatio']:,}".rjust(40))
            if "shortPercentOfFloat" in ticker_info and ticker_info['shortPercentOfFloat'] is not None and "sharesShortPriorMonth" in ticker_info and ticker_info['sharesShortPriorMonth'] is not None:
                print(f"Short % of Float | Short prior Month".ljust(39), f"{100 * ticker_info['shortPercentOfFloat']:.4f}% | {ticker_info['sharesShortPriorMonth']:,}".rjust(40))
            if "heldPercentInstitutions" in ticker_info and ticker_info['heldPercentInstitutions'] is not None or "heldPercentInsiders" in ticker_info and ticker_info['heldPercentInsiders'] is not None:
                print(f"Insiders % | Institution %".ljust(39), f"{100 * ticker_info['heldPercentInsiders']:.4f}% | {100 * ticker_info['heldPercentInstitutions']:.4f}%".rjust(40))

            print()
            if "bookValue" in ticker_info and ticker_info['bookValue'] is not None or "priceToBook" in ticker_info and ticker_info['priceToBook'] is not None or "pegRatio" in ticker_info and ticker_info['pegRatio'] is not None:
                print(f"Book Value | Price to Book | Peg Ratio".ljust(39), f"{ticker_info['priceToBook']} | {ticker_info['priceToBook']} | {ticker_info['pegRatio']}".rjust(40))
            if "forwardPE" in ticker_info and ticker_info['forwardPE'] is not None:
                print(f"Forward PE".ljust(39), f"{ticker_info['forwardPE']}".rjust(40))
            if "forwardEps" in ticker_info and ticker_info['forwardEps'] is not None or "trailingEps" in ticker_info and ticker_info['trailingEps'] is not None:
                print(f"Forward EPS | Trailing EPS".ljust(39), f"{ticker_info['forwardEps']} | {ticker_info['trailingEps']}".rjust(40))
            if "enterpriseValue" in ticker_info and ticker_info['enterpriseValue'] is not None:
                print(f"Enterprise Value".ljust(39), f"{ticker_info['enterpriseValue']:,}".rjust(40))
            if "enterpriseToRevenue" in ticker_info and ticker_info['enterpriseToRevenue'] is not None or "enterpriseToEbitda" in ticker_info and ticker_info['enterpriseToEbitda'] is not None:
                print(f"Enterprise to Revenue | to EBITDA".ljust(39), f"{ticker_info['enterpriseToRevenue']} | {ticker_info['enterpriseToEbitda']}".rjust(40))

            print()
            if "netIncomeToCommon" in ticker_info and ticker_info['netIncomeToCommon'] is not None:
                print(f"Net Income to Common".ljust(39), f"{ticker_info['netIncomeToCommon']:,}".rjust(40))
            if "revenueQuarterlyGrowth" in ticker_info and ticker_info['revenueQuarterlyGrowth'] is not None:
                print(f"Revenue Quarterly Growth".ljust(39), f"{ticker_info['revenueQuarterlyGrowth']}".rjust(40))
            if "profitMargins" in ticker_info and ticker_info['profitMargins'] is not None:
                print(f"Profit Margins".ljust(39), f"{100 * ticker_info['profitMargins']:.4f}%".rjust(40))
            if "earningsQuarterlyGrowth" in ticker_info and ticker_info['earningsQuarterlyGrowth'] is not None:
                print(f"Quarterly Earnings Growth".ljust(39), f"{ticker_info['earningsQuarterlyGrowth']}".rjust(40))
            if "annualReportExpenseRatio" in ticker_info and ticker_info['annualReportExpenseRatio'] is not None:
                print(f"Annual Expense Ratio".ljust(39), f"{ticker_info['annualReportExpenseRatio']}".rjust(40))

            print("\n====  Price Information    " + div)
            _o, _h, _l, _c, _v = ticker_info['open'], ticker_info['dayHigh'], ticker_info['dayLow'], ticker_info['regularMarketPrice'], ticker_info['regularMarketVolume']
            print(f"Open High Low | Close".ljust(39), f"{_o:.4f}  {_o:.4f}  {_l:.4f} | {_c:.4f}".rjust(40))
            print(f"HL2 | HLC3 | OHLC4 | C - OHLC4".ljust(39), f"{0.5 * (_h + _l):.4f}, {(_h + _l + _c) / 3.:.4f}, {0.25 * (_o + _h + _l + _c):.4f}, {_c - 0.25 * (_o + _h + _l + _c):.4f}".rjust(40))
            print(f"Change (%)".ljust(39), f"{_c - ticker_info['previousClose']:.4f} ({100 * ((_c / ticker_info['previousClose']) - 1):.4f}%)".rjust(40))
            if "bid" in ticker_info and ticker_info['bid'] is not None \
                and "bidSize" in ticker_info and ticker_info['bidSize'] is not None \
                and "ask" in ticker_info and ticker_info['ask'] is not None \
                and "askSize" in ticker_info and ticker_info['askSize'] is not None:
                print(f"Bid | Ask | Spread".ljust(39), f"{ticker_info['bid']} x {ticker_info['bidSize']} | {ticker_info['ask']} x {ticker_info['askSize']} | {ticker_info['ask'] - ticker_info['bid']:.4f}".rjust(40))
            print(f"Volume | Market | Avg Vol (10Day)".ljust(40))
            print(f"{ticker_info['volume']:,} | {_v:,} | {ticker_info['averageVolume']:,} ({ticker_info['averageDailyVolume10Day']:,})".rjust(80))

            print()
            if "52WeekChange" in ticker_info and ticker_info['52WeekChange'] is not None:
                print(f"52Wk % Change".ljust(39), f"{100 * ticker_info['52WeekChange']:.4f}%".rjust(40))
            if "SandP52WeekChange" in ticker_info and ticker_info['SandP52WeekChange'] is not None:
                print(f"52Wk % Change vs S&P500".ljust(39), f"{100 *ticker_info['SandP52WeekChange']:.4f}%".rjust(40))
            if "fiftyTwoWeekHigh" in ticker_info and "fiftyTwoWeekLow" in ticker_info and "previousClose" in ticker_info: # or 'regularMarketPrice'
                print(f"52Wk Range (% from 52Wk Low)".ljust(39), f"{ticker_info['fiftyTwoWeekLow']} - {ticker_info['fiftyTwoWeekHigh']} : {ticker_info['fiftyTwoWeekHigh'] - ticker_info['fiftyTwoWeekLow']:.4f} ({100 * (ticker_info['regularMarketPrice'] / ticker_info['fiftyTwoWeekLow'] - 1):.4f}%)".rjust(40))

            avg50  = "fiftyDayAverage" in ticker_info and ticker_info['fiftyDayAverage'] is not None
            avg200 = "twoHundredDayAverage" in ticker_info and ticker_info['twoHundredDayAverage'] is not None
            if avg50 and avg200:
                print(f"SMA 50 | SMA 200".ljust(39), f"{ticker_info['fiftyDayAverage']:.4f} | {ticker_info['twoHundredDayAverage']:.4f}".rjust(40))
            elif avg50:
                print(f"SMA 50".ljust(39), f"{ticker_info['fiftyDayAverage']:.4f}".rjust(40))
            elif avg200:
                print(f"SMA 200".ljust(39), f"{ticker_info['twoHundredDayAverage']:.4f}".rjust(40))
            if "beta" in ticker_info and ticker_info['beta'] is not None and "beta3Year" in ticker_info and ticker_info['beta3Year'] is not None:
                print(f"Beta | 3Yr".ljust(39), f"{ticker_info['beta']} | {ticker_info['beta3Year']}".rjust(40))
            elif "beta" in ticker_info and ticker_info['beta'] is not None:
                print(f"Beta".ljust(39), f"{ticker_info['beta']}".rjust(40))
            if "threeYearAverageReturn" in ticker_info and ticker_info['threeYearAverageReturn'] is not None and "fiveYearAverageReturn" in ticker_info and ticker_info['fiveYearAverageReturn'] is not None:
                print(f"Avg. Return 3Yr | 5Yr".ljust(39), f"{100 * ticker_info['threeYearAverageReturn']:.4f}% | {100 * ticker_info['fiveYearAverageReturn']:.4f}%".rjust(40))

            # Dividends and Splits
            if not dividends.empty or not splits.empty:
                print("\n====  Dividends / Splits   " + div)
                if "dividendRate" in ticker_info and ticker_info['dividendRate'] is not None and "dividendYield" in ticker_info and ticker_info['dividendYield'] is not None and "payoutRatio" in ticker_info and ticker_info['payoutRatio'] is not None:
                    print(f"Rate | Yield | Payout Ratio".ljust(39), f"{ticker_info['dividendRate']} | {100 * ticker_info['dividendYield']:.4f}% | {ticker_info['payoutRatio']}".rjust(40))
                if "trailingAnnualDividendRate" in ticker_info and ticker_info['trailingAnnualDividendRate'] is not None and "trailingAnnualDividendYield" in ticker_info and ticker_info['trailingAnnualDividendYield'] is not None:
                    print(f"Trailing Annual Dividend Rate | Yield".ljust(40), f"{ticker_info['trailingAnnualDividendRate']} | {100 * ticker_info['trailingAnnualDividendYield']:.4f}%\n".rjust(40))
            if not dividends.empty:
                dividends.name = "Value"
                total_dividends = dividends.size
                dividendsdf = DataFrame(dividends.tail(snd_length)[::-1]).T
                print(f"Dividends (Last {snd_length} of {total_dividends}):\n{dividendsdf}")

            if not splits.empty:
                splits.name = "Ratio"
                total_splits = splits.size
                splitsdf = DataFrame(splits.tail(snd_length)[::-1]).T
                print(f"\nStock Splits (Last {snd_length} of {total_splits}):\n{splitsdf}")

        if kind in _all + ["institutional_holders", "ih"]:
            ihdf = yfd.institutional_holders
            if ihdf is not None and "Date Reported" in ihdf.columns:
                ihdf.set_index("Date Reported", inplace=True)
                ihdf["Shares"] = ihdf.apply(lambda x: f"{x['Shares']:,}", axis=1)
                ihdf["Value"] = ihdf.apply(lambda x: f"{x['Value']:,}", axis=1)
                if kind not in _all: print(f"\n{ticker_info['symbol']}")
                print("\n====  Instl. Holders       " + div + f"\n{ihdf}")

        if kind in _all + ["major_holders", "mh"]:
            mhdf = yfd.major_holders
            if mhdf is not None and "Major Holders" in mhdf.columns:
                mhdf.columns = ["Percentage", "Major Holders"]
                mhdf.set_index("Major Holders", inplace=True)
                mhdf["Shares"] = mhdf.apply(lambda x: f"{x['Shares']:,}", axis=1)
                mhdf["Value"] = mhdf.apply(lambda x: f"{x['Value']:,}", axis=1)
                if kind not in _all: print(f"\n{ticker_info['symbol']}")
                print("\n====  Major Holders       " + div + f"\n{mhdf}")

        if kind in _all + ["mutualfund_holders", "mfh"]:
            mfhdf = yfd.get_mutualfund_holders()
            if mfhdf is not None and "Holder" in mfhdf.columns:
                mfhdf.set_index("Date Reported", inplace=True)
                mfhdf["Shares"] = mfhdf.apply(lambda x: f"{x['Shares']:,}", axis=1)
                mfhdf["Value"] = mfhdf.apply(lambda x: f"{x['Value']:,}", axis=1)
                if kind not in _all: print(f"\n{ticker_info['symbol']}")
                print("\n====  Mutual Fund Holders  " + div + f"\n{mfhdf}")

        if kind in _all + ["recommendations", "rec"]:
            recdf = yfd.recommendations
            if recdf is not None:
                recdf = ytd(recdf)
                # recdf_grade = recdf["To Grade"].value_counts().T
                # recdf_grade.name = "Grades"
                if kind not in _all: print(f"\n{ticker_info['symbol']}")
                print("\n====  Recommendation(YTD)  " + div + f"\n{recdf}")

        if kind in _all + ["calendar", "cal"]:
            caldf = yfd.calendar
            if caldf is not None and "Earnings Date" in caldf.columns:
                    caldf.set_index("Earnings Date", inplace=True)
                    if kind not in _all: print(f"\n{ticker_info['symbol']}")
                    print("\n====  Earnings Calendar    " + div + f"\n{caldf}")

        if kind in _all + ["earnings", "earn"]:
            earndf = yfd.earnings
            if not earndf.empty:
                earndf["Revenue"] = earndf.apply(lambda x: f"{x['Revenue']:,}", axis=1)
                earndf["Earnings"] = earndf.apply(lambda x: f"{x['Earnings']:,}", axis=1)
                if kind not in _all: print(f"\n{ticker_info['symbol']}")
                print("\n====  Earnings             " + div + f"\n{earndf}")

        if kind in _all + ["sustainability", "sus", "esg"]:
            susdf = yfd.sustainability
            if susdf is not None:
                susdf.replace({None: False}, inplace=True)
                susdf.columns = ["Score"]
                susdf.drop(susdf[susdf["Score"] == False].index, inplace=True)
                susdf.rename(index=_camelCase2Title, errors="ignore", inplace=True)
                susdf.index.name = "Source"
                if kind not in _all: print(f"\n{ticker_info['symbol']}")
                print("\n====  Sustainability/ESG   " + div + f"\n{susdf}")

        if kind in _all + ["financials", "fin"]:
            icdf = yfd.financials
            bsdf = yfd.balance_sheet
            cfdf = yfd.cashflow

            if icdf.empty or bsdf.empty or cfdf.empty:
                if yfra.__version__ <= "0.1.54":
                    print(f"[!] Best choice: update yfinance to the latest version.")
                    print(f"[!] Ignore if aleady patched. Some tickers do not have financials.")
                    print(f"[!] Otherwise to enable Company Financials, see yfinance Issue #517 patch.")
                    print(f"[!] https://github.com/ranaroussi/yfinance/pull/517/files")
            else:
                print("\n====  Company Financials   " + div)
                if not icdf.empty: print(f"Income Statement:\n{icdf}\n")
                if not bsdf.empty: print(f"Balance Sheet:\n{bsdf}\n")
                if not cfdf.empty: print(f"Cash Flow:\n{cfdf}\n")

        if kind in _all + ["option_chain", "oc"]:
            try:
                yfd_options = yfd.options
            except IndexError as ie:
                yfd_options = None

            if yfd_options is not None:
                opt_expirations = list(yfd_options)
                just_calls = kwargs.pop("calls", None)
                just_puts = kwargs.pop("puts", None)
                itm = kwargs.pop("itm", None)
                opt_date = kwargs.pop("exp", opt_expirations[0])
                opt_expirations_str = f"{ticker} Option Expirations:\n\t{', '.join(opt_expirations)}\n"

                if kind not in _all: print(f"\n{ticker_info['symbol']}")
                if isinstance(itm, bool) and itm: print("\n====  ITM Option Chains    " + div)
                elif isinstance(itm, bool) and not itm: print("\n====  OTM Option Chains    " + div)
                else: print("\n====  Option Chains        " + div)
                print(opt_expirations_str)

                if opt_date not in opt_expirations:
                    print(f"[X] No Options for {ticker_info['quoteType']} {ticker_info['symbol']}")
                else:
                    option_columns = ["Contract", "Last Trade", "Strike", "Price", "Bid", "Ask", "Change", "Percent Change", "Volume", "OI", "IV", "ITM", "Size", "Currency"]
                    cp_chain = yfd.option_chain(proxy=proxy)
                    calls, puts = cp_chain.calls, cp_chain.puts
                    calls.columns = puts.columns = option_columns
                    calls.set_index("Contract", inplace=True)
                    puts.set_index("Contract", inplace=True)

                    calls.name = f"{ticker} Calls for {opt_date}"
                    puts.name = f"{ticker} Puts for {opt_date}"

                    if isinstance(itm, bool):
                        in_or_out = "ITM" if itm else "OTM"
                        calls.name, puts.name = f"{calls.name} {in_or_out}", f"{puts.name} {in_or_out}"
                        itm_calls = f"{calls.name}\n{calls[calls['ITM'] == itm]}"
                        itm_puts = f"{puts.name}\n{puts[puts['ITM'] == itm]}"

                        if    just_calls: print(itm_calls)
                        elif  just_puts: print(itm_puts)
                        else: print(f"{itm_calls}\n\n{itm_puts}")
                    else:
                        all_calls, all_puts = f"{calls.name}\n{calls}", f"{puts.name}\n{puts}"
                        if    just_calls: print(all_calls)
                        elif  just_puts: print(all_puts)
                        else: print(f"{all_calls}\n\n{all_puts}")

        if verbose:
            print("\n====  Chart History        " + div + f"\n[*] Pandas TA v{version} & yfinance v{yfra.__version__}")
            print(f"[+] Downloading {ticker}[{interval}:{period}] from Yahoo Finance")
        if show is not None and isinstance(show, int) and show > 0:
            print(f"\n{df.name}\n{df.tail(show)}\n")
        if verbose: print("=" * 80 + "\n")
        # else: print()
        return df

    else:
        return DataFrame()
