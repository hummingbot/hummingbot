# pylint: disable=bad-continuation



def get_fee(
    self,
    base_currency: str,
    quote_currency: str,
    order_type: OrderType,
    order_side: TradeType, # TradeType.BUY TradeType.SELL
    amount: Decimal,
    price: Decimal = Decimal("nan"),
    is_maker: Optional[bool] = None,
    *_,
    **__,
) -> TradeFeeBase:
    """
    Calculates the estimated fee an order would pay
    """
    # FIXME the hummingbot binance reference is a path to deprecation warning
    # there appears to be no functional reference material, see:
    # ~
    # ~ BitshareExchange
    ## ~ ExchangeBase
    ### ~ ConnectorBase
    #### ~ estimate_fee_pct
    ##### ~ core.utils.estimate_fee.estimate_fee  << binance ends here not implemented
    # self.logger().info("get_fee")
    # I suspect the correct implementation will be:

    account = dict(self.metanode.account) # DISCRETE SQL QUERY
    objects = dict(self.metanode.objects) # DISCRETE SQL QUERY
    assets = dict(sels.metanode.assets) # DISCRETE SQL QUERY
    tx_currency = objects["1.3.0"]["name"]
    tx_amount = account["fees_account"]["create"]
    # you pay market fee on the currency you receive in the transaction
    market_currency = quote_currency
    maker_pct = assets[quote_currency]["fees_asset"]["maker"]
    taker_pct = assets[quote_currency]["fees_asset"]["taker"]
    if order_side == TradeType.BUY:
        market_currency = base_currency
        maker_pct = assets[base_currency]["fees_asset"]["maker"]
        taker_pct = assets[base_currency]["fees_asset"]["taker"]
    market_pct = maker_pct if is_maker else taker_pct
    # build a TradeFeeBase class object
    fee = TradeFeeBase()
    flat_fee = TokenAmount()
    flat_fee.token = tx_currency
    flat_fee.amount = Decimal(tx_amount)
    fee.flat_fees = [flat_fee]
    fee.percent = Decimal(market_pct)
    fee.percent_token = market_currency if market_currency != quote_currency else None

    # return fee
    # FIXME effectively ZERO
    return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(False))
