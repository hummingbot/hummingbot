from decimal import Decimal
from Crypto.Hash import keccak

s_decimal_0 = Decimal(0)
s_decimal_max = Decimal("1e40")
NaN = float("nan")


def unpad(padded_obj):
    precision = padded_obj["currency"]["precision"]
    return Decimal(padded_obj["amount"]) * Decimal(f"1e-{precision}")


def sha3(x):
    return keccak.new(digest_bits=256, data=x).hexdigest()


cdef class DolomiteToken:
    def __init__(self, raw_token: object):
        self.ticker = raw_token["ticker"]
        self.precision = int(raw_token["precision"])
        self.contract_address = raw_token["identifier"]

    def pad(self, unpadded_amount):
        return str(int(Decimal(unpadded_amount) * Decimal(f"1e{self.precision}")))

    def __repr__(self) -> str:
        return f"DolomiteToken(ticker='{self.ticker}', " \
               f"precision={self.precision}, " \
               f"contract_address={self.contract_address})"


cdef class DolomiteTradingRule(TradingRule):
    def __init__(self,
                 trading_pair: str,
                 min_order_size: Decimal,
                 max_order_size: Decimal,
                 primary_token: DolomiteToken,
                 secondary_token: DolomiteToken,
                 amount_decimal_places: int,
                 price_decimal_places: int):
        super().__init__(
            trading_pair=trading_pair,
            min_order_size=min_order_size,
            max_order_size=max_order_size,
            min_price_increment=Decimal('1e-8'),
            min_base_amount_increment=Decimal('1e-8'),
            min_quote_amount_increment=Decimal('1e-8'),
            supports_limit_orders=True,
            supports_market_orders=True)

        self.primary_token = primary_token
        self.secondary_token = secondary_token
        self.amount_decimal_places = amount_decimal_places
        self.price_decimal_places = price_decimal_places

    @classmethod
    def build(cls, trading_pair, market, exchange_info, account_info, exchange_rates, token_registry):
        max_order_size_usd = s_decimal_max
        min_order_size_usd = exchange_info.min_order_size_usd

        if account_info["limits"]["daily_max_trade_amount_usd"] is not None:
            daily_max_usd = unpad(account_info["limits"]["daily_max_trade_amount_usd"])
            daily_used_usd = unpad(account_info["limits"]["daily_used_trade_amount_usd"])
            max_order_size_usd = daily_max_usd - daily_used_usd

        primary_token = DolomiteToken(token_registry[market["primary_token"]])
        secondary_token = DolomiteToken(token_registry[market["secondary_token"]])

        amount_decimal_places = market["primary_ticker_decimal_places"]
        price_decimal_places = market["secondary_ticker_price_decimal_places"]

        return DolomiteTradingRule(
            trading_pair=trading_pair,
            min_order_size=exchange_rates.from_base(min_order_size_usd, "USD", secondary_token.ticker),
            max_order_size=exchange_rates.from_base(max_order_size_usd, "USD", secondary_token.ticker),
            primary_token=primary_token,
            secondary_token=secondary_token,
            amount_decimal_places=amount_decimal_places,
            price_decimal_places=price_decimal_places
        )


class DolomiteExchangeRates:
    def __init__(self, raw_rates):
        self.raw_rates = raw_rates

    def to_base(self, amount, ticker, base_ticker):
        return Decimal(amount) * Decimal(self.raw_rates[ticker]["quote"][base_ticker]["exchange_rate"])

    def from_base(self, amount, base_ticker, ticker):
        return Decimal(amount) / Decimal(self.raw_rates[ticker]["quote"][base_ticker]["exchange_rate"])

    def convert(self, amount, ticker, to_ticker):
        intermediate_quote = Decimal(self.raw_rates[ticker]["quote"]["ETH"]["exchange_rate"])
        final_quote = Decimal(self.raw_rates[to_ticker]["quote"]["ETH"]["exchange_rate"])
        return (Decimal(amount) * intermediate_quote) / final_quote


class DolomiteExchangeInfo:
    def __init__(self,
                 spender_wallet_address,
                 fee_collecting_wallet_address,
                 maker_fee_percentage,
                 taker_fee_percentage,
                 min_order_size_usd,
                 per_fill_fee_registry,
                 spot_trading_fee_premium_registry,
                 fee_burn_rates_table):
        self.spender_wallet_address = spender_wallet_address
        self.fee_collecting_wallet_address = fee_collecting_wallet_address
        self.maker_fee_percentage = maker_fee_percentage
        self.taker_fee_percentage = taker_fee_percentage
        self.min_order_size_usd = min_order_size_usd
        self.per_fill_fee_registry = per_fill_fee_registry
        self.spot_trading_fee_premium_registry = spot_trading_fee_premium_registry
        self.fee_burn_rates_table = fee_burn_rates_table

    @classmethod
    def from_json(cls, exchange_info):
        per_fill_fee_registry = exchange_info["base_spot_trading_fee_amounts"]
        for ticker, padded_amount in per_fill_fee_registry.iteritems():
            per_fill_fee_registry[ticker] = unpad(padded_amount)

        spot_trading_fee_premium_registry = exchange_info["spot_trading_fee_premium_amounts"]
        for ticker, padded_amount in spot_trading_fee_premium_registry.iteritems():
            spot_trading_fee_premium_registry[ticker] = unpad(padded_amount)

        fee_burn_rates_table = {
            "DAI": Decimal(0.15),
            "WETH": Decimal(0.15),
            "LRC": Decimal(0.10),
            "BAT": Decimal(0.20)
        }

        return DolomiteExchangeInfo(
            spender_wallet_address=exchange_info["loopring_delegate_address"],
            fee_collecting_wallet_address=exchange_info["fee_collecting_wallet_address"],
            maker_fee_percentage=Decimal(exchange_info["maker_fee_percentage"]),
            taker_fee_percentage=Decimal(exchange_info["taker_fee_percentage"]),
            min_order_size_usd=unpad(exchange_info["min_usd_maker_trade_amount"]),
            per_fill_fee_registry=per_fill_fee_registry,
            spot_trading_fee_premium_registry=spot_trading_fee_premium_registry,
            fee_burn_rates_table=fee_burn_rates_table
        )
